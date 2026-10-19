"""Pure failover policy: ambiguous evidence must never authorize promotion."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class DecisionState(StrEnum):
    """Externally reportable Embassy states."""

    PRIMARY_HEALTHY = "primary_healthy"
    PRIMARY_DEGRADED = "primary_degraded"
    INGRESS_DEGRADED = "ingress_degraded"
    PRIMARY_UNCERTAIN = "primary_uncertain"
    PRIMARY_SUSPECT = "primary_suspect"
    OUTAGE_CANDIDATE = "outage_candidate"
    MAINTENANCE = "maintenance"
    BLOCKED_UNFENCED = "blocked_unfenced"
    BLOCKED_STANDBY = "blocked_standby"
    READY_FOR_OPERATOR = "ready_for_operator"
    PROMOTION_AUTHORIZED = "promotion_authorized"


@dataclass(frozen=True)
class PrimaryObservation:
    """One uncached observation of the configured primary."""

    reachable: bool | None
    ready: bool | None = None
    node_id: str | None = None
    generation: str | None = None
    database_is_primary: bool | None = None
    filestore_available: bool | None = None
    public_routes_ready: bool | None = None
    maintenance_active: bool = False


@dataclass(frozen=True)
class StandbyObservation:
    """Read-only health evidence collected from the local standby."""

    database_reachable: bool | None
    database_in_recovery: bool | None
    source_node_id: str | None
    source_generation: str | None
    replication_heartbeat_age_seconds: float | None
    replication_lag_bytes: int | None
    filestore_source_generation: str | None
    filestore_generation_age_seconds: float | None
    all_attachments_verified: bool | None
    code_compatible: bool | None
    status_age_seconds: float | None = None
    attachment_verification_age_seconds: float | None = None
    filestore_source_node_id: str | None = None


@dataclass(frozen=True)
class FencingEvidence:
    """Evidence emitted by an explicitly trusted, independent fence adapter."""

    target_node_id: str
    target_generation: str
    source: str
    proof_id: str
    verified_at: datetime
    expires_at: datetime
    acquirable: bool = False
    previous_epoch: int | None = None


@dataclass(frozen=True)
class Decision:
    """A policy result suitable for persistence and operator display."""

    state: DecisionState
    consecutive_primary_failures: int
    reasons: tuple[str, ...] = ()
    proposed_action: str | None = None


@dataclass(frozen=True)
class EmbassyPolicy:
    """Safety limits and identity expected for the current primary lineage."""

    primary_node_id: str
    primary_generation: str
    failure_confirmation_cycles: int = 2
    maximum_recovery_gap_seconds: float = 60.0
    replication_heartbeat_interval_seconds: float = 15.0
    maximum_filestore_generation_age_seconds: float = 60.0
    maximum_standby_status_age_seconds: float = 60.0
    maximum_attachment_verification_age_seconds: float = 60.0
    actions_enabled: bool = False
    trusted_fencing_sources: frozenset[str] = frozenset()
    require_lease_acquirable: bool = True

    def __post_init__(self) -> None:
        if not self.primary_node_id or not self.primary_generation:
            raise ValueError("Primary node and generation must be configured")
        if self.failure_confirmation_cycles < 1:
            raise ValueError("At least one primary failure confirmation is required")
        if self.maximum_recovery_gap_seconds <= 0:
            raise ValueError("Maximum recovery gap must be positive")
        if (
            self.replication_heartbeat_interval_seconds <= 0
            or self.replication_heartbeat_interval_seconds
            > self.maximum_recovery_gap_seconds
        ):
            raise ValueError(
                "Replication heartbeat interval must fit within the recovery gap"
            )
        if self.maximum_filestore_generation_age_seconds <= 0:
            raise ValueError("Maximum filestore age must be positive")
        if self.maximum_standby_status_age_seconds <= 0:
            raise ValueError("Maximum standby status age must be positive")
        if self.maximum_attachment_verification_age_seconds <= 0:
            raise ValueError("Maximum attachment verification age must be positive")


def _valid_age(age_seconds: float | None, maximum: float) -> bool:
    return age_seconds is not None and 0 <= age_seconds <= maximum


def _valid_fence(
    evidence: FencingEvidence | None,
    *,
    policy: EmbassyPolicy,
    now: datetime,
) -> bool:
    if evidence is None or evidence.source not in policy.trusted_fencing_sources:
        return False
    if not evidence.proof_id.strip():
        return False
    if (
        evidence.target_node_id != policy.primary_node_id
        or evidence.target_generation != policy.primary_generation
    ):
        return False
    evidence_times = (evidence.verified_at, evidence.expires_at, now)
    if any(
        value.tzinfo is None or value.utcoffset() is None for value in evidence_times
    ):
        return False
    if not (evidence.verified_at <= now < evidence.expires_at):
        return False
    return not (policy.require_lease_acquirable and not evidence.acquirable)


def fencing_evidence_is_valid(
    evidence: FencingEvidence | None,
    *,
    policy: EmbassyPolicy,
    now: datetime,
) -> bool:
    """Public wrapper used by the observer when refreshing lease proofs."""
    return _valid_fence(evidence, policy=policy, now=now)


def _standby_blockers(
    standby: StandbyObservation,
    *,
    policy: EmbassyPolicy,
    waive_primary_source_freshness: bool = False,
) -> tuple[str, ...]:
    """Return standby promotion blockers.

    When the independent lease fence is already valid, primary-originated
    heartbeat and filestore sync timestamps can no longer advance (the primary
    is offline). In that case require catch-up proof (WAL lag 0 + lineage +
    attachments) and waive heartbeat/filestore *age* freshness only.
    """
    blockers: list[str] = []
    if standby.database_reachable is not True:
        blockers.append("standby_database_unavailable")
    if standby.database_in_recovery is not True:
        blockers.append("standby_not_in_recovery")
    maximum_heartbeat_age = (
        policy.maximum_recovery_gap_seconds
        - policy.replication_heartbeat_interval_seconds
    )
    if not _valid_age(
        standby.status_age_seconds,
        policy.maximum_standby_status_age_seconds,
    ):
        blockers.append("standby_status_stale_or_unknown")
    if (
        standby.source_node_id != policy.primary_node_id
        or standby.source_generation != policy.primary_generation
    ):
        blockers.append("standby_lineage_mismatch")
    lag_ok = (
        not isinstance(standby.replication_lag_bytes, bool)
        and isinstance(standby.replication_lag_bytes, int)
        and standby.replication_lag_bytes == 0
    )
    if not lag_ok:
        blockers.append("replication_wal_apply_lag_nonzero_or_unknown")
    # Heartbeat rows are written on the primary and freeze after outage.
    if (not waive_primary_source_freshness or not lag_ok) and not _valid_age(
        standby.replication_heartbeat_age_seconds,
        maximum_heartbeat_age,
    ):
        blockers.append("replication_heartbeat_stale_or_unknown")
    if (
        standby.filestore_source_node_id is not None
        and standby.filestore_source_node_id != policy.primary_node_id
    ):
        blockers.append("filestore_source_node_mismatch")
    if standby.filestore_source_generation != policy.primary_generation or (
        (not waive_primary_source_freshness or not lag_ok)
        and not _valid_age(
            standby.filestore_generation_age_seconds,
            policy.maximum_filestore_generation_age_seconds,
        )
    ):
        blockers.append("filestore_generation_stale_or_unknown")
    if standby.all_attachments_verified is not True:
        blockers.append("attachment_integrity_unverified")
    if not _valid_age(
        standby.attachment_verification_age_seconds,
        policy.maximum_attachment_verification_age_seconds,
    ):
        blockers.append("attachment_verification_stale_or_unknown")
    if standby.code_compatible is not True:
        blockers.append("standby_code_incompatible")
    return tuple(blockers)


def evaluate(
    *,
    policy: EmbassyPolicy,
    primary: PrimaryObservation,
    standby: StandbyObservation,
    now: datetime,
    previous_failure_cycles: int = 0,
    fencing_evidence: FencingEvidence | None = None,
) -> Decision:
    """Evaluate one poll without performing any service, database, or route action."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Decision time must be timezone-aware")

    if primary.maintenance_active:
        return Decision(
            DecisionState.MAINTENANCE,
            0,
            ("planned_maintenance_active",),
        )

    if primary.reachable is None:
        return Decision(
            DecisionState.PRIMARY_UNCERTAIN,
            previous_failure_cycles,
            ("primary_observation_inconclusive",),
        )

    if primary.reachable:
        if (
            primary.node_id != policy.primary_node_id
            or primary.generation != policy.primary_generation
        ):
            return Decision(
                DecisionState.PRIMARY_DEGRADED,
                0,
                ("primary_identity_or_generation_mismatch",),
            )
        if (
            primary.ready is not True
            or primary.database_is_primary is not True
            or primary.filestore_available is not True
        ):
            return Decision(
                DecisionState.PRIMARY_DEGRADED,
                0,
                ("primary_readiness_or_writer_role_failed",),
            )
        if primary.public_routes_ready is False:
            return Decision(
                DecisionState.INGRESS_DEGRADED,
                0,
                ("public_ingress_unhealthy_while_primary_is_reachable",),
            )
        reasons = (
            ("public_route_probe_inconclusive",)
            if primary.public_routes_ready is None
            else ()
        )
        return Decision(DecisionState.PRIMARY_HEALTHY, 0, reasons)

    # Origin/admin path is down. Public path still up means split-path uncertainty.
    if primary.public_routes_ready is True:
        return Decision(
            DecisionState.PRIMARY_UNCERTAIN,
            previous_failure_cycles,
            ("tailnet_or_origin_down_while_public_route_serves",),
        )

    failures = previous_failure_cycles + 1
    if failures < policy.failure_confirmation_cycles:
        return Decision(
            DecisionState.PRIMARY_SUSPECT,
            failures,
            ("primary_origin_and_public_route_unreachable_confirmation_pending",),
        )

    if primary.public_routes_ready is None:
        return Decision(
            DecisionState.PRIMARY_UNCERTAIN,
            failures,
            ("public_route_probe_inconclusive_during_outage_candidate",),
        )

    # Dual failure confirmed: outage candidate. Lease fence is still required.
    if not _valid_fence(
        fencing_evidence,
        policy=policy,
        now=now,
    ):
        return Decision(
            DecisionState.OUTAGE_CANDIDATE
            if fencing_evidence is None
            else DecisionState.BLOCKED_UNFENCED,
            failures,
            (
                "dual_probe_failure_confirmed",
                "positive_independent_fencing_evidence_missing_or_invalid",
            ),
            proposed_action=(
                "request_lease_takeover" if fencing_evidence is None else None
            ),
        )

    # Lease fence proves the old writer is excluded; primary heartbeats/filestore
    # pulls cannot refresh until after promote. Waive those ages when caught up.
    blockers = _standby_blockers(
        standby,
        policy=policy,
        waive_primary_source_freshness=True,
    )
    if blockers:
        return Decision(
            DecisionState.BLOCKED_STANDBY,
            failures,
            ("dual_probe_failure_confirmed", *blockers),
        )

    if not policy.actions_enabled:
        return Decision(
            DecisionState.READY_FOR_OPERATOR,
            failures,
            ("dual_probe_failure_confirmed", "automatic_actions_disabled"),
            proposed_action="promote",
        )

    return Decision(
        DecisionState.PROMOTION_AUTHORIZED,
        failures,
        ("all_configured_promotion_gates_passed",),
        proposed_action="promote",
    )
