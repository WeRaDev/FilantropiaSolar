"""Filantropia Solar public website: content home + multi-step candidatura + contact."""

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


# Curated short station blurbs (PT). Keys matched against name/location (casefold).
_STATION_INFO_PT = {
    "braga": (
        "Instalação prioritária em abrigo de animais na região de Braga. "
        "Referência da rede Filantropia Solar para impacto social direto."
    ),
    "tavira": (
        "Unidade no Algarve associada a proteção animal. "
        "Exemplo de redução de custos operacionais com solar doado."
    ),
    "lisbon": (
        "Instalação na área metropolitana de Lisboa. "
        "Apoia organizações com consumo diurno elevado."
    ),
    "lisboa": (
        "Instalação na área metropolitana de Lisboa. "
        "Apoia organizações com consumo diurno elevado."
    ),
    "faro": (
        "Estação no Algarve. Boa irradiação solar e perfil típico de consumo institucional."
    ),
    "setubal": (
        "Instalação na península de Setúbal, integrada na rede de monitorização Filantropia Solar."
    ),
    "setúbal": (
        "Instalação na península de Setúbal, integrada na rede de monitorização Filantropia Solar."
    ),
    "loule": (
        "Unidade no interior algarvio (Loulé), parte do conjunto de estações de referência."
    ),
    "loulé": (
        "Unidade no interior algarvio (Loulé), parte do conjunto de estações de referência."
    ),
}

# Panel dimensions and power constants
_PANEL_AREA_M2 = 2.0  # 2 m x 1 m per panel
_PANEL_WATTS = 550  # 550 W per panel

# Interim display constants until Nextcloud exposes aggregate savings
# (admin-editable EUR/kWh is a Nextcloud-app follow-up per Feedback).
_DISPLAY_EUR_PER_KWH = 0.15
_DISPLAY_SPECIFIC_YIELD_KWH_PER_KWP = 1400.0  # Portugal-indicative

# Progress bar percentages for the candidatura funnel
_STEP_PROGRESS = {
    1: 10,
    2: 40,
    3: 70,
    4: 100,
    "sme": 40,
}

_MAX_BILL_BYTES = 5 * 1024 * 1024
_LAT_MIN, _LAT_MAX = -90.0, 90.0
_LNG_MIN, _LNG_MAX = -180.0, 180.0
_MAX_BILL_FILES = 5
_ALLOWED_BILL_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_BILL_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}
# Simple per-IP rate limit for public POSTs (in-process; demo-grade)
_RATE_LIMIT_WINDOW_SEC = 600
_RATE_LIMIT_MAX_POSTS = 20
_rate_buckets: dict[str, list[float]] = {}

_CITY_OPTIONS = [
    "Lisboa",
    "Porto",
    "Braga",
    "Faro",
    "Setúbal",
    "Coimbra",
    "Aveiro",
    "Évora",
    "Funchal",
    "Ponta Delgada",
]


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

    def _enrich_metrics(self, stations: list, dashboard: dict) -> dict:
        """Add indicative total money saved until Nextcloud supplies aggregates."""
        dash = dict(dashboard or {})
        station_count = int(dash.get("station_count") or len(stations) or 0)
        capacity = self._as_float(dash.get("total_capacity_kwp"), 0.0)
        locations = dash.get("locations") or []
        if not locations and stations:
            locations = sorted(
                {
                    (s.get("location") or "").strip()
                    for s in stations
                    if (s.get("location") or "").strip()
                }
            )
        # Prefer API field if present later; else indicative estimate
        total_saved = dash.get("total_money_saved_eur")
        if total_saved is None:
            annual_kwh = capacity * _DISPLAY_SPECIFIC_YIELD_KWH_PER_KWP
            total_saved = annual_kwh * _DISPLAY_EUR_PER_KWH
            dash["savings_is_indicative"] = True
        else:
            dash["savings_is_indicative"] = False
        dash["station_count"] = station_count
        dash["total_capacity_kwp"] = capacity
        dash["locations"] = locations
        dash["location_count"] = len(locations)
        dash["total_money_saved_eur"] = float(total_saved or 0)
        dash["total_money_saved_display"] = f"{int(float(total_saved or 0)):,}".replace(
            ",", " "
        )
        # Per-station indicative savings + short info blurb for list/map popups
        enriched = []
        for s in stations or []:
            row = dict(s)
            cap = self._as_float(row.get("capacity_kwp"), 0.0)
            # Prefer NC series-backed savings; else indicative annual estimate
            saved = row.get("money_saved_eur")
            if saved is None:
                saved = row.get("total_savings_eur")
            indicative = bool(row.get("savings_is_indicative"))
            if saved is None:
                saved = cap * _DISPLAY_SPECIFIC_YIELD_KWH_PER_KWP * _DISPLAY_EUR_PER_KWH
                indicative = True
            elif (
                row.get("has_series_data") is False
                and row.get("savings_is_indicative") is None
            ):
                indicative = True
            row["money_saved_eur"] = float(saved or 0)
            row["money_saved_display"] = f"{int(float(saved or 0)):,}".replace(",", " ")
            row["savings_is_indicative"] = indicative
            website = (row.get("website") or "").strip()
            if website and not website.lower().startswith(("http://", "https://")):
                row["website_href"] = "https://" + website
            else:
                row["website_href"] = website or None
            row["website"] = website or None
            # Prefer NC short_description; else curated blurb; else generic text
            info = (
                row.get("info")
                or row.get("short_description")
                or row.get("description")
                or ""
            ).strip()
            if not info:
                loc = (row.get("location") or "").strip()
                name = (row.get("name") or "").strip()
                blob = f"{name} {loc}".casefold()
                for key, text in _STATION_INFO_PT.items():
                    if key in blob:
                        info = text
                        break
                if not info:
                    loc_disp = loc or "Portugal"
                    name_disp = name or "Instalação"
                    info = (
                        f"{name_disp} em {loc_disp}: instalação da rede Filantropia Solar "
                        f"({cap:g} kWp)."
                    )
            row["info"] = info
            row["short_description"] = info
            enriched.append(row)
        return dash, enriched

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

        dashboard, stations = self._enrich_metrics(stations, dashboard)
        return stations, dashboard, api_error

    def _success_stories(self, limit: int = 3) -> list[dict]:
        """Return published success-story blog posts for homepage teasers."""
        stories: list[dict] = []
        try:
            # Respect current website language for translated post fields
            lang = (
                request.env.context.get("lang")
                or getattr(request, "lang", None)
                or (request.website.default_lang_id.code if request.website else None)
                or "pt_PT"
            )
            BlogPost = request.env["blog.post"].sudo().with_context(lang=lang)
            blog = request.env.ref(
                "filantropia_solar_public.blog_casos_sucesso",
                raise_if_not_found=False,
            )
            domain = [("is_published", "=", True)]
            if blog:
                domain = [*domain, ("blog_id", "=", blog.id)]
            else:
                # fallback: posts whose blog name matches
                Blog = request.env["blog.blog"].sudo()
                b = Blog.search(
                    [
                        "|",
                        ("name", "ilike", "Casos"),
                        ("name", "ilike", "Success"),
                    ],
                    limit=1,
                )
                if b:
                    domain = [*domain, ("blog_id", "=", b.id)]
            posts = BlogPost.search(domain, order="id asc", limit=max(limit, 10))

            # Animal-shelter-first editorial order
            def _story_rank(p):
                n = (p.name or "").casefold()
                if "abrigo" in n or "shelter" in n or "animal" in n:
                    return (0, p.id)
                if "tavira" in n:
                    return (1, p.id)
                return (2, p.id)

            ranked = sorted(posts, key=_story_rank)
            posts = posts.browse([p.id for p in ranked[:limit]])
            for post in posts:
                teaser = ""
                if "teaser_manual" in post._fields and post.teaser_manual:
                    teaser = post.teaser_manual
                elif "teaser" in post._fields and post.teaser:
                    teaser = post.teaser
                elif post.content:
                    # strip tags lightly without importing html
                    raw = post.content or ""
                    parts = []
                    in_tag = False
                    for ch in raw:
                        if ch == "<":
                            in_tag = True
                            continue
                        if ch == ">":
                            in_tag = False
                            parts.append(" ")
                            continue
                        if not in_tag:
                            parts.append(ch)
                    teaser = "".join(parts)
                    teaser = " ".join(teaser.split())[:220]
                url = (
                    post.website_url
                    if "website_url" in post._fields
                    else f"/blog/{post.id}"
                )
                stories.append(
                    {
                        "id": post.id,
                        "name": post.name,
                        "subtitle": post.subtitle or "",
                        "teaser": teaser,
                        "url": url,
                    }
                )
        except Exception as exc:
            _logger.warning("Success stories fetch failed: %s", exc)
        return stories

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

    def _client_ip(self) -> str:
        req = request.httprequest
        forwarded = (req.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        return forwarded or (req.remote_addr or "unknown")

    def _rate_limit_ok(self, bucket: str) -> bool:
        """Return False if this client exceeded demo rate limits."""
        import time

        ip = self._client_ip()
        key = f"{bucket}:{ip}"
        now = time.time()
        cutoff = now - _RATE_LIMIT_WINDOW_SEC
        prior = [t for t in _rate_buckets.get(key, []) if t >= cutoff]
        if len(prior) >= _RATE_LIMIT_MAX_POSTS:
            _rate_buckets[key] = prior
            return False
        prior.append(now)
        _rate_buckets[key] = prior
        return True

    def _validate_bill_uploads(self) -> str | None:
        """Return error message if uploads invalid; else None."""
        files = request.httprequest.files
        if not files:
            return None
        count = 0
        for _name in files:
            for upload in files.getlist(_name):
                if not upload or not upload.filename:
                    continue
                count += 1
                if count > _MAX_BILL_FILES:
                    return f"Máximo de {_MAX_BILL_FILES} ficheiros por candidatura."
                fname = upload.filename.lower()
                ext = "." + fname.rsplit(".", 1)[-1] if "." in fname else ""
                if ext not in _ALLOWED_BILL_EXT:
                    return f"Tipo de ficheiro não permitido: {upload.filename}"
                # size: read stream length carefully
                pos = upload.stream.tell()
                upload.stream.seek(0, 2)
                size = upload.stream.tell()
                upload.stream.seek(pos)
                if size > _MAX_BILL_BYTES:
                    return f"Ficheiro demasiado grande (máx. 5 MB): {upload.filename}"
                mime = (upload.mimetype or "").split(";")[0].strip().lower()
                if (
                    mime
                    and mime not in _ALLOWED_BILL_MIME
                    and mime != "application/octet-stream"
                ):
                    return f"Tipo MIME não permitido: {upload.filename}"
        return None

    def _location_label(self, location: str, location_custom: str) -> str:
        if location == "outro" and location_custom:
            return location_custom
        return location

    def _require_map_coords(self, location: str, lat: str, lng: str) -> str | None:
        if location != "outro":
            return None
        try:
            la = float(lat)
            ln = float(lng)
        except (TypeError, ValueError):
            return "No modo mapa, clique no mapa para definir a localização."
        if not (_LAT_MIN <= la <= _LAT_MAX and _LNG_MIN <= ln <= _LNG_MAX):
            return "Coordenadas de mapa inválidas."
        return None

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

    def _base_values(self, **extra):
        stations, dashboard, api_error = self._get_public_data()
        values = {
            "stations": stations,
            "stations_json": Markup(json.dumps(stations)),
            "dashboard": dashboard,
            "api_error": api_error,
            "city_options": _CITY_OPTIONS,
            "step": 1,
            "progress": 10,
            "submitted": False,
            "contact_submitted": False,
            "estimate": {},
            "estimate_data": "{}",
            "estimate_savings": "0",
            "estimate_kwp": "0.0",
            "panel_count": "",
            "capacity_kwp": "",
            "available_area": "",
            "location": "",
            "location_custom": "",
            "location_lat": "",
            "location_lng": "",
            "surface_type": "",
            "surface_other": "",
            "step1_name": "",
            "step1_email": "",
            "step2_org_name": "",
            "step2_org_type": "",
            "step2_website": "",
            "step2_description": "",
            "step3_monthly_spend": "",
            "step3_price_kwh": "",
            "step3_usage_pattern": "",
            "step3_description": "",
            "contact_name": "",
            "contact_email": "",
            "contact_phone": "",
            "contact_message": "",
            "success_stories": [],
            "blog_all_url": "/blog",
        }
        values.update(extra)
        if not values.get("success_stories"):
            values["success_stories"] = self._success_stories()
        # Prefer blog listing for the seeded blog when available
        try:
            blog = request.env.ref(
                "filantropia_solar_public.blog_casos_sucesso",
                raise_if_not_found=False,
            )
            if blog and getattr(blog, "website_url", None):
                values["blog_all_url"] = blog.website_url
        except Exception:
            pass

        if extra.get("form_error"):
            values["api_error"] = extra["form_error"]

        step = values.get("step", 1)
        if step not in (1, 2, 3, 4, "sme"):
            try:
                step = int(step)
            except (TypeError, ValueError):
                step = 1
        values["step"] = step
        values["progress"] = _STEP_PROGRESS.get(step, 10)

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
        return values

    def _render(self, template, **extra):
        return request.render(template, self._base_values(**extra))

    # ------------------------------------------------------------------
    # Content-first homepage (no application form)
    # ------------------------------------------------------------------
    @http.route(
        ["/", "/inicio", "/filantropia-solar"],
        type="http",
        auth="public",
        website=True,
    )
    def home(self, **kwargs):
        return self._render("filantropia_solar_public.page_inicio")

    # ------------------------------------------------------------------
    # Installations list ("Ver mais")
    # ------------------------------------------------------------------
    @http.route(
        ["/instalacoes", "/filantropia/instalacoes"],
        type="http",
        auth="public",
        website=True,
    )
    def instalacoes(self, **kwargs):
        return self._render("filantropia_solar_public.page_instalacoes")

    # ------------------------------------------------------------------
    # Contact form (simple, separate from candidatura)
    # ------------------------------------------------------------------
    @http.route(
        ["/contacto", "/contact", "/filantropia/contacto"],
        type="http",
        auth="public",
        website=True,
    )
    def contacto(self, **kwargs):
        return self._render("filantropia_solar_public.page_contacto")

    @http.route(
        "/contacto/enviar",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def contacto_enviar(self, **post):
        if not self._rate_limit_ok("contacto"):
            return self._render(
                "filantropia_solar_public.page_contacto",
                form_error="Demasiados pedidos. Aguarde alguns minutos e tente novamente.",
            )
        name = (post.get("contact_name") or "").strip()
        email = (post.get("contact_email") or "").strip()
        phone = (post.get("contact_phone") or "").strip()
        message = (post.get("contact_message") or "").strip()

        lead = (
            request.env["crm.lead"]
            .sudo()
            .create(
                {
                    "name": f"Filantropia Solar Contacto — {name or 'Visitante'}",
                    "contact_name": name or False,
                    "email_from": email or False,
                    "phone": phone or False,
                    "description": "\n".join(
                        [
                            "Contacto simples (não candidatura)",
                            f"Telefone: {phone}",
                            "",
                            "Mensagem:",
                            message,
                        ]
                    ),
                }
            )
        )
        _logger.info("Contact lead created: %s", lead.id)
        return self._render(
            "filantropia_solar_public.page_contacto",
            contact_submitted=True,
            contact_name=name,
            contact_email=email,
            contact_phone=phone,
            contact_message=message,
        )

    # ------------------------------------------------------------------
    # Candidatura multi-step page + funnel POSTs
    # ------------------------------------------------------------------
    @http.route(
        [
            "/candidatura",
            "/filantropia/application",
            "/filantropiasolar/candidatura",
        ],
        type="http",
        auth="public",
        website=True,
    )
    def candidatura(self, **kwargs):
        return self._render(
            "filantropia_solar_public.page_candidatura",
            step=1,
        )

    @http.route(
        "/candidatura/estimativa",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def candidatura_estimativa(self, **post):
        if not self._rate_limit_ok("estimativa"):
            return self._render(
                "filantropia_solar_public.page_candidatura",
                step=1,
                form_error="Demasiados pedidos. Aguarde alguns minutos e tente novamente.",
            )
        step1_name = (post.get("step1_name") or "").strip()
        step1_email = (post.get("step1_email") or "").strip()
        location = (post.get("location") or "").strip()
        location_custom = (post.get("location_custom") or "").strip()
        location_lat = (post.get("location_lat") or "").strip()
        location_lng = (post.get("location_lng") or "").strip()
        map_err = self._require_map_coords(location, location_lat, location_lng)
        if map_err:
            return self._render(
                "filantropia_solar_public.page_candidatura",
                step=1,
                form_error=map_err,
                step1_name=step1_name,
                step1_email=step1_email,
                location=location,
                location_custom=location_custom,
                location_lat=location_lat,
                location_lng=location_lng,
                surface_type=(post.get("surface_type") or "").strip(),
                available_area=(post.get("available_area") or "").strip(),
            )
        location_label = self._location_label(location, location_custom)
        surface_type = (post.get("surface_type") or "").strip()
        surface_other = (post.get("surface_other") or "").strip()
        available_area = self._as_float(post.get("available_area", "0"))

        panels, kwp = self._compute_panels(available_area)
        estimate: dict = {}
        form_error = None
        try:
            estimate = (
                self._estimate(
                    location_label,
                    location_lat or None,
                    location_lng or None,
                    kwp,
                )
                or {}
            )
        except Exception as exc:
            form_error = (
                "Não foi possível obter a estimativa automática. "
                "Pode continuar — a equipa valida os números manualmente."
            )
            _logger.warning("Step 1 estimate failed: %s", exc)

        return self._render(
            "filantropia_solar_public.page_candidatura",
            step=2,
            step1_name=step1_name,
            step1_email=step1_email,
            location=location,
            location_custom=location_custom,
            location_lat=location_lat,
            location_lng=location_lng,
            surface_type=surface_type,
            surface_other=surface_other,
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
        if not self._rate_limit_ok("elegibilidade"):
            return self._render(
                "filantropia_solar_public.page_candidatura",
                step=2,
                form_error="Demasiados pedidos. Aguarde alguns minutos e tente novamente.",
            )
        org_type = (post.get("step2_org_type") or "").strip()
        step1_name = (post.get("step1_name") or "").strip()
        step1_email = (post.get("step1_email") or "").strip()
        location = (post.get("location") or "").strip()
        location_custom = (post.get("location_custom") or "").strip()
        location_lat = (post.get("location_lat") or "").strip()
        location_lng = (post.get("location_lng") or "").strip()
        surface_type = (post.get("surface_type") or "").strip()
        surface_other = (post.get("surface_other") or "").strip()
        available_area = (post.get("available_area") or "").strip()
        capacity_kwp = (post.get("capacity_kwp") or "").strip()
        panel_count = (post.get("panel_count") or "").strip()
        step2_org_name = (post.get("step2_org_name") or "").strip()
        step2_website = (post.get("step2_website") or "").strip()
        step2_description = (post.get("step2_description") or "").strip()
        estimate = self._parse_estimate_data(post.get("estimate_data"))

        common = {
            "step1_name": step1_name,
            "step1_email": step1_email,
            "location": location,
            "location_custom": location_custom,
            "location_lat": location_lat,
            "location_lng": location_lng,
            "surface_type": surface_type,
            "surface_other": surface_other,
            "available_area": available_area,
            "capacity_kwp": capacity_kwp,
            "panel_count": panel_count,
            "step2_org_name": step2_org_name,
            "step2_org_type": org_type,
            "step2_website": step2_website,
            "step2_description": step2_description,
            "estimate": estimate,
            "estimate_data": json.dumps(estimate),
            "contact_name": step1_name,
            "contact_email": step1_email,
        }

        if org_type in _NGO_ORG_TYPES:
            return self._render(
                "filantropia_solar_public.page_candidatura",
                step=3,
                **common,
            )

        loc_label = location_custom if location == "outro" else location
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
                            f"Location: {loc_label}",
                            f"Available area: {available_area} m²",
                            f"Estimated capacity: {capacity_kwp} kWp",
                            f"Description: {step2_description}",
                            "Handed off to WeRa Global.",
                        ]
                    ),
                }
            )
        )
        _logger.info("SME lead created: %s -> WeRa referral", lead.id)
        return self._render(
            "filantropia_solar_public.page_candidatura",
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
        if not self._rate_limit_ok("enviar"):
            return self._render(
                "filantropia_solar_public.page_candidatura",
                step=3,
                form_error="Demasiados pedidos. Aguarde alguns minutos e tente novamente.",
            )
        bill_err = self._validate_bill_uploads()
        if bill_err:
            return self._render(
                "filantropia_solar_public.page_candidatura",
                step=3,
                form_error=bill_err,
                step1_name=(post.get("step1_name") or "").strip(),
                step1_email=(post.get("step1_email") or "").strip(),
                location=(post.get("location") or "").strip(),
                location_custom=(post.get("location_custom") or "").strip(),
                available_area=(post.get("available_area") or "").strip(),
                capacity_kwp=(post.get("capacity_kwp") or "").strip(),
                panel_count=(post.get("panel_count") or "").strip(),
                step2_org_name=(post.get("step2_org_name") or "").strip(),
                step2_org_type=(post.get("step2_org_type") or "").strip(),
                estimate=self._parse_estimate_data(post.get("estimate_data")),
            )
        step1_name = (post.get("step1_name") or "").strip()
        step1_email = (post.get("step1_email") or "").strip()
        location = (post.get("location") or "").strip()
        location_custom = (post.get("location_custom") or "").strip()
        location_lat = (post.get("location_lat") or "").strip()
        location_lng = (post.get("location_lng") or "").strip()
        surface_type = (post.get("surface_type") or "").strip()
        surface_other = (post.get("surface_other") or "").strip()
        available_area = (post.get("available_area") or "").strip()
        # Recompute panels/kWp server-side (do not trust client alone)
        panels, kwp = self._compute_panels(self._as_float(available_area, 0.0))
        capacity_kwp = f"{kwp:.2f}"
        panel_count = str(panels)
        step2_org_name = (post.get("step2_org_name") or "").strip()
        step2_org_type = (post.get("step2_org_type") or "").strip()
        step2_website = (post.get("step2_website") or "").strip()
        step2_description = (post.get("step2_description") or "").strip()
        step3_monthly_spend = (post.get("step3_monthly_spend") or "").strip()
        step3_price_kwh = (post.get("step3_price_kwh") or "").strip()
        step3_usage_pattern = (post.get("step3_usage_pattern") or "").strip()
        step3_description = (post.get("step3_description") or "").strip()
        step3_grid_connection = (post.get("step3_grid_connection") or "on_grid").strip().lower()
        if step3_grid_connection not in ("on_grid", "off_grid"):
            step3_grid_connection = "on_grid"
        if step3_grid_connection == "off_grid":
            # Off-grid: no grid bill / kWh price questions
            step3_monthly_spend = ""
            step3_price_kwh = ""
        # Recompute estimate from ML when possible; fall back to posted payload
        loc_label = self._location_label(location, location_custom)
        estimate = {}
        try:
            estimate = (
                self._estimate(
                    loc_label, location_lat or None, location_lng or None, kwp
                )
                or {}
            )
        except Exception as exc:
            _logger.warning("Final estimate recompute failed: %s", exc)
            estimate = self._parse_estimate_data(post.get("estimate_data"))
        if not estimate:
            estimate = self._parse_estimate_data(post.get("estimate_data"))
        surface_label = surface_other if surface_type == "other" else surface_type

        description_lines = [
            "Filantropia Solar — Candidatura de doação (funnel multi-passos)",
            "",
            "Contacto:",
            f"- Nome: {step1_name}",
            f"- Email: {step1_email}",
            "",
            "Estimativa:",
            f"- Localização: {loc_label}",
            f"- Coordenadas: {location_lat}, {location_lng}",
            f"- Superfície: {surface_label}",
            f"- Área disponível: {available_area} m²",
            f"- Painéis estimados: {panel_count}",
            f"- Capacidade estimada: {capacity_kwp} kWp",
            f"- Poupança anual estimada (EUR): {estimate.get('annual_savings_eur', 'n/d')}",
            "",
            "Organização:",
            f"- Nome: {step2_org_name}",
            f"- Tipo: {step2_org_type}",
            f"- Site: {step2_website}",
            f"- Descrição: {step2_description}",
            "",
            "Padrão de consumo:",
            f"- Ligação à rede: {step3_grid_connection}",
            f"- Gasto mensal: {step3_monthly_spend} EUR",
            f"- Preço/kWh: {step3_price_kwh}",
            f"- Padrão: {step3_usage_pattern}",
            f"- Notas: {step3_description}",
        ]

        price_kwh = self._as_float(step3_price_kwh, 0.0) if step3_price_kwh else 0.0
        website = step2_website or False
        if website and not str(website).lower().startswith(("http://", "https://")):
            website = "https://" + str(website)
        lead_vals = {
            "name": f"Filantropia Solar Candidatura — {step2_org_name or 'ONG'}",
            "type": "opportunity",
            "contact_name": step1_name or "Contacto desconhecido",
            "email_from": step1_email or False,
            "partner_name": step2_org_name or False,
            "city": loc_label or False,
            "website": website,
            "description": "\n".join(description_lines),
            "fs_is_donation_application": True,
            "fs_station_location_label": loc_label or False,
            "fs_station_latitude": self._as_float(location_lat, 0.0),
            "fs_station_longitude": self._as_float(location_lng, 0.0),
            "fs_station_grid_connection_type": step3_grid_connection,
                    "fs_station_capacity_kwp": kwp,
            "fs_station_website": website,
            "fs_station_short_description": step2_description or False,
            "fs_nc_sync_state": "pending",
            "fs_nc_sync_origin": "crm",
        }
        if price_kwh > 0:
            lead_vals["fs_station_grid_price_kwh"] = price_kwh
        lead = request.env["crm.lead"].sudo().create(lead_vals)
        self._attach_files(lead)
        # Deferred Virtual: New CRM stage has no NC station until Qualified
        # (ADR 0006 mirror: New/none, Qualified/Virtual).
        _logger.info(
            "Donation application lead created (NC Virtual deferred until Qualified): %s",
            lead.id,
        )

        return self._render(
            "filantropia_solar_public.page_candidatura",
            step=4,
            submitted=True,
            step1_name=step1_name,
            step1_email=step1_email,
            location=location,
            location_custom=location_custom,
            available_area=available_area,
            capacity_kwp=capacity_kwp,
            panel_count=panel_count,
            step2_org_name=step2_org_name,
            step2_org_type=step2_org_type,
            estimate=estimate,
            estimate_data=json.dumps(estimate),
            contact_name=step1_name,
            contact_email=step1_email,
        )
