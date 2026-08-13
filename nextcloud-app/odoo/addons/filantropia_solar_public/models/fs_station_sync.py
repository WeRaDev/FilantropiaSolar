"""Inbound NC->CRM mirror + fleet import (all NC stations present in CRM)."""

from __future__ import annotations

import contextlib
import logging

from odoo import api, fields, models

from ..services.nc_lifecycle_client import (
    NcLifecycleClient,
    NcLifecycleError,
    redact_secrets,
)
from ..services.stage_map import stage_xmlid_for_nc_state

_logger = logging.getLogger(__name__)

_MODULE = "filantropia_solar_public"


class FsStationSync(models.AbstractModel):
    _name = "fs.station.sync"
    _description = "Filantropia NC station CRM mirror"

    @api.model
    def _stage_for_nc_state(self, lifecycle_state: str | None):
        xml_frag = stage_xmlid_for_nc_state(lifecycle_state)
        if not xml_frag:
            return self.env.ref(f"{_MODULE}.stage_new", raise_if_not_found=False)
        return self.env.ref(f"{_MODULE}.{xml_frag}", raise_if_not_found=False)

    @api.model
    def upsert_from_nc_station(self, station: dict, *, origin: str = "nc"):
        """Create/update crm.lead from NC lifecycle station payload."""
        Lead = self.env["crm.lead"].sudo()
        installation_id = (station.get("installation_id") or "").strip()
        odoo_lead_id = station.get("odoo_lead_id")
        lead = Lead.browse()
        if odoo_lead_id:
            with contextlib.suppress(TypeError, ValueError):
                cand = Lead.browse(int(odoo_lead_id))
                if cand.exists():
                    lead = cand
        if not lead and installation_id:
            lead = Lead.search(
                [("fs_nc_installation_id", "=", installation_id)], limit=1
            )

        stage = self._stage_for_nc_state(station.get("lifecycle_state"))
        vals = {
            "fs_is_donation_application": True,
            "fs_nc_installation_id": installation_id or False,
            "fs_nc_lifecycle_state": station.get("lifecycle_state") or False,
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
            "partner_name": station.get("name") or False,
            "name": station.get("name") or installation_id or "NC station",
        }
        if station.get("id") is not None:
            with contextlib.suppress(TypeError, ValueError):
                vals["fs_nc_db_id"] = int(station["id"])
        if stage and (not lead or lead.stage_id != stage):
            vals["stage_id"] = stage.id

        if lead:
            lead.with_context(fs_skip_nc_enqueue=True).write(vals)
            return lead
        return Lead.with_context(fs_skip_nc_enqueue=True).create(vals)

    @api.model
    def import_all_from_nc(self) -> dict:
        """Pull all NC stations into CRM leads (reconciliation)."""
        client = NcLifecycleClient()
        try:
            payload = client.list_stations(include_soft_removed=False)
        except NcLifecycleError as exc:
            _logger.warning("NC list stations failed: %s", redact_secrets(str(exc)))
            return {"ok": False, "error": redact_secrets(str(exc))}
        stations = []
        if isinstance(payload, dict):
            stations = payload.get("stations") or []
        created = updated = 0
        Lead = self.env["crm.lead"].sudo()
        for st in stations:
            if not isinstance(st, dict):
                continue
            installation_id = (st.get("installation_id") or "").strip()
            existed = bool(
                installation_id
                and Lead.search_count([("fs_nc_installation_id", "=", installation_id)])
            )
            self.upsert_from_nc_station(st, origin="sync")
            if existed:
                updated += 1
            else:
                created += 1
        _logger.info(
            "NC fleet import done created=%s updated=%s total=%s",
            created,
            updated,
            len(stations),
        )
        return {
            "ok": True,
            "created": created,
            "updated": updated,
            "total": len(stations),
        }

    @api.model
    def cron_import_all_from_nc(self):
        self.import_all_from_nc()
