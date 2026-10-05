"""Controlled failback as a role transition, not an old-snapshot overwrite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import logging

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
    """Stop the current writer before reseeding or switching roles."""
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
) -> dict[str, object]:
    """Documented failback steps; destructive restore remains operator-driven.

    This function fences the current writer and can perform a fenced switchover
    lease handoff. Database/filestore reseeding for the writes-occurred branch
    must be executed from verified recovery bundles under operator supervision.
    """
    fence_current_writer(reason="failback_fence")
    if plan.branch is FailbackBranch.STANDBY_WRITES_OR_UNCERTAIN:
        # Do not automatically restore bundles here.
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

    # No standby writes: keep returning host pre-outage data; only move lease back
    # after separate validation. start_writer defaults false for safety.
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
            cloudflared_compose=context.cloudflared_compose,
        ),
        start_writer=start_writer,
    )
    switched["branch"] = plan.branch.value
    switched["preserve_current_writer_data"] = False
    return switched
