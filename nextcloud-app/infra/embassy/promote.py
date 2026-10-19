"""Fail-closed promotion actions after lease fencing and standby validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import os
from pathlib import Path
import subprocess
import time
from typing import TYPE_CHECKING

from embassy.filestore_promote import FilestorePromoteConfig, promote_filestore
from embassy.lease_client import LeaseClientError, write_fencing_proof_file
from embassy.lease_guard import LeaseGuardError, arm_lease_guard_as_writer
from embassy.policy import DecisionState
from embassy.replication_bootstrap import promote_standby_sql

if TYPE_CHECKING:
    from embassy.replication import AttachmentReference

_LOGGER = logging.getLogger("filantropia_embassy_promote")


class PromoteError(RuntimeError):
    """Raised when an automatic or operator promotion cannot proceed."""


@dataclass(frozen=True)
class PromoteContext:
    standby_node_id: str
    new_generation: str
    previous_epoch: int
    database_container: str = "filantropia-odoo-db"
    database_name: str = "filantropia_public"
    odoo_container: str = "filantropia-odoo"
    # Docker container name for the standby public origin connector (Frank).
    origin_container: str | None = "filantropia-cloudflared"
    cloudflared_compose: Path | None = None
    # After acquire, arm local lease-guard so TTL renewals keep apex up.
    arm_lease_guard: bool = True
    lease_guard_state_path: Path | None = None
    lease_guard_enable_timer: bool = True
    lease_guard_renew_now: bool = True
    # Irreversible standby SQL promote; disable for lease-only failback handoffs.
    run_database_promote: bool = True


def _run(command: list[str], *, label: str, timeout: int = 120) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PromoteError(f"{label} did not complete") from exc
    if result.returncode:
        raise PromoteError(f"{label} failed")
    return result.stdout.strip()


def promote_database(context: PromoteContext) -> None:
    """Promote the local PostgreSQL standby after lease acquire + guard arm."""
    _run(
        [
            "docker",
            "exec",
            context.database_container,
            "psql",
            "--no-psqlrc",
            "--set=ON_ERROR_STOP=1",
            "-U",
            "odoo",
            "-d",
            context.database_name,
            "-c",
            promote_standby_sql(),
        ],
        label="PostgreSQL promote",
    )


def start_odoo_writer(context: PromoteContext) -> None:
    """Start Odoo only after DB promotion and filestore staging succeed."""
    _run(
        ["docker", "update", "--restart=unless-stopped", context.odoo_container],
        label="Odoo restart policy enable",
    )
    _run(["docker", "start", context.odoo_container], label="Odoo start")


def stop_odoo_writer(context: PromoteContext) -> None:
    """Best-effort stop of a partially started local writer."""
    try:
        _run(
            ["docker", "update", "--restart=no", context.odoo_container],
            label="Odoo restart policy disable",
        )
    except PromoteError:
        _LOGGER.exception("Could not disable Odoo restart policy during compensate")
    try:
        _run(
            ["docker", "stop", "--time", "30", context.odoo_container],
            label="Odoo stop",
            timeout=90,
        )
    except PromoteError:
        _LOGGER.exception("Could not stop Odoo during compensate")


def start_origin_connector(context: PromoteContext) -> None:
    """Start the standby origin tunnel/connector after Odoo is up."""
    if context.cloudflared_compose is not None:
        compose = context.cloudflared_compose
        _run(
            ["docker", "compose", "-f", str(compose), "up", "-d"],
            label="Origin compose up",
        )
        return
    if not context.origin_container:
        return
    _run(
        ["docker", "update", "--restart=unless-stopped", context.origin_container],
        label="Origin connector restart policy enable",
    )
    _run(["docker", "start", context.origin_container], label="Origin connector start")


def stop_origin_connector(context: PromoteContext) -> None:
    """Best-effort stop of a partially started origin connector."""
    if context.cloudflared_compose is not None:
        compose = context.cloudflared_compose
        try:
            _run(
                ["docker", "compose", "-f", str(compose), "stop"],
                label="Origin compose stop",
            )
        except PromoteError:
            _LOGGER.exception("Could not stop origin compose during compensate")
        return
    if not context.origin_container:
        return
    try:
        _run(
            ["docker", "update", "--restart=no", context.origin_container],
            label="Origin connector restart policy disable",
        )
    except PromoteError:
        _LOGGER.exception(
            "Could not disable origin connector restart policy during compensate"
        )
    try:
        _run(
            ["docker", "stop", "--time", "30", context.origin_container],
            label="Origin connector stop",
            timeout=90,
        )
    except PromoteError:
        _LOGGER.exception("Could not stop origin connector during compensate")


def acquire_writer_epoch(client, context: PromoteContext):
    """Acquire the next lease epoch for the standby node."""
    decision = client.acquire(
        node_id=context.standby_node_id,
        generation=context.new_generation,
        previous_epoch=context.previous_epoch,
    )
    if not decision.ok:
        raise PromoteError(f"Lease acquire refused: {decision.reason}")
    return decision


def _lease_guard_state_path(context: PromoteContext) -> Path:
    if context.lease_guard_state_path is not None:
        return context.lease_guard_state_path
    return Path(
        os.environ.get(
            "FILANTROPIA_LEASE_GUARD_STATE",
            "/etc/filantropia-embassy/lease-guard-state.json",
        )
    )


def _arm_guard(client, context: PromoteContext, lease) -> dict[str, object]:
    if lease.state.epoch is None:
        raise PromoteError("Lease acquire returned no epoch for guard arming")
    try:
        return arm_lease_guard_as_writer(
            client=client,
            node_id=context.standby_node_id,
            generation=context.new_generation,
            epoch=int(lease.state.epoch),
            lease_expires_at=lease.state.lease_expires_at,
            state_path=_lease_guard_state_path(context),
            enable_timer=context.lease_guard_enable_timer,
            renew_now=context.lease_guard_renew_now,
        )
    except LeaseGuardError as exc:
        raise PromoteError(
            f"Promotion acquired lease but failed to arm lease-guard: {exc}"
        ) from exc


def _compensate_partial_promotion(
    context: PromoteContext,
    *,
    writer_started: bool,
    origin_started: bool,
) -> list[str]:
    """Fail closed after a partial promote: drop local public path if raised."""
    actions: list[str] = []
    if origin_started:
        stop_origin_connector(context)
        actions.append("origin_stopped")
    if writer_started:
        stop_odoo_writer(context)
        actions.append("odoo_stopped")
    try:
        from embassy.writer_control import fence_writer

        fence_writer(reason="promote_compensate")
        actions.append("local_writer_fenced")
    except Exception as exc:
        _LOGGER.warning("Promote compensate fence failed: %s", exc)
        actions.append("local_writer_fence_failed")
    return actions


def execute_promotion(
    *,
    decision_state: str,
    client,
    context: PromoteContext,
    filestore: FilestorePromoteConfig | None = None,
    attachment_references: list[AttachmentReference] | None = None,
    fencing_proof_path: Path | None = None,
    start_writer: bool = True,
) -> dict[str, object]:
    """Run the ordered promotion sequence. Caller must already authorize it.

    Durable order (fail-closed):
    1. optional filestore stage
    2. lease acquire
    3. lease-guard arm (before irreversible DB promote and public origin)
    4. optional PostgreSQL promote
    5. optional Odoo + origin start

    Any failure after lease acquire attempts local fence and stops any services
    this call started so apex cannot linger on a non-renewing writer.
    """
    if decision_state != DecisionState.PROMOTION_AUTHORIZED.value:
        raise PromoteError("Promotion refused: decision is not PROMOTION_AUTHORIZED")

    status = client.status()
    if status.fencing_proof and fencing_proof_path is not None:
        write_fencing_proof_file(fencing_proof_path, status.fencing_proof)

    if filestore is not None:
        promote_filestore(
            filestore,
            attachment_references or [],
            require_encrypted_mount=False,
        )

    lease = None
    guard_arm: dict[str, object] | None = None
    writer_started = False
    origin_started = False
    database_promoted = False

    try:
        lease = acquire_writer_epoch(client, context)

        if context.arm_lease_guard:
            guard_arm = _arm_guard(client, context, lease)

        if context.run_database_promote:
            promote_database(context)
            database_promoted = True

        if start_writer:
            start_odoo_writer(context)
            writer_started = True
            start_origin_connector(context)
            origin_started = bool(
                context.origin_container or context.cloudflared_compose is not None
            )
    except Exception as exc:
        compensate = _compensate_partial_promotion(
            context,
            writer_started=writer_started,
            origin_started=origin_started,
        )
        _LOGGER.error(
            "Promotion failed after partial progress (db_promoted=%s, compensate=%s): %s",
            database_promoted,
            compensate,
            exc,
        )
        if isinstance(exc, PromoteError):
            raise
        raise PromoteError(f"Promotion failed: {exc}") from exc

    assert lease is not None
    result = {
        "promoted_at_utc": datetime.now(UTC).isoformat(),
        "standby_node_id": context.standby_node_id,
        "new_generation": context.new_generation,
        "epoch": lease.state.epoch,
        "phase": lease.phase.value,
        "database_promoted": database_promoted,
        "origin_started": origin_started,
        "lease_guard_armed": bool(guard_arm and guard_arm.get("armed")),
        "lease_guard": guard_arm,
    }
    _LOGGER.info("Promotion complete: %s", result)
    return result


def refresh_fencing_proof_from_status(client, *, proof_path: Path):
    """Pull the live lease fencing proof and persist it for Embassy policy."""
    try:
        decision = client.status()
    except LeaseClientError as exc:
        raise PromoteError(f"Lease status refresh failed: {exc}") from exc
    if decision.fencing_proof:
        write_fencing_proof_file(proof_path, decision.fencing_proof)
    return decision


def wait_for_acquirable_fencing_proof(
    client,
    *,
    proof_path: Path,
    timeout_seconds: float = 60.0,
    poll_seconds: float = 2.0,
):
    """Poll lease status until the fencing proof is acquirable or fail closed."""
    deadline = time.monotonic() + max(timeout_seconds, 1.0)
    last = None
    while True:
        last = refresh_fencing_proof_from_status(client, proof_path=proof_path)
        proof = last.fencing_proof or {}
        if proof.get("acquirable") is True:
            return last
        if time.monotonic() >= deadline:
            raise PromoteError("Fencing proof did not become acquirable before timeout")
        time.sleep(max(poll_seconds, 0.2))


def request_takeover_and_persist_proof(
    client,
    *,
    requester_node_id: str,
    target_node_id: str,
    target_generation: str,
    proof_path: Path,
    wait_for_acquirable: bool = True,
    acquirable_timeout_seconds: float = 60.0,
):
    """Ask the lease authority to fence the old writer and publish proof."""
    try:
        decision = client.request_takeover(
            requester_node_id=requester_node_id,
            target_node_id=target_node_id,
            target_generation=target_generation,
            reason="dual_probe_failure",
        )
    except LeaseClientError as exc:
        raise PromoteError(f"Takeover request failed: {exc}") from exc
    if not decision.ok:
        raise PromoteError(f"Takeover refused: {decision.reason}")
    if decision.fencing_proof:
        write_fencing_proof_file(proof_path, decision.fencing_proof)
    proof = decision.fencing_proof or {}
    if wait_for_acquirable and proof.get("acquirable") is not True:
        decision = wait_for_acquirable_fencing_proof(
            client,
            proof_path=proof_path,
            timeout_seconds=acquirable_timeout_seconds,
        )
    return decision
