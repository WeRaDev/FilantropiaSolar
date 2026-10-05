"""Renew the software lease and self-fence local Odoo writers on loss.

The guard is cooperative. If this process cannot run, Docker is wedged, or a
write path bypasses the guard, software fencing cannot guarantee stoppage.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Protocol

from embassy.lease import LeaseDecision, LeasePhase
from embassy.lease_client import LeaseClientError, load_lease_client_from_env
from embassy.writer_control import WriterControlError, fence_writer

_LOGGER = logging.getLogger("filantropia_embassy_lease_guard")
_NODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_DEFAULT_STATE = Path(
    os.environ.get(
        "FILANTROPIA_LEASE_GUARD_STATE",
        "/etc/filantropia-embassy/lease-guard-state.json",
    )
)


class LeaseGuardError(RuntimeError):
    """Raised when the local lease guard cannot safely continue as writer."""


class LeaseClientProtocol(Protocol):
    def status(self) -> LeaseDecision: ...

    def renew(
        self,
        *,
        node_id: str,
        epoch: int,
        generation: str,
        readiness_ok: bool,
    ) -> LeaseDecision: ...


def _identity() -> tuple[str, str]:
    node_id = os.environ.get("FS_EMBASSY_NODE_ID", "").strip()
    generation = os.environ.get("FS_WRITER_GENERATION", "").strip()
    if not _NODE_PATTERN.fullmatch(node_id) or not _NODE_PATTERN.fullmatch(generation):
        raise LeaseGuardError("Local writer identity is missing or invalid")
    if "REPLACE_WITH" in generation:
        raise LeaseGuardError("Writer generation placeholder is not allowed")
    return node_id, generation


def _read_state(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise LeaseGuardError("Lease guard state must not be a symlink")
    if not path.exists():
        return {"schema_version": 1, "highest_epoch_seen": 0, "fenced": False}
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise LeaseGuardError("Lease guard state is not private")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LeaseGuardError("Lease guard state is unreadable") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise LeaseGuardError("Lease guard state schema is invalid")
    return value


def _write_state(path: Path, state: dict[str, Any]) -> None:
    parent = path.parent
    if parent.is_symlink():
        raise LeaseGuardError("Lease guard state directory must not be a symlink")
    parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    payload = dict(state)
    payload["schema_version"] = 1
    payload["updated_at_utc"] = datetime.now(UTC).isoformat()
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise LeaseGuardError("Could not persist lease guard state") from exc


def local_readiness_ok() -> bool:
    """Best-effort local readiness used only to decide whether to renew."""
    if os.environ.get("FS_LEASE_FORCE_NOT_READY", "").strip() in {"1", "true", "yes"}:
        return False
    marker = Path(
        os.environ.get(
            "FILANTROPIA_ODOO_FENCE_FILE",
            "/etc/filantropia-embassy/odoo-fenced.json",
        )
    )
    if marker.exists() or marker.is_symlink():
        return False
    return True


def should_self_fence(
    *,
    node_id: str,
    generation: str,
    local_state: dict[str, Any],
    decision: LeaseDecision | None,
    authority_error: bool,
) -> tuple[bool, str]:
    """Decide whether the local writer must stop."""
    if local_state.get("fenced") is True:
        return True, "already_fenced"
    if authority_error:
        # Fail closed for renewals: cannot prove ownership while authority is down.
        return True, "lease_authority_unreachable"
    if decision is None:
        return True, "lease_decision_missing"
    highest = int(local_state.get("highest_epoch_seen") or 0)
    if decision.state.epoch < highest:
        return True, "stale_epoch_observed"
    if decision.phase != LeasePhase.ACTIVE:
        return True, f"lease_phase_{decision.phase.value}"
    if decision.state.owner_node_id != node_id:
        return True, "lease_owned_by_other_node"
    if decision.state.generation != generation:
        return True, "lease_generation_mismatch"
    if not decision.ok and decision.reason != "lease_renewed":
        # status-only success is fine when still active owner
        if decision.reason != "status":
            return True, decision.reason
    return False, "lease_active"


def run_once(
    *,
    client: LeaseClientProtocol,
    state_path: Path = _DEFAULT_STATE,
    perform_fence: bool = True,
) -> str:
    """One guard cycle: renew if owner, otherwise self-fence."""
    node_id, generation = _identity()
    local_state = _read_state(state_path)
    if local_state.get("fenced") is True:
        return "fenced"

    decision: LeaseDecision | None = None
    authority_error = False
    try:
        status = client.status()
        local_state["highest_epoch_seen"] = max(
            int(local_state.get("highest_epoch_seen") or 0),
            status.state.epoch,
        )
        if (
            status.phase == LeasePhase.ACTIVE
            and status.state.owner_node_id == node_id
            and status.state.generation == generation
        ):
            decision = client.renew(
                node_id=node_id,
                epoch=status.state.epoch,
                generation=generation,
                readiness_ok=local_readiness_ok(),
            )
            local_state["highest_epoch_seen"] = max(
                int(local_state["highest_epoch_seen"]),
                decision.state.epoch,
            )
        else:
            decision = status
    except (LeaseClientError, OSError, ValueError) as exc:
        _LOGGER.error("Lease authority interaction failed: %s", exc)
        authority_error = True

    fence, reason = should_self_fence(
        node_id=node_id,
        generation=generation,
        local_state=local_state,
        decision=decision,
        authority_error=authority_error,
    )
    if fence:
        local_state["fenced"] = True
        local_state["fence_reason"] = reason
        _write_state(state_path, local_state)
        if perform_fence:
            try:
                fence_writer(reason=reason[:64])
            except WriterControlError as exc:
                raise LeaseGuardError(
                    f"Self-fence marker set but writer stop failed: {exc}"
                ) from exc
        return f"fenced:{reason}"

    assert decision is not None
    local_state["fenced"] = False
    local_state["active_epoch"] = decision.state.epoch
    local_state["lease_expires_at"] = (
        decision.state.lease_expires_at.isoformat()
        if decision.state.lease_expires_at
        else None
    )
    _write_state(state_path, local_state)
    return "active"


def startup_allowed(*, state_path: Path = _DEFAULT_STATE) -> bool:
    """Boot gate used by ensure-stack before starting Odoo or cloudflared."""
    state = _read_state(state_path)
    if state.get("fenced") is True:
        return False
    fence_file = Path(
        os.environ.get(
            "FILANTROPIA_ODOO_FENCE_FILE",
            "/etc/filantropia-embassy/odoo-fenced.json",
        )
    )
    return not (fence_file.exists() or fence_file.is_symlink())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("once", "startup-check"),
        help="Run one renew/fence cycle, or exit 0/1 for boot gating",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=_DEFAULT_STATE,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Update local lease state without calling writer_control fence",
    )
    arguments = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        if arguments.action == "startup-check":
            return 0 if startup_allowed(state_path=arguments.state_file) else 1
        client = load_lease_client_from_env()
        result = run_once(
            client=client,
            state_path=arguments.state_file,
            perform_fence=not arguments.dry_run,
        )
        _LOGGER.info("Lease guard result: %s", result)
        return 0 if result == "active" else 2
    except (LeaseGuardError, LeaseClientError, WriterControlError, OSError, ValueError) as exc:
        _LOGGER.error("Lease guard failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
