"""Nextcloud lifecycle API client for Odoo CRM glue (MVP-5).

Never log bearer tokens. Prefer FS_LIFECYCLE_* env vars; fall back to public token.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
import urllib.error
from urllib.parse import quote
import urllib.request

_logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(
    r"(Bearer\s+)[A-Za-z0-9._\-+=/]+",
    re.IGNORECASE,
)


def redact_secrets(text: str) -> str:
    """Strip bearer tokens and long hex secrets from log-safe strings."""
    if not text:
        return text
    out = _TOKEN_RE.sub(r"\1[REDACTED]", text)
    # Long hex-like tokens (public_api_token style)
    out = re.sub(r"\b[a-f0-9]{32,}\b", "[REDACTED]", out, flags=re.I)
    return out


def lifecycle_base_url() -> str:
    """Base URL ending at .../api/lifecycle/v1 (no trailing slash)."""
    explicit = (os.environ.get("FS_LIFECYCLE_API_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    public = (
        (
            os.environ.get("FS_API_BASE_URL")
            or "http://filantropia-nextcloud/apps/filantropia_solar/api/public/v1"
        )
        .strip()
        .rstrip("/")
    )
    if public.endswith("/api/public/v1"):
        return public[: -len("/api/public/v1")] + "/api/lifecycle/v1"
    if "/api/public/" in public:
        return public.replace("/api/public/", "/api/lifecycle/")
    # Last resort: sibling path under apps/filantropia_solar
    if public.endswith("/apps/filantropia_solar"):
        return public + "/api/lifecycle/v1"
    return public + "/api/lifecycle/v1"


def lifecycle_token() -> str:
    return (
        os.environ.get("FS_LIFECYCLE_API_TOKEN")
        or os.environ.get("FS_PUBLIC_API_TOKEN")
        or ""
    ).strip()


class NcLifecycleError(Exception):
    def __init__(
        self, message: str, *, status: int | None = None, body: str | None = None
    ):
        super().__init__(message)
        self.status = status
        self.body = body


class NcLifecycleClient:
    """Thin urllib client for NC lifecycle write API."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or lifecycle_base_url()).rstrip("/")
        self.token = token if token is not None else lifecycle_token()
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            headers=self._headers(),
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return {"success": True}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = str(exc)
            safe = redact_secrets(body)
            _logger.warning(
                "NC lifecycle HTTP %s %s -> %s: %s",
                method,
                path,
                exc.code,
                safe[:500],
            )
            raise NcLifecycleError(
                f"NC lifecycle {method} {path} failed with HTTP {exc.code}",
                status=exc.code,
                body=safe,
            ) from None
        except Exception as exc:
            safe = redact_secrets(str(exc))
            _logger.warning("NC lifecycle request failed: %s", safe)
            raise NcLifecycleError(safe) from None

    def create_virtual(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "stations/virtual", payload)

    def promote_planned(self, installation_id: str) -> dict[str, Any]:
        enc = quote(str(installation_id), safe="")
        return self._request("POST", f"stations/{enc}/promote-planned", {})

    def get_station(self, installation_id: str) -> dict[str, Any]:
        enc = quote(str(installation_id), safe="")
        return self._request("GET", f"stations/{enc}")

    def mark_installed(
        self,
        installation_id: str,
        *,
        installed_at: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        enc = quote(str(installation_id), safe="")
        body: dict[str, Any] = {}
        if installed_at:
            body["installed_at"] = installed_at
        if actor:
            body["actor"] = actor
        return self._request("POST", f"stations/{enc}/mark-installed", body or {})

    def list_stations(
        self,
        *,
        include_soft_removed: bool = False,
        include_dataset: bool = False,
    ) -> dict[str, Any]:
        """List stations for CRM mirror (ops only unless include_dataset)."""
        parts = [
            "include_soft_removed=1"
            if include_soft_removed
            else "include_soft_removed=0",
            "include_dataset=1" if include_dataset else "include_dataset=0",
        ]
        return self._request("GET", f"stations?{'&'.join(parts)}")

    def bind_lead(self, installation_id: str, odoo_lead_id: int) -> dict[str, Any]:
        """Attach CRM lead id on NC station (idempotent)."""
        enc = quote(str(installation_id), safe="")
        return self._request(
            "POST",
            f"stations/{enc}/bind-lead",
            {"odoo_lead_id": int(odoo_lead_id)},
        )

    def set_lifecycle(
        self,
        installation_id: str,
        lifecycle_state: str,
        *,
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Set NC lifecycle explicitly (supports demotion)."""
        enc = quote(str(installation_id), safe="")
        body: dict[str, Any] = {"lifecycle_state": str(lifecycle_state)}
        if actor:
            body["actor"] = actor
        return self._request("POST", f"stations/{enc}/set-lifecycle", body)
