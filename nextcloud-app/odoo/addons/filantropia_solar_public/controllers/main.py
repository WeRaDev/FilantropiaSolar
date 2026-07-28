import json
import logging
import os
import urllib.error
import urllib.request

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class FilantropiaSolarPublicController(http.Controller):
    """Public website routes that consume the Nextcloud token-auth API."""

    def _api_base_url(self) -> str:
        return os.getenv(
            "FS_API_BASE_URL",
            "http://filantropia-nextcloud/apps/filantropia_solar/api/public/v1",
        ).rstrip("/")

    def _api_token(self) -> str:
        return os.getenv("FS_PUBLIC_API_TOKEN", "").strip()

    def _api_headers(self, include_content_type: bool = False) -> dict:
        headers = {"Accept": "application/json"}
        token = self._api_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if include_content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def _fetch_json(self, endpoint: str, payload: dict | None = None) -> dict:
        url = f"{self._api_base_url()}/{endpoint.lstrip('/')}"
        body = None
        method = "GET"
        headers = self._api_headers(include_content_type=payload is not None)
        if payload is not None:
            method = "POST"
            body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}

    def _get_public_data(self) -> tuple[list, dict, str | None]:
        stations = []
        dashboard = {}
        api_error = None
        try:
            stations_response = self._fetch_json("stations")
            stations = stations_response.get("stations", [])
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
        ) as exc:
            _logger.warning(
                "Unable to fetch stations from Nextcloud public API: %s", exc
            )
            api_error = "Stations are temporarily unavailable."
        try:
            dashboard = self._fetch_json("dashboard")
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
        ) as exc:
            _logger.warning(
                "Unable to fetch dashboard from Nextcloud public API: %s", exc
            )
            if not api_error:
                api_error = "Dashboard metrics are temporarily unavailable."
        return stations, dashboard, api_error

    @staticmethod
    def _as_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _estimate(self, location, latitude, longitude, capacity_kwp):
        payload = {
            "location": location or None,
            "latitude": self._as_float(latitude, None),
            "longitude": self._as_float(longitude, None),
            "capacity_kwp": self._as_float(capacity_kwp),
        }
        if payload["latitude"] is None or payload["longitude"] is None:
            payload.pop("latitude", None)
            payload.pop("longitude", None)
        return self._fetch_json("estimate", payload=payload).get("estimate", {})

    def _render_dashboard(self, **extra_values):
        stations, dashboard, api_error = self._get_public_data()
        values = {
            "stations": stations,
            "stations_json": json.dumps(stations),
            "dashboard": dashboard,
            "api_error": api_error,
            "estimate": None,
            "estimate_error": None,
            "submitted": False,
            "quote_name": "",
            "quote_email": "",
            "quote_org": "",
            "quote_message": "",
            "location": "",
            "latitude": "",
            "longitude": "",
            "capacity_kwp": "",
        }
        values.update(extra_values)
        return request.render("filantropia_solar_public.page_dashboard", values)

    @http.route(
        "/filantropia-solar",
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def public_dashboard(self, **kwargs):
        return self._render_dashboard()

    @http.route(
        "/filantropia-solar/estimate",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
    )
    def estimate_station(self, **post):
        location = post.get("location", "").strip()
        latitude = post.get("latitude", "").strip()
        longitude = post.get("longitude", "").strip()
        capacity_kwp = post.get("capacity_kwp", "").strip()
        estimate = None
        estimate_error = None
        try:
            estimate = self._estimate(location, latitude, longitude, capacity_kwp)
            if not estimate:
                estimate_error = "Estimate service returned an empty response."
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
        ) as exc:
            _logger.warning("Estimate call failed: %s", exc)
            estimate_error = (
                "Could not calculate estimate right now. Please try again shortly."
            )
        return self._render_dashboard(
            estimate=estimate,
            estimate_error=estimate_error,
            location=location,
            latitude=latitude,
            longitude=longitude,
            capacity_kwp=capacity_kwp,
        )

    @http.route(
        "/filantropia-solar/quote",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
    )
    def request_quote(self, **post):
        quote_name = post.get("quote_name", "").strip()
        quote_email = post.get("quote_email", "").strip()
        quote_org = post.get("quote_org", "").strip()
        quote_message = post.get("quote_message", "").strip()
        location = post.get("location", "").strip()
        latitude = post.get("latitude", "").strip()
        longitude = post.get("longitude", "").strip()
        capacity_kwp = post.get("capacity_kwp", "").strip()

        estimate = None
        estimate_error = None
        try:
            estimate = self._estimate(location, latitude, longitude, capacity_kwp)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
        ) as exc:
            _logger.warning("Estimate call failed during quote creation: %s", exc)
            estimate_error = "Could not retrieve estimate while creating quote."

        title_parts = ["FilantropiaSolar Quote Request"]
        if quote_org:
            title_parts.append(quote_org)
        elif quote_name:
            title_parts.append(quote_name)
        lead_name = " - ".join(title_parts)

        description_lines = [
            "FilantropiaSolar public website quote request",
            "",
            "Virtual station inputs:",
            f"- Location: {location or 'n/a'}",
            f"- Latitude: {latitude or 'n/a'}",
            f"- Longitude: {longitude or 'n/a'}",
            f"- Capacity (kWp): {capacity_kwp or 'n/a'}",
            "",
            "Estimate result:",
        ]
        if estimate:
            description_lines.extend(
                [
                    f"- Annual production (kWh): {estimate.get('annual_production_kwh', 'n/a')}",
                    f"- Annual savings (EUR): {estimate.get('annual_savings_eur', 'n/a')}",
                    f"- Specific energy (kWh/kWp): {estimate.get('specific_energy_kwh_kwp', 'n/a')}",
                    f"- Method: {estimate.get('method', 'n/a')}",
                ]
            )
        else:
            description_lines.append(
                f"- Estimate unavailable: {estimate_error or 'unknown'}"
            )
        description_lines.extend(["", "Requester message:", quote_message or "n/a"])

        request.env["crm.lead"].sudo().create(
            {
                "name": lead_name,
                "contact_name": quote_name or "Unknown contact",
                "email_from": quote_email or False,
                "partner_name": quote_org or False,
                "description": "\n".join(description_lines),
            }
        )

        return self._render_dashboard(
            submitted=True,
            estimate=estimate,
            estimate_error=estimate_error,
            quote_name=quote_name,
            quote_email=quote_email,
            quote_org=quote_org,
            quote_message=quote_message,
            location=location,
            latitude=latitude,
            longitude=longitude,
            capacity_kwp=capacity_kwp,
        )
