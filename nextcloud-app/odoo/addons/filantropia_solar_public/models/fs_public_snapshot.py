"""Persistent, public-safe snapshot for the Odoo website map and KPIs."""

from __future__ import annotations

import logging

from odoo import api, fields, models

from ..controllers.main import FilantropiaSolarPublicController

_logger = logging.getLogger(__name__)
_PUBLIC_SNAPSHOT_KEY = "public"


class FsPublicSnapshot(models.Model):
    _name = "fs.public.snapshot"
    _description = "FilantropiaSolar public website snapshot"
    _snapshot_key_unique = models.Constraint(
        "UNIQUE (snapshot_key)",
        "Only one snapshot may exist for each public data key.",
    )

    snapshot_key = fields.Char(
        required=True,
        default=_PUBLIC_SNAPSHOT_KEY,
        index=True,
        copy=False,
    )
    stations_data = fields.Json(
        string="Public stations",
        required=True,
        default=list,
        copy=False,
    )
    dashboard_data = fields.Json(
        string="Public dashboard",
        required=True,
        default=dict,
        copy=False,
    )
    refreshed_at = fields.Datetime(
        string="Last complete refresh (UTC)",
        required=True,
        readonly=True,
        copy=False,
    )

    @api.model
    def _get_current(self):
        return self.sudo().search(
            [("snapshot_key", "=", _PUBLIC_SNAPSHOT_KEY)],
            limit=1,
        )

    @api.model
    def cron_refresh_public_snapshot(self):
        """Replace the snapshot only after both public API responses validate."""
        controller = FilantropiaSolarPublicController()
        try:
            stations_payload = controller._fetch_json("stations")
            dashboard_payload = controller._fetch_json("dashboard")
            if (
                not isinstance(stations_payload, dict)
                or stations_payload.get("success") is False
                or not isinstance(stations_payload.get("stations"), list)
                or any(
                    not isinstance(station, dict)
                    for station in stations_payload["stations"]
                )
            ):
                raise ValueError("Invalid stations response")
            if (
                not isinstance(dashboard_payload, dict)
                or dashboard_payload.get("success") is False
            ):
                raise ValueError("Invalid dashboard response")
            dashboard, stations = controller._enrich_metrics(
                stations_payload["stations"],
                dashboard_payload,
            )
        except Exception as exc:
            _logger.warning(
                "Public website snapshot refresh failed; retaining last complete "
                "snapshot: %s",
                exc,
            )
            return False

        values = {
            "stations_data": stations,
            "dashboard_data": dashboard,
            "refreshed_at": fields.Datetime.now(),
        }
        snapshot = self.sudo()._get_current()
        if snapshot:
            snapshot.write(values)
        else:
            self.sudo().create(
                {
                    "snapshot_key": _PUBLIC_SNAPSHOT_KEY,
                    **values,
                }
            )
        _logger.info(
            "Public website snapshot refreshed: stations=%s",
            len(stations),
        )
        return True
