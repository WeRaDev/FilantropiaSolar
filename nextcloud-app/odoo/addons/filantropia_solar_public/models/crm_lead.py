"""CRM lead extensions: NC lifecycle sync fields + actions (mirror CRM <-> NC)."""

from __future__ import annotations

import contextlib
import logging
from typing import ClassVar

from odoo import api, fields, models

from ..services.nc_lifecycle_client import (
    NcLifecycleClient,
    NcLifecycleError,
    redact_secrets,
)
from ..services.stage_map import lifecycle_action_for_stage_change, nc_state_for_stage

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    _inherit = "crm.lead"

    fs_nc_installation_id = fields.Char(
        string="NC installation id",
        copy=False,
        index=True,
        help="Nextcloud installation_id (location_serial) linked to this lead.",
    )
    fs_nc_db_id = fields.Integer(
        string="NC DB id",
        copy=False,
        help="Nextcloud internal station primary key when known.",
    )
    fs_nc_lifecycle_state = fields.Selection(
        selection=[
            ("virtual", "Virtual"),
            ("planned", "Planned"),
            ("running", "Running"),
        ],
        string="NC lifecycle",
        copy=False,
    )
    fs_nc_sync_state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("ok", "OK"),
            ("error", "Error"),
            ("skipped", "Skipped"),
        ],
        string="NC sync state",
        copy=False,
        default="pending",
    )
    fs_nc_sync_error = fields.Text(string="NC sync error", copy=False)
    fs_nc_last_sync_at = fields.Datetime(string="NC last sync", copy=False)
    fs_nc_sync_origin = fields.Selection(
        selection=[
            ("crm", "CRM"),
            ("nc", "Nextcloud"),
            ("sync", "Reconcile"),
        ],
        string="NC sync origin",
        copy=False,
        help="Last writer in the CRM/NC mirror; used to avoid echo loops.",
    )

    # Snapshot used to create the Virtual station (set by candidatura controller)
    fs_station_location_label = fields.Char(string="Station location label", copy=False)
    fs_station_latitude = fields.Float(
        string="Station latitude", digits=(10, 6), copy=False
    )
    fs_station_longitude = fields.Float(
        string="Station longitude", digits=(10, 6), copy=False
    )
    fs_station_capacity_kwp = fields.Float(
        string="Station capacity kWp", digits=(12, 3), copy=False
    )
    fs_station_grid_price_kwh = fields.Float(
        string="Station grid price EUR/kWh",
        digits=(8, 4),
        copy=False,
    )
    fs_station_grid_connection_type = fields.Selection(
        selection=[
            ("on_grid", "On-grid"),
            ("off_grid", "Off-grid"),
        ],
        string="Grid connection",
        default="on_grid",
        copy=False,
    )
    fs_station_website = fields.Char(string="Organisation website", copy=False)
    fs_station_short_description = fields.Text(
        string="Organisation short description",
        copy=False,
    )
    fs_is_donation_application = fields.Boolean(
        string="Filantropia donation application",
        default=False,
        copy=False,
        help="True for NGO candidatura leads that participate in NC lifecycle mirror.",
    )

    def _fs_client(self) -> NcLifecycleClient:
        return NcLifecycleClient()

    def _fs_apply_station_payload(self, payload: dict, *, origin: str = "crm") -> None:
        station = (payload or {}).get("station") or {}
        vals = {
            "fs_nc_last_sync_at": fields.Datetime.now(),
            "fs_nc_sync_state": "ok",
            "fs_nc_sync_error": False,
            "fs_nc_sync_origin": origin,
        }
        if station.get("installation_id"):
            vals["fs_nc_installation_id"] = station["installation_id"]
        if station.get("id") is not None:
            with contextlib.suppress(TypeError, ValueError):
                vals["fs_nc_db_id"] = int(station["id"])
        if station.get("lifecycle_state"):
            vals["fs_nc_lifecycle_state"] = station["lifecycle_state"]
        # Prefer NC snapshot when present so CRM stays symmetrical with NC.
        if station.get("name"):
            # Keep station title (name) in sync; only seed partner_name when empty
            # so org rename is not forced back onto a custom station name.
            if self.fs_nc_installation_id or station.get("installation_id"):
                vals["name"] = station["name"]
            if not (self.partner_name or "").strip():
                vals["partner_name"] = station["name"]
        if station.get("location") is not None:
            vals["fs_station_location_label"] = station.get("location") or False
            vals["city"] = station.get("location") or False
        if station.get("latitude") is not None:
            with contextlib.suppress(TypeError, ValueError):
                vals["fs_station_latitude"] = float(station.get("latitude") or 0.0)
        if station.get("longitude") is not None:
            with contextlib.suppress(TypeError, ValueError):
                vals["fs_station_longitude"] = float(station.get("longitude") or 0.0)
        if station.get("capacity_kwp") is not None:
            with contextlib.suppress(TypeError, ValueError):
                vals["fs_station_capacity_kwp"] = float(
                    station.get("capacity_kwp") or 0.0
                )
        if "website" in station:
            vals["fs_station_website"] = station.get("website") or False
            vals["website"] = station.get("website") or False
        if "short_description" in station:
            vals["fs_station_short_description"] = (
                station.get("short_description") or False
            )
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
        # origin stamp must not re-trigger outbound stage jobs
        self.with_context(fs_skip_nc_enqueue=True).write(vals)

    def _fs_mark_error(self, exc: Exception) -> None:
        msg = redact_secrets(str(exc))
        self.with_context(fs_skip_nc_enqueue=True).write(
            {
                "fs_nc_sync_state": "error",
                "fs_nc_sync_error": msg[:2000],
                "fs_nc_last_sync_at": fields.Datetime.now(),
            }
        )

    def fs_create_virtual_station(self) -> bool:
        """Create Virtual station on NC (idempotent via odoo_lead_id)."""
        self.ensure_one()
        if not self.fs_is_donation_application and not self.fs_nc_installation_id:
            self.with_context(fs_skip_nc_enqueue=True).write(
                {"fs_nc_sync_state": "skipped", "fs_nc_sync_error": False}
            )
            return False

        # Already virtual or beyond: refresh only
        if (
            self.fs_nc_lifecycle_state in ("virtual", "planned", "running")
            and (self.fs_nc_installation_id or "").strip()
        ):
            if self.fs_nc_lifecycle_state == "virtual":
                self.with_context(fs_skip_nc_enqueue=True).write(
                    {"fs_nc_sync_state": "ok", "fs_nc_sync_error": False}
                )
                return True
            # higher states already satisfy ensure_virtual
            return True

        capacity = float(self.fs_station_capacity_kwp or 0.0)
        if capacity <= 0:
            capacity = 1.0  # NC requires positive capacity; ops can edit later

        # Station title: opportunity name; org stays in partner_name / organization_name.
        station_name = (
            (self.name or "").strip()
            or (self.partner_name or "").strip()
            or f"Lead {self.id}"
        )
        payload = {
            "odoo_lead_id": int(self.id),
            "name": station_name,
            "latitude": float(self.fs_station_latitude or 0.0),
            "longitude": float(self.fs_station_longitude or 0.0),
            "capacity_kwp": capacity,
            "location_label": self.fs_station_location_label or self.city or "Portugal",
            "organization_name": self.partner_name or "",
        }
        if (
            self.fs_station_grid_price_kwh is not False
            and self.fs_station_grid_price_kwh is not None
        ):
            payload["grid_price_kwh"] = float(self.fs_station_grid_price_kwh or 0.0)
        gct = (self.fs_station_grid_connection_type or "").strip().lower()
        if gct in ("on_grid", "off_grid"):
            payload["grid_connection_type"] = gct
        website = (self.fs_station_website or self.website or "").strip()
        if website:
            if not website.lower().startswith(("http://", "https://")):
                website = "https://" + website
            payload["website"] = website
        short = (self.fs_station_short_description or "").strip()
        if short:
            payload["short_description"] = short

        try:
            result = self._fs_client().create_virtual(payload)
            self._fs_apply_station_payload(result, origin="crm")
            _logger.info(
                "NC virtual station synced for lead %s -> %s",
                self.id,
                self.fs_nc_installation_id,
            )
            return True
        except NcLifecycleError as exc:
            self._fs_mark_error(exc)
            _logger.warning(
                "NC virtual create failed for lead %s: %s",
                self.id,
                redact_secrets(str(exc)),
            )
            return False

    def fs_promote_planned(self) -> bool:
        """Promote linked NC station Virtual → Planned."""
        self.ensure_one()
        if (
            self.fs_nc_lifecycle_state in ("planned", "running")
            and (self.fs_nc_installation_id or "").strip()
        ):
            return True
        installation_id = (self.fs_nc_installation_id or "").strip()
        if not installation_id:
            if not self.fs_create_virtual_station():
                return False
            installation_id = (self.fs_nc_installation_id or "").strip()
        if not installation_id:
            self._fs_mark_error(
                NcLifecycleError(
                    "missing fs_nc_installation_id after virtual create; "
                    "check FS_LIFECYCLE_API_BASE_URL / token and NC connectivity"
                )
            )
            return False
        try:
            result = self._fs_client().promote_planned(installation_id)
            self._fs_apply_station_payload(result, origin="crm")
            _logger.info(
                "NC promote planned for lead %s -> %s",
                self.id,
                self.fs_nc_installation_id,
            )
            return True
        except NcLifecycleError as exc:
            self._fs_mark_error(exc)
            _logger.warning(
                "NC promote planned failed for lead %s: %s",
                self.id,
                redact_secrets(str(exc)),
            )
            return False

    def fs_mark_installed(self) -> bool:
        """Mark linked NC station Planned → Running (Installed CRM stage)."""
        self.ensure_one()
        if (
            self.fs_nc_lifecycle_state == "running"
            and (self.fs_nc_installation_id or "").strip()
        ):
            return True
        # Ensure Planned first when only Virtual/missing
        if self.fs_nc_lifecycle_state != "planned" and not self.fs_promote_planned():
            return False
        installation_id = (self.fs_nc_installation_id or "").strip()
        if not installation_id:
            self._fs_mark_error(
                NcLifecycleError("missing fs_nc_installation_id for mark-installed")
            )
            return False
        try:
            result = self._fs_client().mark_installed(
                installation_id, actor=f"odoo-lead-{self.id}"
            )
            self._fs_apply_station_payload(result, origin="crm")
            _logger.info(
                "NC mark installed for lead %s -> %s",
                self.id,
                self.fs_nc_installation_id,
            )
            return True
        except NcLifecycleError as exc:
            self._fs_mark_error(exc)
            _logger.warning(
                "NC mark installed failed for lead %s: %s",
                self.id,
                redact_secrets(str(exc)),
            )
            return False

    def _fs_installation_key(self) -> str:
        """Prefer NC PK for writes when serial-less installation_id is fragile."""
        if self.fs_nc_db_id:
            return str(int(self.fs_nc_db_id))
        return (self.fs_nc_installation_id or "").strip()

    def fs_push_station_profile(self) -> bool:
        """Push CRM station snapshot fields to linked NC station."""
        self.ensure_one()
        key = self._fs_installation_key()
        if not key:
            return False
        website = (self.fs_station_website or self.website or "").strip()
        if website and not website.lower().startswith(("http://", "https://")):
            website = "https://" + website
        # Station display name: opportunity name is the editable station title.
        # partner_name stays the organisation; do not overwrite a custom station name.
        station_name = (
            (self.name or "").strip()
            or (self.partner_name or "").strip()
            or f"Lead {self.id}"
        )
        payload = {
            "name": station_name,
            "location_label": self.fs_station_location_label or self.city or "",
            "latitude": float(self.fs_station_latitude or 0.0),
            "longitude": float(self.fs_station_longitude or 0.0),
            "capacity_kwp": float(self.fs_station_capacity_kwp or 0.0),
            "website": website,
            "short_description": (self.fs_station_short_description or "").strip(),
        }
        # Always include grid price when set on the lead (0.0 is valid).
        if (
            self.fs_station_grid_price_kwh is not False
            and self.fs_station_grid_price_kwh is not None
        ):
            payload["grid_price_kwh"] = float(self.fs_station_grid_price_kwh or 0.0)
        gct = (self.fs_station_grid_connection_type or "").strip().lower()
        if gct in ("on_grid", "off_grid"):
            payload["grid_connection_type"] = gct
        try:
            result = self._fs_client().update_profile(
                key, payload, actor=f"odoo-lead-{self.id}"
            )
            self._fs_apply_station_payload(result, origin="crm")
            _logger.info(
                "NC profile synced for lead %s -> %s",
                self.id,
                self.fs_nc_installation_id,
            )
            return True
        except NcLifecycleError as exc:
            self._fs_mark_error(exc)
            _logger.warning(
                "NC profile sync failed for lead %s: %s",
                self.id,
                redact_secrets(str(exc)),
            )
            return False

    def fs_enqueue_push_station_profile(self):
        """Enqueue CRM->NC station profile sync."""
        for lead in self:
            if not lead._fs_installation_key():
                continue
            lead.with_context(fs_skip_nc_enqueue=True).write(
                {
                    "fs_nc_sync_state": "pending",
                    "fs_nc_sync_error": False,
                    "fs_nc_sync_origin": "crm",
                }
            )
            if hasattr(lead, "with_delay"):
                lead.with_delay(
                    priority=12,
                    description=f"NC profile sync for lead {lead.id}",
                    channel="root.filantropia",
                    identity_key=f"fs-profile-{lead.id}",
                ).fs_push_station_profile()
            else:
                lead.fs_push_station_profile()
        return True

    def fs_set_lifecycle(self, lifecycle_state: str) -> bool:
        """Set NC lifecycle explicitly (demotion / correction)."""
        self.ensure_one()
        target = (lifecycle_state or "").strip().lower()
        if target not in ("virtual", "planned", "running"):
            self._fs_mark_error(NcLifecycleError(f"invalid lifecycle_state {target!r}"))
            return False
        key = self._fs_installation_key()
        if not key:
            # No station yet: only Virtual can be created; Planned/Running need promote path.
            if target == "virtual":
                return self.fs_create_virtual_station()
            self._fs_mark_error(
                NcLifecycleError("missing NC station link for set-lifecycle")
            )
            return False
        if self.fs_nc_lifecycle_state == target:
            self.with_context(fs_skip_nc_enqueue=True).write(
                {"fs_nc_sync_state": "ok", "fs_nc_sync_error": False}
            )
            return True
        try:
            result = self._fs_client().set_lifecycle(
                key, target, actor=f"odoo-lead-{self.id}"
            )
            self._fs_apply_station_payload(result, origin="crm")
            _logger.info(
                "NC set-lifecycle %s for lead %s -> %s",
                target,
                self.id,
                self.fs_nc_installation_id,
            )
            return True
        except NcLifecycleError as exc:
            self._fs_mark_error(exc)
            _logger.warning(
                "NC set-lifecycle %s failed for lead %s: %s",
                target,
                self.id,
                redact_secrets(str(exc)),
            )
            return False

    def fs_enqueue_set_lifecycle(self, lifecycle_state: str):
        """Enqueue explicit lifecycle set (demotion)."""
        target = (lifecycle_state or "").strip().lower()
        for lead in self:
            if not lead.fs_is_donation_application and not lead.fs_nc_installation_id:
                continue
            lead.with_context(fs_skip_nc_enqueue=True).write(
                {
                    "fs_nc_sync_state": "pending",
                    "fs_nc_sync_error": False,
                    "fs_nc_sync_origin": "crm",
                }
            )
            if hasattr(lead, "with_delay"):
                lead.with_delay(
                    priority=10,
                    description=f"NC set-lifecycle {target} for lead {lead.id}",
                    channel="root.filantropia",
                    identity_key=f"fs-set-lc-{target}-{lead.id}",
                ).fs_set_lifecycle(target)
            else:
                lead.fs_set_lifecycle(target)
        return True

    def fs_enqueue_create_virtual(self):
        """Enqueue Virtual create (non-blocking)."""
        for lead in self:
            if not lead.fs_is_donation_application and not lead.fs_nc_installation_id:
                continue
            lead.with_context(fs_skip_nc_enqueue=True).write(
                {
                    "fs_nc_sync_state": "pending",
                    "fs_nc_sync_error": False,
                    "fs_nc_sync_origin": "crm",
                }
            )
            if hasattr(lead, "with_delay"):
                lead.with_delay(
                    priority=10,
                    description=f"NC Virtual create for lead {lead.id}",
                    channel="root.filantropia",
                    identity_key=f"fs-virtual-{lead.id}",
                ).fs_create_virtual_station()
            else:
                lead.fs_create_virtual_station()
        return True

    def fs_enqueue_promote_planned(self):
        """Enqueue promote Planned (non-blocking)."""
        for lead in self:
            if not lead.fs_is_donation_application and not lead.fs_nc_installation_id:
                continue
            lead.with_context(fs_skip_nc_enqueue=True).write(
                {
                    "fs_nc_sync_state": "pending",
                    "fs_nc_sync_error": False,
                    "fs_nc_sync_origin": "crm",
                }
            )
            if hasattr(lead, "with_delay"):
                lead.with_delay(
                    priority=10,
                    description=f"NC promote Planned for lead {lead.id}",
                    channel="root.filantropia",
                    identity_key=f"fs-promote-{lead.id}",
                ).fs_promote_planned()
            else:
                lead.fs_promote_planned()
        return True

    def fs_enqueue_mark_installed(self):
        """Enqueue mark-installed / Running (non-blocking)."""
        for lead in self:
            if not lead.fs_is_donation_application and not lead.fs_nc_installation_id:
                continue
            lead.with_context(fs_skip_nc_enqueue=True).write(
                {
                    "fs_nc_sync_state": "pending",
                    "fs_nc_sync_error": False,
                    "fs_nc_sync_origin": "crm",
                }
            )
            if hasattr(lead, "with_delay"):
                lead.with_delay(
                    priority=10,
                    description=f"NC mark installed for lead {lead.id}",
                    channel="root.filantropia",
                    identity_key=f"fs-installed-{lead.id}",
                ).fs_mark_installed()
            else:
                lead.fs_mark_installed()
        return True

    _FS_PROFILE_FIELDS: ClassVar[set[str]] = {
        "name",
        "partner_name",
        "city",
        "website",
        "fs_station_location_label",
        "fs_station_latitude",
        "fs_station_longitude",
        "fs_station_capacity_kwp",
        "fs_station_website",
        "fs_station_short_description",
        "fs_station_grid_price_kwh",
        "fs_station_grid_connection_type",
    }

    def write(self, vals):
        skip = self.env.context.get("fs_skip_nc_enqueue")
        old_stages = {lead.id: lead.stage_id for lead in self}
        res = super().write(vals)
        if skip:
            return res
        # CRM station snapshot edits -> NC profile
        if self._FS_PROFILE_FIELDS.intersection(vals):
            self.fs_enqueue_push_station_profile()
        if "stage_id" not in vals:
            return res
        for lead in self:
            old_stage = old_stages.get(lead.id)
            new_stage = lead.stage_id
            action = lifecycle_action_for_stage_change(
                old_stage.name if old_stage else None,
                new_stage.name if new_stage else None,
                old_is_won=bool(old_stage.is_won) if old_stage else False,
                new_is_won=bool(new_stage.is_won) if new_stage else False,
            )
            # Skip if NC already at target (inbound mirror or manual re-write)
            target = nc_state_for_stage(
                new_stage.name if new_stage else None,
                is_won=bool(new_stage.is_won) if new_stage else False,
            )
            if target and lead.fs_nc_lifecycle_state == target:
                continue
            if action == "ensure_virtual":
                lead.fs_enqueue_create_virtual()
            elif action == "promote_planned":
                lead.fs_enqueue_promote_planned()
            elif action == "mark_installed":
                lead.fs_enqueue_mark_installed()
            elif action == "set_lifecycle_virtual":
                lead.fs_enqueue_set_lifecycle("virtual")
            elif action == "set_lifecycle_planned":
                lead.fs_enqueue_set_lifecycle("planned")
        return res

    @api.model
    def cron_import_all_from_nc(self):
        """Hourly reconcile: ensure every NC station has a CRM lead."""
        return self.env["fs.station.sync"].import_all_from_nc()
