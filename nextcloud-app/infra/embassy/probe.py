"""Origin-specific and public-route probes with cache and redirect defenses."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

_MAX_JSON_BYTES = 64 * 1024
_TAILSCALE_IPV4 = ipaddress.ip_network("100.64.0.0/10")


@dataclass(frozen=True)
class ProbeResult:
    """Sanitized result; never retain request URLs or authorization headers."""

    reachable: bool
    status_code: int | None
    payload: dict[str, object] | None = None
    error_kind: str | None = None


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl


def _uncached_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Probe URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Probe URL must not contain credentials or a fragment")
    if parsed.query:
        raise ValueError("Probe URL must not contain a query string")
    if parsed.scheme == "http":
        hostname = parsed.hostname.lower()
        allowed_http = hostname in {"localhost", "127.0.0.1", "::1"}
        if not allowed_http:
            try:
                allowed_http = ipaddress.ip_address(hostname) in _TAILSCALE_IPV4
            except ValueError:
                allowed_http = hostname.endswith(".ts.net")
        if not allowed_http:
            raise ValueError("Plain HTTP probes are restricted to loopback or Tailnet")
    query = urlencode({"_embassy_probe": time.time_ns()})
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", query, ""))


def _decode_json(raw: bytes) -> tuple[dict[str, object] | None, str | None]:
    if len(raw) > _MAX_JSON_BYTES:
        return None, "response_too_large"
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "invalid_json"
    if not isinstance(value, dict):
        return None, "invalid_json_shape"
    return value, None


def _request(
    url: str,
    *,
    timeout_seconds: float,
    token: str | None,
    decode_json: bool,
) -> ProbeResult:
    nonce_url = _uncached_url(url)
    headers = {
        "Accept": "application/json" if decode_json else "*/*",
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
    }
    if token is not None:
        if not token.strip():
            raise ValueError("Readiness token must not be empty")
        headers["Authorization"] = f"Bearer {token}"
    request = Request(nonce_url, headers=headers, method="GET")
    opener = build_opener(ProxyHandler({}), _NoRedirectHandler())

    response = None
    try:
        response = opener.open(request, timeout=timeout_seconds)
        status_code = response.getcode()
    except HTTPError as exc:
        response = exc
        status_code = exc.code
    except (OSError, TimeoutError, URLError) as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        return ProbeResult(
            reachable=False,
            status_code=None,
            error_kind=type(reason).__name__,
        )

    try:
        raw = response.read(_MAX_JSON_BYTES + 1) if decode_json else b""
    finally:
        response.close()

    payload = None
    error_kind = None
    if decode_json:
        payload, error_kind = _decode_json(raw)
    return ProbeResult(
        reachable=True,
        status_code=status_code,
        payload=payload,
        error_kind=error_kind,
    )


def probe_readiness(url: str, *, token: str, timeout_seconds: float) -> ProbeResult:
    """Request the protected, origin-specific readiness payload."""
    return _request(
        url,
        timeout_seconds=timeout_seconds,
        token=token,
        decode_json=True,
    )


def probe_public_route(url: str, *, timeout_seconds: float) -> ProbeResult:
    """Request one public route without following redirects or using caches."""
    return _request(
        url,
        timeout_seconds=timeout_seconds,
        token=None,
        decode_json=False,
    )
