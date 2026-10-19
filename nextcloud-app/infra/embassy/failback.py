"""Controlled failback as a role transition, not an old-snapshot overwrite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import logging
import os

from embassy.promote import PromoteContext, PromoteError, execute_promotion
from embassy.writer_control import WriterControlError, fence_writer

_LOGGER = logging.getLogger("filantropia_embassy_failback")


class FailbackBranch(StrEnum):
    NO_STANDBY_WRITES = "no_standby_writes"
    STANDBY_WRITES_OR_UNCERTAIN = "standby_writes_or_uncertain"


@dataclass(frozen=True)
class FailbackPlan:
    branch: FailbackBranch
    current_writer_node_id: str
    returning_node_id: str
    returning_generation: str
    previous_epoch: int
    preserve_current_writer_data: bool


def plan_failback(
    *,
    frank_accepted_writes: bool | None,
    current_writer_node_id: str = "frank",
    returning_node_id: str = "trl5",
    returning_generation: str,
    previous_epoch: int,
) -> FailbackPlan:
    """Choose the failback branch from write-status evidence."""
    if frank_accepted_writes is False:
        branch = FailbackBranch.NO_STANDBY_WRITES
        preserve = False
    else:
        branch = FailbackBranch.STANDBY_WRITES_OR_UNCERTAIN
        preserve = True
    return FailbackPlan(
        branch=branch,
        current_writer_node_id=current_writer_node_id,
        returning_node_id=returning_node_id,
        returning_generation=returning_generation,
        previous_epoch=previous_epoch,
        preserve_current_writer_data=preserve,
    )


def fence_current_writer(*, reason: str = "failback_fence") -> None:
    """Stop the *local* writer only; does not prove a remote host is fenced."""
    try:
        fence_writer(reason=reason)
    except WriterControlError as exc:
        raise PromoteError(f"Failback fence failed: {exc}") from exc


def execute_failback(
    *,
    plan: FailbackPlan,
    client,
    context: PromoteContext,
    start_writer: bool = False,
    allow_destructive_execute: bool = False,
    confirm_remote_writer_fenced: bool = False,
    confirm_local_host_is_returning_node: bool = False,
) -> dict[str, object]:
    """Documented failback steps; destructive restore remains operator-driven.

    Safety gates (all required for any execute path):
    - ``allow_destructive_execute`` must be True (default False).
    - ``confirm_remote_writer_fenced`` must be True — operator attestation that
      the *current* writer (e.g. Frank) is stopped/fenced; local
      ``fence_current_writer`` alone is not multi-host proof.
    - ``confirm_local_host_is_returning_node`` must be True and the process
      identity (``FS_EMBASSY_NODE_ID``) must match ``plan.returning_node_id``.

    The NO_STANDBY_WRITES branch performs a **lease-only** handoff by default
    (no ``pg_promote``), because the returning host is expected to already hold
    pre-outage primary data. STANDBY_WRITES_OR_UNCERTAIN always pauses for
    operator reseed and never auto-promotes.
    """
    if not allow_destructive_execute:
        raise PromoteError(
            "execute_failback refused: set allow_destructive_execute=True only "
            "after following docs/ops/EMBASSY-FAILBACK-ANTI-RACE.md"
        )
    if not confirm_remote_writer_fenced:
        raise PromoteError(
            "execute_failback refused: confirm_remote_writer_fenced=True is "
            "required (local Docker fence is not remote proof)"
        )
    if not confirm_local_host_is_returning_node:
        raise PromoteError(
            "execute_failback refused: confirm_local_host_is_returning_node=True "
            "is required so the wrong host cannot claim the lease"
        )
    local_node = os.environ.get("FS_EMBASSY_NODE_ID", "").strip()
    if local_node != plan.returning_node_id:
        raise PromoteError(
            "execute_failback refused: FS_EMBASSY_NODE_ID does not match "
            f"returning_node_id={plan.returning_node_id!r}"
        )

    # Local fence is still useful on the returning host if it was a degraded
    # dual-start attempt; it does not replace remote writer attestation.
    fence_current_writer(reason="failback_fence")
    if plan.branch is FailbackBranch.STANDBY_WRITES_OR_UNCERTAIN:
        result = {
            "failback_at_utc": datetime.now(UTC).isoformat(),
            "branch": plan.branch.value,
            "status": "awaiting_operator_reseed_and_validation",
            "preserve_current_writer_data": True,
            "note": (
                "Preserve Frank authoritative DB+filestore, reseed returning host "
                "from verified Frank-originated pair, validate, then switch lease."
            ),
        }
        _LOGGER.warning("Failback paused for operator reseed: %s", result)
        return result

    # No standby writes: keep returning host pre-outage data; lease-only switch.
    # start_writer defaults false for safety.
    switched = execute_promotion(
        decision_state="promotion_authorized",
        client=client,
        context=PromoteContext(
            standby_node_id=plan.returning_node_id,
            new_generation=plan.returning_generation,
            previous_epoch=plan.previous_epoch,
            database_container=context.database_container,
            database_name=context.database_name,
            odoo_container=context.odoo_container,
            origin_container=context.origin_container,
            cloudflared_compose=context.cloudflared_compose,
            arm_lease_guard=context.arm_lease_guard,
            lease_guard_state_path=context.lease_guard_state_path,
            lease_guard_enable_timer=context.lease_guard_enable_timer,
            lease_guard_renew_now=context.lease_guard_renew_now,
            run_database_promote=False,
        ),
        start_writer=start_writer,
    )
    switched["branch"] = plan.branch.value
    switched["preserve_current_writer_data"] = False
    switched["database_promote_skipped"] = True
    return switched
