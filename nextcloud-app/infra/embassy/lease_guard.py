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
# Fences that must never auto-clear (failback/standby/other-writer).
_PERMANENT_FENCE_REASONS = frozenset(
    {
        "failback_to_trl5",
        "standby_awaiting_promote",
        "lease_owned_by_other_node",
        "lease_generation_mismatch",
        "stale_epoch_observed",
        "operator_fence",
        "already_fenced",
    }
)
# Transient reasons: authority blip or expired self-lease while still the writer.
_RECOVERABLE_FENCE_REASONS = frozenset(
    {
        "lease_authority_unreachable",
        "lease_decision_missing",
        "lease_phase_acquirable",
        "lease_phase_unowned",
        "not_current_owner_or_lease_expired",
    }
)
_DEFAULT_AUTHORITY_FAILURE_THRESHOLD = 2


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

    def acquire(
        self,
        *,
        node_id: str,
        generation: str,
        previous_epoch: int,
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
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
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
    if marker.is_symlink():
        return False
    if not marker.exists():
        return True
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    # Only a fenced marker blocks renew; unfenced/operator markers may remain.
    return not (isinstance(payload, dict) and payload.get("state") == "fenced")


def authority_failure_threshold() -> int:
    raw = os.environ.get("FS_LEASE_AUTHORITY_FAILURE_THRESHOLD", "").strip()
    if not raw:
        return _DEFAULT_AUTHORITY_FAILURE_THRESHOLD
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_AUTHORITY_FAILURE_THRESHOLD
    return max(1, value)


def is_recoverable_fence_reason(reason: str | None) -> bool:
    """Return True when a sticky fence may clear after the authority recovers."""
    if not reason:
        return False
    if reason in _PERMANENT_FENCE_REASONS:
        return False
    if reason.startswith("failback") or reason.startswith("standby_"):
        return False
    if reason in _RECOVERABLE_FENCE_REASONS:
        return True
    # lease_phase_* for draining/takeover_pending stays sticky until operator.
    return False


def is_intentional_standby_fence(reason: str | None) -> bool:
    """Return True for operator/standby fences that are healthy non-writer posture."""
    if not reason:
        return False
    if reason in {"failback_to_trl5", "standby_awaiting_promote", "operator_fence"}:
        return True
    if reason.startswith("failback") or reason.startswith("standby_"):
        return True
    return False


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
        existing = str(local_state.get("fence_reason") or "already_fenced")
        return True, existing if existing else "already_fenced"
    if authority_error:
        failures = int(local_state.get("authority_failures") or 0)
        threshold = authority_failure_threshold()
        if failures < threshold:
            # Soft fail: do not sticky-fence on a single blip.
            return False, f"authority_retry_{failures}"
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
    if not decision.ok and decision.reason not in {"lease_renewed", "status"}:
        # status-only success is fine when still active owner
        return True, decision.reason
    return False, "lease_active"


def _record_active_state(
    *,
    state_path: Path,
    local_state: dict[str, Any],
    decision: LeaseDecision,
) -> str:
    local_state["fenced"] = False
    local_state.pop("fence_reason", None)
    local_state["authority_failures"] = 0
    local_state["active_epoch"] = decision.state.epoch
    local_state["lease_expires_at"] = (
        decision.state.lease_expires_at.isoformat()
        if decision.state.lease_expires_at
        else None
    )
    _write_state(state_path, local_state)
    return "active"


def ensure_writer_containers() -> None:
    """Best-effort restart of local writer containers after transient recovery."""
    import subprocess

    raw = os.environ.get(
        "FS_LEASE_GUARD_ENSURE_CONTAINERS",
        "filantropia-odoo-db,filantropia-odoo,filantropia-cloudflared",
    )
    names = [part.strip() for part in raw.split(",") if part.strip()]
    if not names:
        return
    if os.environ.get("FS_LEASE_GUARD_SKIP_ENSURE_CONTAINERS", "").strip() in {
        "1",
        "true",
        "yes",
    }:
        return
    try:
        subprocess.run(
            ["docker", "start", *names],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _LOGGER.warning("Writer container ensure failed: %s", exc)


def _try_recover_transient_fence(
    *,
    client: LeaseClientProtocol,
    node_id: str,
    generation: str,
    state_path: Path,
    local_state: dict[str, Any],
    perform_fence: bool,
) -> str:
    """Clear recoverable fences once the lease authority is reachable again."""
    reason = str(local_state.get("fence_reason") or "already_fenced")
    if not is_recoverable_fence_reason(reason):
        return f"fenced:{reason}"

    try:
        status = client.status()
    except (LeaseClientError, OSError, ValueError) as exc:
        _LOGGER.warning("Recovery probe still failing (%s): %s", reason, exc)
        return f"fenced:{reason}"

    local_state["highest_epoch_seen"] = max(
        int(local_state.get("highest_epoch_seen") or 0),
        int(status.state.epoch or 0),
    )
    decision: LeaseDecision | None = None

    if (
        status.phase == LeasePhase.ACTIVE
        and status.state.owner_node_id == node_id
        and status.state.generation == generation
        and status.state.epoch is not None
    ):
        # Prove ownership before clearing fences or starting containers.
        try:
            decision = client.renew(
                node_id=node_id,
                epoch=int(status.state.epoch),
                generation=generation,
                readiness_ok=True,
            )
        except (LeaseClientError, OSError, ValueError) as exc:
            _LOGGER.error("Recovery renew failed: %s", exc)
            return f"fenced:{reason}"
        if (
            not decision.ok
            or decision.phase != LeasePhase.ACTIVE
            or decision.state.owner_node_id != node_id
        ):
            return f"fenced:{reason}"
        clear_local_writer_fence_marker()
        local_state["highest_epoch_seen"] = max(
            int(local_state["highest_epoch_seen"]),
            int(decision.state.epoch or 0),
        )
        local_state["recovery_reason"] = f"recovered_from_{reason}"
        _record_active_state(
            state_path=state_path, local_state=local_state, decision=decision
        )
        if perform_fence:
            ensure_writer_containers()
        _LOGGER.info("Lease guard recovered active ownership after %s", reason)
        return "recovered:active"

    if (
        status.phase == LeasePhase.ACQUIRABLE
        and status.state.owner_node_id == node_id
        and status.state.generation == generation
        and status.state.epoch is not None
    ):
        # Prove reacquire before clearing fences or starting containers.
        try:
            decision = client.acquire(
                node_id=node_id,
                generation=generation,
                previous_epoch=int(status.state.epoch),
            )
        except (LeaseClientError, OSError, ValueError) as exc:
            _LOGGER.error("Recovery acquire failed: %s", exc)
            return f"fenced:{reason}"
        if (
            not decision.ok
            or decision.phase != LeasePhase.ACTIVE
            or decision.state.owner_node_id != node_id
        ):
            return f"fenced:{reason}"
        clear_local_writer_fence_marker()
        local_state["highest_epoch_seen"] = max(
            int(local_state["highest_epoch_seen"]),
            int(decision.state.epoch or 0),
        )
        local_state["recovery_reason"] = f"reacquired_from_{reason}"
        _record_active_state(
            state_path=state_path, local_state=local_state, decision=decision
        )
        if perform_fence:
            ensure_writer_containers()
        _LOGGER.info("Lease guard reacquired expired self-lease after %s", reason)
        return "recovered:reacquired"

    if (
        status.state.owner_node_id
        and status.state.owner_node_id != node_id
        and status.phase == LeasePhase.ACTIVE
    ):
        local_state["fenced"] = True
        local_state["fence_reason"] = "lease_owned_by_other_node"
        _write_state(state_path, local_state)
        return "fenced:lease_owned_by_other_node"

    # Authority is up but this node is not yet eligible to write again.
    return f"fenced:{reason}"


def run_once(
    *,
    client: LeaseClientProtocol,
    state_path: Path = _DEFAULT_STATE,
    perform_fence: bool = True,
) -> str:
    """One guard cycle: renew if owner, recover transient fences, else self-fence."""
    node_id, generation = _identity()
    local_state = _read_state(state_path)
    if local_state.get("fenced") is True:
        return _try_recover_transient_fence(
            client=client,
            node_id=node_id,
            generation=generation,
            state_path=state_path,
            local_state=local_state,
            perform_fence=perform_fence,
        )

    decision: LeaseDecision | None = None
    authority_error = False
    try:
        status = client.status()
        local_state["authority_failures"] = 0
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
        elif (
            status.phase == LeasePhase.ACQUIRABLE
            and status.state.owner_node_id == node_id
            and status.state.generation == generation
            and status.state.epoch is not None
        ):
            # Expired self-lease: reclaim before fencing so a brief TTL miss does
            # not permanently stop the only writer.
            decision = client.acquire(
                node_id=node_id,
                generation=generation,
                previous_epoch=int(status.state.epoch),
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
        local_state["authority_failures"] = int(
            local_state.get("authority_failures") or 0
        ) + 1

    fence, reason = should_self_fence(
        node_id=node_id,
        generation=generation,
        local_state=local_state,
        decision=decision,
        authority_error=authority_error,
    )
    if authority_error and not fence:
        # Soft authority blip: persist failure count, keep writer running.
        _write_state(state_path, local_state)
        return f"authority_retry:{local_state.get('authority_failures')}"
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
    return _record_active_state(
        state_path=state_path, local_state=local_state, decision=decision
    )


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


def _fence_marker_path() -> Path:
    return Path(
        os.environ.get(
            "FILANTROPIA_ODOO_FENCE_FILE",
            "/etc/filantropia-embassy/odoo-fenced.json",
        )
    )


def clear_local_writer_fence_marker(*, fence_file: Path | None = None) -> None:
    """Remove sticky Odoo fence marker so the new writer can renew."""
    path = fence_file if fence_file is not None else _fence_marker_path()
    if path.is_symlink():
        raise LeaseGuardError("Odoo fence marker must not be a symlink")
    if not path.exists():
        return
    try:
        path.unlink()
    except OSError as exc:
        raise LeaseGuardError("Could not clear Odoo fence marker") from exc


def write_active_guard_state(
    *,
    state_path: Path = _DEFAULT_STATE,
    epoch: int,
    lease_expires_at: datetime | None,
    highest_epoch_seen: int | None = None,
    arm_reason: str = "post_promote_arm",
) -> dict[str, Any]:
    """Persist unfenced lease-guard state for the newly acquired writer epoch."""
    if epoch < 1:
        raise LeaseGuardError("Active epoch must be positive")
    previous = {}
    if state_path.exists():
        previous = _read_state(state_path)
    highest = max(
        int(previous.get("highest_epoch_seen") or 0),
        int(highest_epoch_seen or 0),
        int(epoch),
    )
    state: dict[str, Any] = {
        "schema_version": 1,
        "fenced": False,
        "highest_epoch_seen": highest,
        "active_epoch": int(epoch),
        "lease_expires_at": (
            lease_expires_at.isoformat() if lease_expires_at is not None else None
        ),
        "arm_reason": arm_reason,
        "authority_failures": 0,
    }
    # Drop sticky fence reason from standby/failback posture.
    previous.pop("fence_reason", None)
    _write_state(state_path, state)
    return state


def enable_lease_guard_timer(
    *,
    unit: str = "filantropia-lease-guard.timer",
    run_once_unit: str = "filantropia-lease-guard.service",
) -> None:
    """Ensure the host lease-guard timer (and one immediate cycle) is running."""
    import subprocess

    commands = (
        ["systemctl", "reset-failed", run_once_unit],
        ["systemctl", "enable", "--now", unit],
        ["systemctl", "start", run_once_unit],
        ["systemctl", "start", unit],
    )
    for command in commands:
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "LC_ALL": "C"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LeaseGuardError(
                f"Lease guard unit command failed: {' '.join(command)}"
            ) from exc
        # reset-failed / enable may return non-zero on missing units in lab;
        # start of the timer is mandatory for durability.
        if command[1] in {"start", "enable"} and result.returncode:
            detail = (result.stderr or result.stdout or "").strip()[:200]
            raise LeaseGuardError(
                f"Could not ensure lease guard unit {' '.join(command[1:])}: {detail}"
            )


def arm_lease_guard_as_writer(
    *,
    client: LeaseClientProtocol,
    node_id: str,
    generation: str,
    epoch: int,
    lease_expires_at: datetime | None = None,
    state_path: Path = _DEFAULT_STATE,
    fence_file: Path | None = None,
    enable_timer: bool = True,
    renew_now: bool = True,
) -> dict[str, object]:
    """Transition standby/fenced guard posture into durable writer renewals.

    Called immediately after promote acquires the lease so apex does not 503
    when the previous prep left the timer stopped or state fenced.
    """
    if not _NODE_PATTERN.fullmatch(node_id) or not _NODE_PATTERN.fullmatch(generation):
        raise LeaseGuardError("Writer identity for arm is invalid")
    if epoch < 1:
        raise LeaseGuardError("Writer epoch for arm is invalid")

    # Prove this node already owns the active epoch BEFORE clearing local fences.
    # Otherwise a failed/partial promote could unfence a standby incorrectly.
    try:
        status = client.status()
    except (LeaseClientError, OSError, ValueError) as exc:
        raise LeaseGuardError(
            f"Post-promote lease status verification failed: {exc}"
        ) from exc
    if (
        status.phase != LeasePhase.ACTIVE
        or status.state.owner_node_id != node_id
        or status.state.generation != generation
        or status.state.epoch is None
        or int(status.state.epoch) < int(epoch)
    ):
        raise LeaseGuardError(
            "Post-promote lease is not active for the promoted writer"
        )

    clear_local_writer_fence_marker(fence_file=fence_file)
    active_epoch = int(status.state.epoch)
    expires_at = status.state.lease_expires_at or lease_expires_at
    state = write_active_guard_state(
        state_path=state_path,
        epoch=active_epoch,
        lease_expires_at=expires_at,
        highest_epoch_seen=active_epoch,
        arm_reason="post_promote_arm",
    )

    renewed = False
    if renew_now:
        try:
            decision = client.renew(
                node_id=node_id,
                epoch=active_epoch,
                generation=generation,
                readiness_ok=True,
            )
        except (LeaseClientError, OSError, ValueError) as exc:
            raise LeaseGuardError(f"Post-promote lease renew failed: {exc}") from exc
        if (
            not decision.ok
            or decision.phase != LeasePhase.ACTIVE
            or decision.state.owner_node_id != node_id
            or decision.state.epoch is None
            or int(decision.state.epoch) < active_epoch
        ):
            raise LeaseGuardError(
                f"Post-promote lease renew refused: {decision.reason}"
            )
        renewed = True
        active_epoch = int(decision.state.epoch)
        expires_at = decision.state.lease_expires_at
        state = write_active_guard_state(
            state_path=state_path,
            epoch=active_epoch,
            lease_expires_at=expires_at,
            highest_epoch_seen=active_epoch,
            arm_reason="post_promote_arm_renewed",
        )

    timer_enabled = False
    if enable_timer:
        enable_lease_guard_timer()
        timer_enabled = True

    # Re-check ownership after renew/timer so apex durability is proven.
    try:
        final_status = client.status()
    except (LeaseClientError, OSError, ValueError) as exc:
        raise LeaseGuardError(
            f"Post-promote lease status verification failed: {exc}"
        ) from exc
    if (
        final_status.phase != LeasePhase.ACTIVE
        or final_status.state.owner_node_id != node_id
        or final_status.state.generation != generation
    ):
        raise LeaseGuardError(
            "Post-promote lease is not active for the promoted writer after arm"
        )

    result = {
        "armed": True,
        "renewed": renewed,
        "timer_enabled": timer_enabled,
        "epoch": active_epoch,
        "lease_expires_at": expires_at.isoformat() if expires_at else None,
        "state_path": str(state_path),
        "fenced": bool(state.get("fenced")),
    }
    _LOGGER.info("Lease guard armed as writer: %s", result)
    return result


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
        if result == "active" or result.startswith("recovered:") or result.startswith(
            "authority_retry:"
        ):
            return 0
        if result.startswith("fenced:"):
            fence_reason = result.split(":", 1)[1]
            # Standby/failback posture is expected healthy; avoid systemd failure spam.
            if is_intentional_standby_fence(fence_reason):
                return 0
        return 2
    except (
        LeaseGuardError,
        LeaseClientError,
        WriterControlError,
        OSError,
        ValueError,
    ) as exc:
        _LOGGER.error("Lease guard failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
