"""Transient admin dashboard KPIs from NC public API."""

from __future__ import annotations

import contextlib
import logging

from odoo import api, fields, models

from ..services.nc_public_client import NcPublicClient, nc_admin_url

_logger = logging.getLogger(__name__)


class FsDashboard(models.TransientModel):
    _name = "fs.dashboard"
    _description = "Filantropia NC dashboard"

    station_count = fields.Integer(readonly=True)
    total_capacity_kwp = fields.Float(readonly=True, digits=(12, 3))
    total_savings_eur = fields.Float(readonly=True, digits=(14, 2))
    planned_count = fields.Integer(readonly=True)
    existing_count = fields.Integer(readonly=True)
    nc_admin_url = fields.Char(readonly=True)
    last_error = fields.Text(readonly=True)
    notes = fields.Text(readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        client = NcPublicClient()
        err = ""
        stations = []
        dash = {}
        try:
            stations = client.stations()
            dash = client.dashboard() or {}
        except Exception as exc:
            err = str(exc)
            _logger.warning("dashboard fetch failed: %s", exc)
        planned = existing = 0
        cap = 0.0
        savings = 0.0
        for s in stations:
            if not isinstance(s, dict):
                continue
            cat = (s.get("public_category") or s.get("lifecycle_state") or "").lower()
            if cat in ("planned",):
                planned += 1
            elif cat in ("existing", "running"):
                existing += 1
            try:
                cap += float(s.get("capacity_kwp") or 0)
            except (TypeError, ValueError):
                pass
            for k in (
                "money_saved_eur",
                "total_savings_eur",
                "indicative_savings_eur",
            ):
                if s.get(k) is not None:
                    try:
                        savings += float(s.get(k) or 0)
                        break
                    except (TypeError, ValueError):
                        pass
        # prefer dashboard totals when present
        if isinstance(dash, dict):
            for k, dest in (
                ("total_capacity_kwp", "cap"),
                ("capacity_kwp", "cap"),
                ("total_savings_eur", "savings"),
                ("money_saved_eur", "savings"),
            ):
                if dash.get(k) is not None:
                    try:
                        if dest == "cap":
                            cap = float(dash[k])
                        else:
                            savings = float(dash[k])
                    except (TypeError, ValueError):
                        pass
            if dash.get("station_count") is not None:
                try:
                    res["station_count"] = int(dash["station_count"])
                except (TypeError, ValueError):
                    pass
        res.update(
            {
                "station_count": res.get("station_count", len(stations)),
                "total_capacity_kwp": cap,
                "total_savings_eur": savings,
                "planned_count": planned,
                "existing_count": existing,
                "nc_admin_url": nc_admin_url(),
                "last_error": err or False,
                "notes": (
                    "KPIs from Nextcloud public API. Open NC for full ops admin. "
                    "CRM stages mirror lifecycle (ADR 0006)."
                ),
            }
        )
        return res

    def action_open_nextcloud(self):
        self.ensure_one()
        url = self.nc_admin_url or nc_admin_url()
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_refresh(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "fs.dashboard",
            "view_mode": "form",
            "target": "current",
            "context": {"form_view_initial_mode": "readonly"},
        }

    def action_import_nc_stations(self):
        result = self.env["fs.station.sync"].import_all_from_nc()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "NC import",
                "message": str(result),
                "sticky": False,
                "type": "success" if result.get("ok") else "danger",
            },
        }
