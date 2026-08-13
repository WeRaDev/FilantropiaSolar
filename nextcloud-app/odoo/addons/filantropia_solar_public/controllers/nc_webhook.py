"""Inbound NC lifecycle webhook / pull endpoint for CRM mirror."""

from __future__ import annotations

import json
import logging
import os

from odoo import http
from odoo.http import request

from ..services.nc_lifecycle_client import redact_secrets

_logger = logging.getLogger(__name__)


class FsNcWebhookController(http.Controller):
    def _authorized(self) -> bool:
        expected = (
            os.environ.get("FS_LIFECYCLE_API_TOKEN")
            or os.environ.get("FS_PUBLIC_API_TOKEN")
            or ""
        ).strip()
        if not expected:
            # also allow Odoo system param
            expected = (
                request.env["ir.config_parameter"]
                .sudo()
                .get_param("filantropia_solar_public.lifecycle_webhook_token")
                or ""
            ).strip()
        auth = request.httprequest.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            return bool(expected) and token == expected
        return False

    @http.route(
        "/filantropia/nc/lifecycle",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def lifecycle_event(self, **payload):
        if not self._authorized():
            return {"success": False, "error": "unauthorized"}
        station = payload.get("station") if isinstance(payload, dict) else None
        if not station and isinstance(payload, dict):
            # raw body style
            station = payload
        if not isinstance(station, dict) or not (
            station.get("installation_id") or station.get("odoo_lead_id")
        ):
            return {"success": False, "error": "station payload required"}
        try:
            lead = (
                request.env["fs.station.sync"]
                .sudo()
                .upsert_from_nc_station(station, origin="nc")
            )
            return {
                "success": True,
                "lead_id": lead.id,
                "stage": lead.stage_id.name if lead.stage_id else None,
            }
        except Exception as exc:
            _logger.exception("NC webhook failed: %s", redact_secrets(str(exc)))
            return {"success": False, "error": redact_secrets(str(exc))}

    @http.route(
        "/filantropia/nc/lifecycle/http",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def lifecycle_event_http(self, **kwargs):
        if not self._authorized():
            return request.make_json_response(
                {"success": False, "error": "unauthorized"}, status=401
            )
        try:
            raw = request.httprequest.get_data(as_text=True) or "{}"
            data = json.loads(raw)
        except Exception:
            data = kwargs or {}
        station = data.get("station") if isinstance(data, dict) else None
        if not isinstance(station, dict):
            station = data if isinstance(data, dict) else {}
        try:
            lead = (
                request.env["fs.station.sync"]
                .sudo()
                .upsert_from_nc_station(station, origin="nc")
            )
            return request.make_json_response(
                {
                    "success": True,
                    "lead_id": lead.id,
                    "stage": lead.stage_id.name if lead.stage_id else None,
                }
            )
        except Exception as exc:
            _logger.exception("NC http webhook failed: %s", redact_secrets(str(exc)))
            return request.make_json_response(
                {"success": False, "error": redact_secrets(str(exc))}, status=500
            )
