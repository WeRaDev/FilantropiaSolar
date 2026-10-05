"""Authenticated HTTP client for the external software-lease authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from embassy.lease import LeaseDecision, LeaseError, LeasePhase, LeaseState

if TYPE_CHECKING:
    from embassy.lease import InMemoryLeaseAuthority

_MAX_JSON_BYTES = 32 * 1024


class LeaseClientError(RuntimeError):
    """Raised when the lease authority cannot be reached or trusted."""


@dataclass(frozen=True)
class LeaseClientConfig:
    """Connection settings for the Durable Object or lab HTTP authority."""

    base_url: str
    token: str
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not self.base_url.startswith(("https://", "http://")):
            raise LeaseClientError("Lease authority URL must be absolute HTTP(S)")
        if self.base_url.startswith("http://"):
            host = self.base_url.removeprefix("http://").split("/", 1)[0].lower()
            if not (
                host.startswith("127.0.0.1")
                or host.startswith("localhost")
                or host.startswith("[::1]")
            ):
                raise LeaseClientError("Plain HTTP lease clients are loopback-only")
        if not self.token.strip():
            raise LeaseClientError("Lease authority token is required")
        if self.timeout_seconds <= 0:
            raise LeaseClientError("Lease timeout must be positive")


class HttpLeaseClient:
    """Talk to a remote lease Worker/Durable Object over HTTPS."""

    def __init__(self, config: LeaseClientConfig) -> None:
        self.config = config
        self._opener = build_opener(ProxyHandler({}))

    def status(self) -> LeaseDecision:
        return self._call("GET", "/lease/status", body=None)

    def bootstrap(self, *, node_id: str, generation: str) -> LeaseDecision:
        return self._call(
            "POST",
            "/lease/bootstrap",
            body={"node_id": node_id, "generation": generation},
        )

    def renew(
        self,
        *,
        node_id: str,
        epoch: int,
        generation: str,
        readiness_ok: bool,
    ) -> LeaseDecision:
        return self._call(
            "POST",
            "/lease/renew",
            body={
                "node_id": node_id,
                "epoch": epoch,
                "generation": generation,
                "readiness_ok": readiness_ok,
            },
        )

    def request_takeover(
        self,
        *,
        requester_node_id: str,
        target_node_id: str,
        target_generation: str,
        reason: str = "dual_probe_failure",
    ) -> LeaseDecision:
        return self._call(
            "POST",
            "/lease/request-takeover",
            body={
                "requester_node_id": requester_node_id,
                "target_node_id": target_node_id,
                "target_generation": target_generation,
                "reason": reason,
            },
        )

    def acquire(
        self,
        *,
        node_id: str,
        generation: str,
        previous_epoch: int,
    ) -> LeaseDecision:
        return self._call(
            "POST",
            "/lease/acquire",
            body={
                "node_id": node_id,
                "generation": generation,
                "previous_epoch": previous_epoch,
            },
        )

    def _call(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None,
    ) -> LeaseDecision:
        url = self.config.base_url.rstrip("/") + path
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.token}",
            "Cache-Control": "no-cache, no-store, max-age=0",
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read(_MAX_JSON_BYTES + 1)
                status_code = response.getcode()
        except HTTPError as exc:
            try:
                raw = exc.read(_MAX_JSON_BYTES + 1)
            except OSError as read_exc:
                raise LeaseClientError("Lease authority error body unreadable") from read_exc
            status_code = exc.code
            if status_code >= 500:
                raise LeaseClientError("Lease authority is unavailable") from exc
        except (OSError, TimeoutError, URLError) as exc:
            raise LeaseClientError("Lease authority is unreachable") from exc
        if len(raw) > _MAX_JSON_BYTES:
            raise LeaseClientError("Lease authority response is too large")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LeaseClientError("Lease authority returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise LeaseClientError("Lease authority returned invalid shape")
        return _decision_from_payload(payload, http_ok=200 <= status_code < 300)


class MemoryLeaseClient:
    """Adapter so Embassy/lease-guard code can use InMemoryLeaseAuthority."""

    def __init__(self, authority: InMemoryLeaseAuthority) -> None:
        self.authority = authority

    def status(self) -> LeaseDecision:
        return self.authority.status(now=datetime.now(UTC))

    def bootstrap(self, *, node_id: str, generation: str) -> LeaseDecision:
        return self.authority.bootstrap(
            node_id=node_id,
            generation=generation,
            now=datetime.now(UTC),
        )

    def renew(
        self,
        *,
        node_id: str,
        epoch: int,
        generation: str,
        readiness_ok: bool,
    ) -> LeaseDecision:
        return self.authority.renew(
            node_id=node_id,
            epoch=epoch,
            generation=generation,
            readiness_ok=readiness_ok,
            now=datetime.now(UTC),
        )

    def request_takeover(
        self,
        *,
        requester_node_id: str,
        target_node_id: str,
        target_generation: str,
        reason: str = "dual_probe_failure",
    ) -> LeaseDecision:
        return self.authority.request_takeover(
            requester_node_id=requester_node_id,
            target_node_id=target_node_id,
            target_generation=target_generation,
            now=datetime.now(UTC),
            reason=reason,
        )

    def acquire(
        self,
        *,
        node_id: str,
        generation: str,
        previous_epoch: int,
    ) -> LeaseDecision:
        return self.authority.acquire(
            node_id=node_id,
            generation=generation,
            previous_epoch=previous_epoch,
            now=datetime.now(UTC),
        )


def load_lease_client_from_env() -> HttpLeaseClient:
    """Build a production-style client from process environment."""
    token_env = os.environ.get("FS_LEASE_TOKEN_ENV", "FS_LEASE_AUTHORITY_TOKEN")
    token = os.environ.get(token_env, "")
    config = LeaseClientConfig(
        base_url=os.environ.get("FS_LEASE_AUTHORITY_URL", ""),
        token=token,
        timeout_seconds=float(os.environ.get("FS_LEASE_TIMEOUT_SECONDS", "5")),
    )
    return HttpLeaseClient(config)


def write_fencing_proof_file(path: str | os.PathLike[str], proof: dict[str, object]) -> None:
    """Atomically publish a private fencing-proof JSON file for Embassy."""
    from pathlib import Path
    import stat
    import tempfile

    target = Path(path)
    if target.is_symlink():
        raise LeaseClientError("Fencing proof path must not be a symlink")
    parent = target.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise LeaseClientError("Fencing proof directory is not private")
    payload = (json.dumps(proof, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(target)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise LeaseClientError("Could not publish fencing proof") from exc


def _decision_from_payload(payload: dict[str, object], *, http_ok: bool) -> LeaseDecision:
    try:
        state = LeaseState.from_dict(payload["state"])  # type: ignore[arg-type]
        phase = LeasePhase(str(payload["phase"]))
        reason = str(payload.get("reason") or "unspecified")
        fencing_proof = payload.get("fencing_proof")
        if fencing_proof is not None and not isinstance(fencing_proof, dict):
            raise LeaseError("Invalid fencing proof")
        request_permit = bool(payload.get("request_permit", False))
        ok = bool(payload.get("ok", http_ok))
    except (KeyError, TypeError, ValueError, LeaseError) as exc:
        raise LeaseClientError("Lease authority payload is invalid") from exc
    return LeaseDecision(
        ok=ok,
        state=state,
        phase=phase,
        reason=reason,
        fencing_proof=fencing_proof if isinstance(fencing_proof, dict) else None,
        request_permit=request_permit,
    )
