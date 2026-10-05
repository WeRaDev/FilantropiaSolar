"""Fail-closed promotion actions after lease fencing and standby validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import os
from pathlib import Path
import subprocess

from embassy.filestore_promote import FilestorePromoteConfig, promote_filestore
from embassy.lease_client import LeaseClientError, write_fencing_proof_file
from embassy.policy import DecisionState
from embassy.replication import AttachmentReference
from embassy.replication_bootstrap import promote_standby_sql

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
    cloudflared_compose: Path | None = None


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
    """Promote the local PostgreSQL standby after fencing gates pass."""
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
    """Run the ordered promotion sequence. Caller must already authorize it."""
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

    promote_database(context)
    lease = acquire_writer_epoch(client, context)
    if start_writer:
        start_odoo_writer(context)

    result = {
        "promoted_at_utc": datetime.now(UTC).isoformat(),
        "standby_node_id": context.standby_node_id,
        "new_generation": context.new_generation,
        "epoch": lease.state.epoch,
        "phase": lease.phase.value,
    }
    _LOGGER.info("Promotion complete: %s", result)
    return result


def request_takeover_and_persist_proof(
    client,
    *,
    requester_node_id: str,
    target_node_id: str,
    target_generation: str,
    proof_path: Path,
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
    return decision
