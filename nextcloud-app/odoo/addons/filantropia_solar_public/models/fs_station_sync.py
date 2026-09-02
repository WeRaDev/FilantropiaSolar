"""Inbound NC->CRM mirror + fleet import (all NC stations present in CRM)."""

from __future__ import annotations

import contextlib
from datetime import timedelta
import logging

from odoo import api, fields, models

from ..services.nc_lifecycle_client import (
    NcLifecycleClient,
    NcLifecycleError,
    redact_secrets,
)
from ..services.stage_map import stage_xmlid_for_nc_state

_logger = logging.getLogger(__name__)

# Inbound NC webhook often echoes a CRM->NC profile/lifecycle write within
# milliseconds. Applying it again races the outbound job's crm.lead write
# (Postgres "could not serialize access due to concurrent update").
_FS_CRM_ECHO_SECONDS = 20


class FsStationSync(models.AbstractModel):
    _name = "fs.station.sync"
    _description = "Filantropia NC station CRM mirror"

    @api.model
    def _stage_for_nc_state(
        self, lifecycle_state: str | None, *, public_archived: bool = False
    ):
        xmlid = stage_xmlid_for_nc_state(
            lifecycle_state, public_archived=bool(public_archived)
        )
        if not xmlid:
            return self.env.ref("crm.stage_lead1", raise_if_not_found=False)
        return self.env.ref(xmlid, raise_if_not_found=False)

    @api.model
    def _default_mirror_user(self):
        """Salesperson visible in CRM Pipeline (not OdooBot/__system__)."""
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        if admin and admin.active and not admin.share:
            return admin
        return (
            self.env["res.users"]
            .sudo()
            .search([("share", "=", False), ("active", "=", True)], order="id", limit=1)
        )

    @api.model
    def _default_mirror_team(self):
        team = self.env.ref(
            "sales_team.team_sales_department", raise_if_not_found=False
        )
        if team:
            return team
        return self.env["crm.team"].sudo().search([], order="id", limit=1)

    @api.model
    def upsert_from_nc_station(self, station: dict, *, origin: str = "nc"):
        """Create/update crm.lead from NC lifecycle station payload."""
        Lead = self.env["crm.lead"].sudo()
        installation_id = (station.get("installation_id") or "").strip()
        source = (station.get("source") or "").strip().lower()
        if source == "dataset":
            # Training corpus is not part of the CRM mirror.
            return Lead.browse()
        odoo_lead_id = station.get("odoo_lead_id")
        lead = Lead.browse()
        if odoo_lead_id:
            with contextlib.suppress(TypeError, ValueError):
                cand = Lead.browse(int(odoo_lead_id))
                if cand.exists():
                    lead = cand
        # Match by NC primary key before installation_id: changing location
        # rewrites location_serial installation_id while DB id stays stable.
        if not lead and station.get("id") is not None:
            with contextlib.suppress(TypeError, ValueError):
                nc_db_id = int(station["id"])
                if nc_db_id:
                    lead = Lead.search([("fs_nc_db_id", "=", nc_db_id)], limit=1)
        if not lead and installation_id:
            lead = Lead.search(
                [("fs_nc_installation_id", "=", installation_id)], limit=1
            )

        # Dampen CRM->NC->CRM echo: if this lead was just written by CRM (or is
        # still pending an outbound job), skip a redundant webhook upsert.
        if lead and origin == "nc" and self._is_crm_echo(lead, station):
            _logger.info(
                "NC webhook echo skipped for lead %s iid=%s (recent CRM origin)",
                lead.id,
                installation_id or lead.fs_nc_installation_id,
            )
            return lead

        public_archived = bool(station.get("public_archived"))
        stage = self._stage_for_nc_state(
            station.get("lifecycle_state"), public_archived=public_archived
        )
        name = station.get("name") or installation_id or "NC station"
        vals = {
            "type": "opportunity",
            "active": True,
            "fs_is_donation_application": True,
            "fs_nc_installation_id": installation_id or False,
            "fs_nc_lifecycle_state": station.get("lifecycle_state") or False,
            "fs_nc_public_archived": public_archived,
            "fs_nc_sync_state": "ok",
            "fs_nc_sync_error": False,
            "fs_nc_last_sync_at": fields.Datetime.now(),
            "fs_nc_sync_origin": origin,
            "fs_station_location_label": station.get("location") or False,
            "fs_station_latitude": float(station.get("latitude") or 0.0),
            "fs_station_longitude": float(station.get("longitude") or 0.0),
            "fs_station_capacity_kwp": float(station.get("capacity_kwp") or 0.0),
            "fs_station_website": station.get("website") or False,
            "fs_station_short_description": station.get("short_description") or False,
            # Station title only — do not clobber organisation (partner_name)
            # when CRM already has a distinct org label.
            "name": name,
            "city": station.get("location") or False,
            "website": station.get("website") or False,
        }
        # Seed partner_name only on create, when empty, or when it still equals
        # the old station title (user never set a distinct organisation).
        if (
            not lead
            or not (lead.partner_name or "").strip()
            or (lead.partner_name or "").strip() == (lead.name or "").strip()
        ):
            vals["partner_name"] = name
        if (
            station.get("grid_price_kwh") is not None
            and station.get("grid_price_kwh") != ""
        ):
            with contextlib.suppress(TypeError, ValueError):
                vals["fs_station_grid_price_kwh"] = float(
                    station.get("grid_price_kwh") or 0.0
                )
        gct = (station.get("grid_connection_type") or "").strip().lower()
        if gct in ("on_grid", "off_grid"):
            vals["fs_station_grid_connection_type"] = gct
        if station.get("id") is not None:
            with contextlib.suppress(TypeError, ValueError):
                vals["fs_nc_db_id"] = int(station["id"])
        # Always force stage from NC lifecycle so reconcile heals drift.
        if stage:
            vals["stage_id"] = stage.id

        # CRM Pipeline defaults to "My Pipeline" (assigned_to_me). Mirror leads
        # created under sudo often land on OdooBot and disappear for admin.
        mirror_user = self._default_mirror_user()
        mirror_team = self._default_mirror_team()
        system_user = self.env.ref("base.user_root", raise_if_not_found=False)
        need_user = (
            not lead
            or not lead.user_id
            or (system_user and lead.user_id == system_user)
        )
        if need_user and mirror_user:
            vals["user_id"] = mirror_user.id
        if (not lead or not lead.team_id) and mirror_team:
            vals["team_id"] = mirror_team.id

        if lead:
            if hasattr(lead, "_fs_safe_write"):
                lead._fs_safe_write(vals)
            else:
                lead.with_context(fs_skip_nc_enqueue=True).write(vals)
            return lead
        return Lead.with_context(fs_skip_nc_enqueue=True).create(vals)

    @api.model
    def _is_crm_echo(self, lead, station: dict) -> bool:
        """True when inbound NC event is an echo of a recent CRM outbound write."""
        if not lead or not lead.exists():
            return False
        # Still waiting on outbound job: webhook is almost certainly the echo.
        if (lead.fs_nc_sync_state or "") == "pending" and (
            lead.fs_nc_sync_origin or ""
        ) == "crm":
            return True
        if (lead.fs_nc_sync_origin or "") != "crm":
            return False
        last = lead.fs_nc_last_sync_at
        if not last:
            return False
        now = fields.Datetime.now()
        try:
            age = now - last
        except TypeError:
            return False
        if age > timedelta(seconds=_FS_CRM_ECHO_SECONDS):
            return False
        # Same station identity when NC sends ids (avoid suppressing real edits
        # that arrive on a different station bound later).
        st_iid = (station.get("installation_id") or "").strip()
        lead_iid = (lead.fs_nc_installation_id or "").strip()
        if st_iid and lead_iid and st_iid != lead_iid:
            st_db = station.get("id")
            if st_db is None or int(st_db or 0) != int(lead.fs_nc_db_id or 0):
                return False
        return True

    @api.model
    def _bind_nc_lead_if_needed(
        self, lead, station: dict, client: NcLifecycleClient
    ) -> bool:
        """Write odoo_lead_id back to NC when missing (true bidirectional link)."""
        if not lead or not lead.exists():
            return False
        installation_id = (
            station.get("installation_id") or lead.fs_nc_installation_id or ""
        ).strip()
        if not installation_id:
            return False
        existing = station.get("odoo_lead_id")
        if existing is not None:
            with contextlib.suppress(TypeError, ValueError):
                if int(existing) == int(lead.id):
                    return False
                if int(existing) != int(lead.id):
                    _logger.warning(
                        "NC station %s already bound to lead %s (crm %s); skip bind",
                        installation_id,
                        existing,
                        lead.id,
                    )
                    return False
        # Prefer numeric NC PK when present — installation_id may be location_{id}
        # when serial_number is null and older resolvers miss it.
        bind_keys: list[str] = []
        nc_db_id = (
            station.get("id") if station.get("id") is not None else lead.fs_nc_db_id
        )
        if nc_db_id is not None:
            with contextlib.suppress(TypeError, ValueError):
                bind_keys.append(str(int(nc_db_id)))
        bind_keys.append(installation_id)
        last_err: Exception | None = None
        for key in bind_keys:
            try:
                client.bind_lead(key, int(lead.id))
                return True
            except NcLifecycleError as exc:
                last_err = exc
                continue
        _logger.warning(
            "NC bind-lead failed for %s lead %s: %s",
            installation_id,
            lead.id,
            redact_secrets(str(last_err) if last_err else "unknown"),
        )
        return False

    @api.model
    def import_all_from_nc(self) -> dict:
        """Pull NC ops stations into CRM leads and bind reverse links."""
        client = NcLifecycleClient()
        try:
            payload = client.list_stations(
                include_soft_removed=False, include_dataset=False
            )
        except NcLifecycleError as exc:
            _logger.warning("NC list stations failed: %s", redact_secrets(str(exc)))
            return {"ok": False, "error": redact_secrets(str(exc))}
        stations = []
        if isinstance(payload, dict):
            stations = payload.get("stations") or []
        created = updated = bound = skipped = 0
        Lead = self.env["crm.lead"].sudo()
        seen_iids: set[str] = set()
        for st in stations:
            if not isinstance(st, dict):
                skipped += 1
                continue
            if (st.get("source") or "").strip().lower() == "dataset":
                skipped += 1
                continue
            installation_id = (st.get("installation_id") or "").strip()
            if not installation_id:
                skipped += 1
                continue
            seen_iids.add(installation_id)
            existed = bool(
                Lead.search_count([("fs_nc_installation_id", "=", installation_id)])
            )
            lead = self.upsert_from_nc_station(st, origin="sync")
            if not lead:
                skipped += 1
                continue
            if existed:
                updated += 1
            else:
                created += 1
            if self._bind_nc_lead_if_needed(lead, st, client):
                bound += 1

        # Archive CRM mirror leads that no longer exist on NC ops list
        # (e.g. prior dataset imports). Keep candidatura New leads without iid.
        archived = 0
        orphans = Lead.search(
            [
                ("fs_nc_installation_id", "!=", False),
                ("fs_is_donation_application", "=", True),
            ]
        )
        for lead in orphans:
            iid = (lead.fs_nc_installation_id or "").strip()
            if iid and iid not in seen_iids and lead.active:
                lead.with_context(fs_skip_nc_enqueue=True).write(
                    {
                        "active": False,
                        "fs_nc_sync_state": "skipped",
                        "fs_nc_sync_error": "Not on NC ops station list (archived by reconcile)",
                        "fs_nc_sync_origin": "sync",
                        "fs_nc_last_sync_at": fields.Datetime.now(),
                    }
                )
                archived += 1

        _logger.info(
            "NC fleet import done created=%s updated=%s bound=%s archived=%s "
            "skipped=%s total=%s",
            created,
            updated,
            bound,
            archived,
            skipped,
            len(stations),
        )
        return {
            "ok": True,
            "created": created,
            "updated": updated,
            "bound": bound,
            "archived": archived,
            "skipped": skipped,
            "total": len(stations),
        }

    @api.model
    def cron_import_all_from_nc(self):
        self.import_all_from_nc()
