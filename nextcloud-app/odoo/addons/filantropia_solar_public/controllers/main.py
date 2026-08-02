"""Filantropia Solar public website controller with 3-step application funnel."""

import base64
import json
import logging
import os
import urllib.error
import urllib.request

from markupsafe import Markup
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# NGO org types eligible for Filantropia Solar
_NGO_ORG_TYPES = {"ong", "ipss", "fundacao", "cooperativa"}

# Panel dimensions and power constants
_PANEL_AREA_M2 = 2.0  # 2 m x 1 m per panel
_PANEL_WATTS = 550     # 550 W per panel


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
            api_error = f"Não foi possível carregar as estações."
            _logger.warning("Stations fetch failed: %s", exc)

        try:
            dashboard = self._fetch_json("dashboard")
        except Exception as exc:
            dashboard = {"station_count": 0, "total_capacity_kwp": 0, "locations": []}
            api_error = api_error or "Dashboard indisponível."
            _logger.warning("Dashboard fetch failed: %s", exc)

        return stations, dashboard, api_error

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

    def _compute_panels(self, area_m2: float) -> tuple[int, float]:
        """Calculate how many 2m x 1m panels fit and the resulting DC kWp."""
        count = int(area_m2 // _PANEL_AREA_M2)
        if count < 1:
            count = 1
        kwp = count * _PANEL_WATTS / 1000.0
        return count, kwp

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
                    Attachment.create({
                        "name": upload.filename,
                        "datas": base64.b64encode(upload.read()),
                        "res_model": "crm.lead",
                        "res_id": lead.id,
                        "mimetype": upload.mimetype,
                    })
                except Exception as exc:
                    _logger.warning(
                        "Could not attach file %s to lead %s: %s",
                        upload.filename, lead.id, exc,
                    )

    def _render_page(self, template, **extra):
        stations, dashboard, api_error = self._get_public_data()
        values = {
            "stations": stations,
            "stations_json": Markup(json.dumps(stations)),
            "dashboard": dashboard,
            "api_error": api_error,
            "step": 0,
            "submitted": False,
        }
        values.update(extra)
        return request.render(template, values)

    # ------------------------------------------------------------------
    # Home page
    # ------------------------------------------------------------------
    @http.route(["/inicio", "/filantropia-solar"], type="http", auth="public", website=True)
    def home(self, **kwargs):
        return self._render_page("filantropia_solar_public.page_home")

    # ------------------------------------------------------------------
    # Static pages
    # ------------------------------------------------------------------
    @http.route("/como-funciona", type="http", auth="public", website=True)
    def como_funciona(self, **kwargs):
        return request.render("filantropia_solar_public.page_como_funciona")

    @http.route("/casos-de-sucesso", type="http", auth="public", website=True)
    def casos_de_sucesso(self, **kwargs):
        return request.render("filantropia_solar_public.page_casos")

    @http.route("/faq", type="http", auth="public", website=True)
    def faq(self, **kwargs):
        return request.render("filantropia_solar_public.page_faq")

    @http.route("/sobre", type="http", auth="public", website=True)
    def sobre(self, **kwargs):
        return request.render("filantropia_solar_public.page_sobre")

    @http.route("/contacto", type="http", auth="public", website=True)
    def contacto(self, **kwargs):
        return request.render("filantropia_solar_public.page_contacto")

    # ------------------------------------------------------------------
    # 3-Step funnel: /candidatura
    # ------------------------------------------------------------------
    @http.route("/candidatura", type="http", auth="public", website=True, sitemap=True)
    def candidatura(self, **kwargs):
        return self._render_page(
            "filantropia_solar_public.page_candidatura",
            step=1,
        )

    # Step 1: Estimate savings
    @http.route("/candidatura/estimativa", type="http", auth="public", website=True, methods=["POST"])
    def candidatura_estimativa(self, **post):
        step1_name = post.get("step1_name", "").strip()
        step1_email = post.get("step1_email", "").strip()
        location = post.get("location", "").strip()
        surface_type = post.get("surface_type", "").strip()
        available_area = self._as_float(post.get("available_area", "0"))

        panels, kwp = self._compute_panels(available_area)
        estimate = None
        try:
            estimate = self._estimate(location, None, None, kwp)
        except Exception as exc:
            _logger.warning("Step 1 estimate failed: %s", exc)

        return self._render_page(
            "filantropia_solar_public.page_candidatura",
            step=2,
            step1_name=step1_name,
            step1_email=step1_email,
            location=location,
            surface_type=surface_type,
            available_area=str(available_area),
            capacity_kwp=str(kwp),
            panel_count=str(panels),
            estimate=estimate or {},
            contact_name=step1_name,
            contact_email=step1_email,
        )

    # Step 2: Eligibility check
    @http.route("/candidatura/elegibilidade", type="http", auth="public", website=True, methods=["POST"])
    def candidatura_elegibilidade(self, **post):
        org_type = post.get("step2_org_type", "").strip()

        if org_type in _NGO_ORG_TYPES:
            return self._render_page(
                "filantropia_solar_public.page_candidatura",
                step=3,
                step1_name=post.get("step1_name", "").strip(),
                step1_email=post.get("step1_email", "").strip(),
                location=post.get("location", "").strip(),
                available_area=post.get("available_area", "").strip(),
                capacity_kwp=post.get("capacity_kwp", "").strip(),
                step2_org_name=post.get("step2_org_name", "").strip(),
                step2_org_type=org_type,
                step2_website=post.get("step2_website", "").strip(),
                estimate=json.loads(post.get("estimate_data", "{}")),
                contact_name=post.get("step1_name", "").strip(),
                contact_email=post.get("step1_email", "").strip(),
            )
        else:
            # SME / for-profit → referral branch, lead preserved
            lead = request.env["crm.lead"].sudo().create({
                "name": f"Filantropia Solar — {post.get('step2_org_name', '').strip() or 'SME referral'}",
                "contact_name": post.get("step1_name", "").strip(),
                "email_from": post.get("step1_email", "").strip() or False,
                "partner_name": post.get("step2_org_name", "").strip() or False,
                "description": "\n".join([
                    "NÃO ELEGÍVEL para Filantropia Solar (SME/for-profit referral)",
                    f"Org type: {org_type}",
                    f"Location: {post.get('location', '').strip()}",
                    f"Available area: {post.get('available_area', '').strip()} m²",
                    "Handed off to WeRa Global.",
                ]),
            })
            _logger.info("SME lead created: %s -> WeRa referral", lead.id)
            return self._render_page(
                "filantropia_solar_public.page_candidatura",
                step="sme",
                step1_name=post.get("step1_name", "").strip(),
                step1_email=post.get("step1_email", "").strip(),
                location=post.get("location", "").strip(),
            )

    # Step 3: Submit donation application
    @http.route("/candidatura/enviar", type="http", auth="public", website=True, methods=["POST"])
    def candidatura_enviar(self, **post):
        description_lines = [
            "Filantropia Solar — Candidatura de doação (funnel 3-passos)",
            "",
            "Contacto:",
            f"- Nome: {post.get('step1_name', '').strip()}",
            f"- Email: {post.get('step1_email', '').strip()}",
            "",
            "Estimativa:",
            f"- Localização: {post.get('location', '').strip()}",
            f"- Área disponível: {post.get('available_area', '').strip()} m²",
            f"- Capacidade estimada: {post.get('capacity_kwp', '').strip()} kWp",
            "",
            "Organização:",
            f"- Nome: {post.get('step2_org_name', '').strip()}",
            f"- Tipo: {post.get('step2_org_type', '').strip()}",
            f"- Site/descrição: {post.get('step2_website', '').strip()}",
            "",
            "Padrão de consumo:",
            f"- Gasto mensal: {post.get('step3_monthly_spend', '').strip()} EUR",
            f"- Preço/kWh: {post.get('step3_price_kwh', '').strip()}",
            f"- Padrão: {post.get('step3_usage_pattern', '').strip()}",
            f"- Notas: {post.get('step3_description', '').strip()}",
        ]

        lead = request.env["crm.lead"].sudo().create({
            "name": f"Filantropia Solar Candidatura — {post.get('step2_org_name', '').strip() or 'ONG'}",
            "contact_name": post.get("step1_name", "").strip() or "Contacto desconhecido",
            "email_from": post.get("step1_email", "").strip() or False,
            "partner_name": post.get("step2_org_name", "").strip() or False,
            "description": "\n".join(description_lines),
        })
        self._attach_files(lead)
        _logger.info("Donation application lead created: %s", lead.id)

        return self._render_page(
            "filantropia_solar_public.page_candidatura",
            step=3,
            submitted=True,
            step1_name=post.get("step1_name", "").strip(),
            step1_email=post.get("step1_email", "").strip(),
            location=post.get("location", "").strip(),
            available_area=post.get("available_area", "").strip(),
            capacity_kwp=post.get("capacity_kwp", "").strip(),
            step2_org_name=post.get("step2_org_name", "").strip(),
            step2_org_type=post.get("step2_org_type", "").strip(),
            step2_website=post.get("step2_website", "").strip(),
        )
