"""CRM lead extensions: NC lifecycle sync fields + actions (mirror CRM <-> NC)."""

from __future__ import annotations

import contextlib
import logging

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
        if station.get("website") and not self.fs_station_website:
            vals["fs_station_website"] = station["website"]
        if station.get("short_description") and not self.fs_station_short_description:
            vals["fs_station_short_description"] = station["short_description"]
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

        payload = {
            "odoo_lead_id": int(self.id),
            "name": self.partner_name or self.name or f"Lead {self.id}",
            "latitude": float(self.fs_station_latitude or 0.0),
            "longitude": float(self.fs_station_longitude or 0.0),
            "capacity_kwp": capacity,
            "location_label": self.fs_station_location_label or self.city or "Portugal",
            "organization_name": self.partner_name or "",
        }
        if self.fs_station_grid_price_kwh:
            payload["grid_price_kwh"] = float(self.fs_station_grid_price_kwh)
        website = (self.fs_station_website or "").strip()
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
        if self.fs_nc_lifecycle_state != "planned":
            if not self.fs_promote_planned():
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

    def write(self, vals):
        skip = self.env.context.get("fs_skip_nc_enqueue")
        old_stages = {lead.id: lead.stage_id for lead in self}
        res = super().write(vals)
        if skip or "stage_id" not in vals:
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
        return res

    @api.model
    def cron_import_all_from_nc(self):
        """Hourly reconcile: ensure every NC station has a CRM lead."""
        return self.env["fs.station.sync"].import_all_from_nc()
