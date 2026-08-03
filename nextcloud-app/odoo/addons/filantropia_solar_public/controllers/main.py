"""Filantropia Solar public website controller with 3-step application funnel."""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.request

from markupsafe import Markup
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# NGO org types eligible for Filantropia Solar
_NGO_ORG_TYPES = {"ong", "ipss", "fundacao", "cooperativa"}

# Panel dimensions and power constants
_PANEL_AREA_M2 = 2.0  # 2 m x 1 m per panel
_PANEL_WATTS = 550  # 550 W per panel


class FilantropiaSolarPublicController(http.Controller):
    def _api_base_url(self) -> str:
        return os.environ.get(
            "FS_API_BASE_URL",
            "http://filantropia-nextcloud/apps/filantropia_solar/api/public/v1",
        )

    def _api_token(self) -> str:
        return os.environ.get("FS_PUBLIC_API_TOKEN", "")

    def _api_headers(self, include_content_type: bool = False) -> dict:
        headers = {"Authorization": f"Bearer {self._api_token()}"}
        if include_content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def _fetch_json(self, endpoint: str, payload: dict | None = None) -> dict:
        url = f"{self._api_base_url()}/{endpoint.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(
            url,
            data=data,
            headers=self._api_headers(include_content_type=payload is not None),
            method="POST" if payload else "GET",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get_public_data(self):
        api_error = None
        stations = []
        dashboard = {}
        try:
            stations_payload = self._fetch_json("stations")
            stations = stations_payload.get("stations", [])
        except Exception as exc:
            stations = []
            api_error = "Não foi possível carregar as estações."
            _logger.warning("Stations fetch failed: %s", exc)

        try:
            dashboard = self._fetch_json("dashboard")
        except Exception as exc:
            dashboard = {"station_count": 0, "total_capacity_kwp": 0, "locations": []}
            api_error = api_error or "Dashboard indisponível."
            _logger.warning("Dashboard fetch failed: %s", exc)

        return stations, dashboard, api_error

    def _as_float(self, value, default=0.0):
        try:
            if value is None or value == "":
                return default
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

    def _compute_panels(self, area_m2: float) -> tuple[int, float]:
        """Calculate how many 2m x 1m panels fit and the resulting DC kWp."""
        area = max(self._as_float(area_m2, 0.0), 0.0)
        count = int(area // _PANEL_AREA_M2)
        count = max(count, 1)
        kwp = count * _PANEL_WATTS / 1000.0
        return count, kwp

    def _parse_estimate_data(self, raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _attach_files(self, lead):
        """Store uploaded form files as ir.attachment records on the lead."""
        Attachment = request.env["ir.attachment"].sudo()
        files = request.httprequest.files
        for _field_name in files:
            uploads = files.getlist(_field_name)
            for upload in uploads:
                if not upload or not upload.filename:
                    continue
                try:
                    Attachment.create(
                        {
                            "name": upload.filename,
                            "datas": base64.b64encode(upload.read()),
                            "res_model": "crm.lead",
                            "res_id": lead.id,
                            "mimetype": upload.mimetype or "application/octet-stream",
                        }
                    )
                except Exception as exc:
                    _logger.warning(
                        "Could not attach file %s to lead %s: %s",
                        upload.filename,
                        lead.id,
                        exc,
                    )

    def _render_page(self, template, **extra):
        stations, dashboard, api_error = self._get_public_data()
        values = {
            "stations": stations,
            "stations_json": Markup(json.dumps(stations)),
            "dashboard": dashboard,
            "api_error": api_error,
            "step": 1,
            "submitted": False,
            "estimate": {},
            "estimate_data": "{}",
            "estimate_savings": "0",
            "estimate_kwp": "0.0",
            "panel_count": "",
            "capacity_kwp": "",
            "available_area": "",
            "location": "",
            "surface_type": "",
            "step1_name": "",
            "step1_email": "",
            "step2_org_name": "",
            "step2_org_type": "",
            "step2_website": "",
            "step3_monthly_spend": "",
            "step3_price_kwh": "",
            "step3_usage_pattern": "",
            "step3_description": "",
            "contact_name": "",
            "contact_email": "",
        }
        values.update(extra)

        # Allow a step-specific estimate error without wiping station fetch errors
        if extra.get("form_error"):
            values["api_error"] = extra["form_error"]

        step = values.get("step", 1)
        if step not in (1, 2, 3, "sme"):
            try:
                step = int(step)
            except (TypeError, ValueError):
                step = 1
        values["step"] = step

        est = values.get("estimate") or {}
        if not isinstance(est, dict):
            est = {}
            values["estimate"] = est

        if not values.get("estimate_data") or values.get("estimate_data") == "{}":
            values["estimate_data"] = json.dumps(est)

        cap = values.get("capacity_kwp")
        try:
            savings_val = float(est.get("annual_savings_eur", 0) or 0)
        except (TypeError, ValueError):
            savings_val = 0.0
        try:
            kwp_val = float(est.get("capacity_kwp") or cap or 0)
        except (TypeError, ValueError):
            kwp_val = 0.0
        values["estimate_savings"] = str(int(savings_val))
        values["estimate_kwp"] = f"{kwp_val:.1f}"

        values["contact_name"] = values.get("contact_name") or values.get("step1_name") or ""
        values["contact_email"] = values.get("contact_email") or values.get("step1_email") or ""

        return request.render(template, values)

    @http.route(
        ["/", "/inicio", "/filantropia-solar"],
        type="http",
        auth="public",
        website=True,
    )
    def home(self, **kwargs):
        return self._render_page("filantropia_solar_public.page_inicio", step=1)

    @http.route(
        "/candidatura/estimativa",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def candidatura_estimativa(self, **post):
        step1_name = (post.get("step1_name") or "").strip()
        step1_email = (post.get("step1_email") or "").strip()
        location = (post.get("location") or "").strip()
        surface_type = (post.get("surface_type") or "").strip()
        available_area = self._as_float(post.get("available_area", "0"))

        panels, kwp = self._compute_panels(available_area)
        estimate: dict = {}
        form_error = None
        try:
            estimate = self._estimate(location, None, None, kwp) or {}
        except Exception as exc:
            form_error = (
                "Não foi possível obter a estimativa automática. "
                "Pode continuar — a equipa valida os números manualmente."
            )
            _logger.warning("Step 1 estimate failed: %s", exc)

        return self._render_page(
            "filantropia_solar_public.page_inicio",
            step=2,
            step1_name=step1_name,
            step1_email=step1_email,
            location=location,
            surface_type=surface_type,
            available_area=str(available_area),
            capacity_kwp=f"{kwp:.2f}",
            panel_count=str(panels),
            estimate=estimate,
            estimate_data=json.dumps(estimate),
            form_error=form_error,
            contact_name=step1_name,
            contact_email=step1_email,
        )

    @http.route(
        "/candidatura/elegibilidade",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def candidatura_elegibilidade(self, **post):
        org_type = (post.get("step2_org_type") or "").strip()
        step1_name = (post.get("step1_name") or "").strip()
        step1_email = (post.get("step1_email") or "").strip()
        location = (post.get("location") or "").strip()
        surface_type = (post.get("surface_type") or "").strip()
        available_area = (post.get("available_area") or "").strip()
        capacity_kwp = (post.get("capacity_kwp") or "").strip()
        panel_count = (post.get("panel_count") or "").strip()
        step2_org_name = (post.get("step2_org_name") or "").strip()
        step2_website = (post.get("step2_website") or "").strip()
        estimate = self._parse_estimate_data(post.get("estimate_data"))

        common = {
            "step1_name": step1_name,
            "step1_email": step1_email,
            "location": location,
            "surface_type": surface_type,
            "available_area": available_area,
            "capacity_kwp": capacity_kwp,
            "panel_count": panel_count,
            "step2_org_name": step2_org_name,
            "step2_org_type": org_type,
            "step2_website": step2_website,
            "estimate": estimate,
            "estimate_data": json.dumps(estimate),
            "contact_name": step1_name,
            "contact_email": step1_email,
        }

        if org_type in _NGO_ORG_TYPES:
            return self._render_page(
                "filantropia_solar_public.page_inicio",
                step=3,
                **common,
            )

        lead = (
            request.env["crm.lead"]
            .sudo()
            .create(
                {
                    "name": f"Filantropia Solar — {step2_org_name or 'SME referral'}",
                    "contact_name": step1_name or False,
                    "email_from": step1_email or False,
                    "partner_name": step2_org_name or False,
                    "description": "\n".join(
                        [
                            "NÃO ELEGÍVEL para Filantropia Solar (SME/for-profit referral)",
                            f"Org type: {org_type}",
                            f"Location: {location}",
                            f"Available area: {available_area} m²",
                            f"Estimated capacity: {capacity_kwp} kWp",
                            "Handed off to WeRa Global.",
                        ]
                    ),
                }
            )
        )
        _logger.info("SME lead created: %s -> WeRa referral", lead.id)
        return self._render_page(
            "filantropia_solar_public.page_inicio",
            step="sme",
            **common,
        )

    @http.route(
        "/candidatura/enviar",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def candidatura_enviar(self, **post):
        step1_name = (post.get("step1_name") or "").strip()
        step1_email = (post.get("step1_email") or "").strip()
        location = (post.get("location") or "").strip()
        surface_type = (post.get("surface_type") or "").strip()
        available_area = (post.get("available_area") or "").strip()
        capacity_kwp = (post.get("capacity_kwp") or "").strip()
        panel_count = (post.get("panel_count") or "").strip()
        step2_org_name = (post.get("step2_org_name") or "").strip()
        step2_org_type = (post.get("step2_org_type") or "").strip()
        step2_website = (post.get("step2_website") or "").strip()
        step3_monthly_spend = (post.get("step3_monthly_spend") or "").strip()
        step3_price_kwh = (post.get("step3_price_kwh") or "").strip()
        step3_usage_pattern = (post.get("step3_usage_pattern") or "").strip()
        step3_description = (post.get("step3_description") or "").strip()
        estimate = self._parse_estimate_data(post.get("estimate_data"))

        description_lines = [
            "Filantropia Solar — Candidatura de doação (funnel 3-passos)",
            "",
            "Contacto:",
            f"- Nome: {step1_name}",
            f"- Email: {step1_email}",
            "",
            "Estimativa:",
            f"- Localização: {location}",
            f"- Superfície: {surface_type}",
            f"- Área disponível: {available_area} m²",
            f"- Painéis estimados: {panel_count}",
            f"- Capacidade estimada: {capacity_kwp} kWp",
            f"- Poupança anual estimada (EUR): {estimate.get('annual_savings_eur', 'n/d')}",
            "",
            "Organização:",
            f"- Nome: {step2_org_name}",
            f"- Tipo: {step2_org_type}",
            f"- Site/descrição: {step2_website}",
            "",
            "Padrão de consumo:",
            f"- Gasto mensal: {step3_monthly_spend} EUR",
            f"- Preço/kWh: {step3_price_kwh}",
            f"- Padrão: {step3_usage_pattern}",
            f"- Notas: {step3_description}",
        ]

        lead = (
            request.env["crm.lead"]
            .sudo()
            .create(
                {
                    "name": f"Filantropia Solar Candidatura — {step2_org_name or 'ONG'}",
                    "contact_name": step1_name or "Contacto desconhecido",
                    "email_from": step1_email or False,
                    "partner_name": step2_org_name or False,
                    "description": "\n".join(description_lines),
                }
            )
        )
        self._attach_files(lead)
        _logger.info("Donation application lead created: %s", lead.id)

        return self._render_page(
            "filantropia_solar_public.page_inicio",
            step=3,
            submitted=True,
            step1_name=step1_name,
            step1_email=step1_email,
            location=location,
            surface_type=surface_type,
            available_area=available_area,
            capacity_kwp=capacity_kwp,
            panel_count=panel_count,
            step2_org_name=step2_org_name,
            step2_org_type=step2_org_type,
            step2_website=step2_website,
            step3_monthly_spend=step3_monthly_spend,
            step3_price_kwh=step3_price_kwh,
            step3_usage_pattern=step3_usage_pattern,
            step3_description=step3_description,
            estimate=estimate,
            estimate_data=json.dumps(estimate),
            contact_name=step1_name,
            contact_email=step1_email,
        )
