"""Nextcloud public API client (read-only KPIs for Odoo admin dashboard)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any
import urllib.error
import urllib.request

from .nc_lifecycle_client import redact_secrets

_logger = logging.getLogger(__name__)


def public_base_url() -> str:
    return (
        (
            os.environ.get("FS_API_BASE_URL")
            or "http://filantropia-nextcloud/apps/filantropia_solar/api/public/v1"
        )
        .strip()
        .rstrip("/")
    )


def public_token() -> str:
    return (
        os.environ.get("FS_PUBLIC_API_TOKEN")
        or os.environ.get("FS_LIFECYCLE_API_TOKEN")
        or ""
    ).strip()


def nc_admin_url() -> str:
    """Operator UI for FilantropiaSolar app (AIO on TRL5 after cutover)."""
    explicit = (os.environ.get("FS_NC_ADMIN_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/") + (
            "" if explicit.rstrip("/").endswith("filantropia_solar") else "/apps/filantropia_solar/"
        )
    # Prefer public browser origin when API base is an internal Docker hostname
    for key in ("FS_NC_PUBLIC_ORIGIN", "WEBSITE_NC_URL"):
        origin = (os.environ.get(key) or "").strip().rstrip("/")
        if origin:
            return origin + "/apps/filantropia_solar/"
    base = public_base_url()
    # Internal docker hosts are not clickable from the operator browser
    if any(h in base for h in ("filantropia-nextcloud", "nextcloud-aio-", "localhost", "127.0.0.1")):
        # TRL5 AIO is the single NC instance — use public HTTPS host when known
        return "https://wera-ss-pt-tv-1.tailfb390c.ts.net/apps/filantropia_solar/"
    if "/apps/filantropia_solar" in base:
        return base.split("/apps/filantropia_solar")[0] + "/apps/filantropia_solar/"
    return base.rstrip("/") + "/apps/filantropia_solar/"


class NcPublicClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or public_base_url()).rstrip("/")
        self.token = token if token is not None else public_token()
        self.timeout = timeout

    def _get(self, path: str) -> dict[str, Any] | list[Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except Exception as exc:
            _logger.warning(
                "NC public GET %s failed: %s", path, redact_secrets(str(exc))
            )
            raise

    def stations(self) -> list[dict[str, Any]]:
        data = self._get("stations")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ("stations", "data", "results"):
                if isinstance(data.get(k), list):
                    return data[k]
        return []

    def dashboard(self) -> dict[str, Any]:
        try:
            data = self._get("dashboard")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
