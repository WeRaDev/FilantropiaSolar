"""Cooperative software-lease protocol for single-writer Odoo ownership.

This module is the shared source of truth for epoch/lease transitions. The
Cloudflare Durable Object worker and the in-process test authority both call
into these pure functions. A lease is not physical fencing: the active host
must still stop local writers when renewal is refused or the lease expires.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any


class LeaseError(ValueError):
    """Raised for malformed lease requests or impossible state transitions."""


class LeasePhase(StrEnum):
    """High-level ownership phase visible to Embassy and the public Worker."""

    UNOWNED = "unowned"
    ACTIVE = "active"
    TAKEOVER_PENDING = "takeover_pending"
    DRAINING = "draining"
    ACQUIRABLE = "acquirable"


@dataclass(frozen=True)
class LeaseState:
    """Durable ownership record. Never cache this outside the authority."""

    schema_version: int
    owner_node_id: str | None
    epoch: int
    generation: str | None
    lease_expires_at: datetime | None
    takeover_pending: bool
    takeover_requested_at: datetime | None
    previous_owner_node_id: str | None
    previous_epoch: int | None
    previous_generation: str | None
    self_fence_grace_until: datetime | None
    in_flight_drain_until: datetime | None
    proof_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "owner_node_id": self.owner_node_id,
            "epoch": self.epoch,
            "generation": self.generation,
            "lease_expires_at": _iso(self.lease_expires_at),
            "takeover_pending": self.takeover_pending,
            "takeover_requested_at": _iso(self.takeover_requested_at),
            "previous_owner_node_id": self.previous_owner_node_id,
            "previous_epoch": self.previous_epoch,
            "previous_generation": self.previous_generation,
            "self_fence_grace_until": _iso(self.self_fence_grace_until),
            "in_flight_drain_until": _iso(self.in_flight_drain_until),
            "proof_id": self.proof_id,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> LeaseState:
        if value.get("schema_version") != 1:
            raise LeaseError("Unsupported lease schema")
        return cls(
            schema_version=1,
            owner_node_id=_optional_str(value.get("owner_node_id")),
            epoch=_required_nonneg_int(value.get("epoch"), field="epoch"),
            generation=_optional_str(value.get("generation")),
            lease_expires_at=_optional_datetime(value.get("lease_expires_at")),
            takeover_pending=bool(value.get("takeover_pending", False)),
            takeover_requested_at=_optional_datetime(
                value.get("takeover_requested_at")
            ),
            previous_owner_node_id=_optional_str(value.get("previous_owner_node_id")),
            previous_epoch=_optional_nonneg_int(value.get("previous_epoch")),
            previous_generation=_optional_str(value.get("previous_generation")),
            self_fence_grace_until=_optional_datetime(
                value.get("self_fence_grace_until")
            ),
            in_flight_drain_until=_optional_datetime(
                value.get("in_flight_drain_until")
            ),
            proof_id=_optional_str(value.get("proof_id")),
        )


@dataclass(frozen=True)
class LeasePolicy:
    """Timing knobs for renewals, drains, and self-fence grace."""

    lease_ttl_seconds: float = 30.0
    renew_before_seconds: float = 10.0
    in_flight_drain_seconds: float = 5.0
    self_fence_grace_seconds: float = 15.0
    source_name: str = "cloudflare-durable-object-lease"

    def __post_init__(self) -> None:
        if self.lease_ttl_seconds <= 0:
            raise LeaseError("lease_ttl_seconds must be positive")
        if not 0 < self.renew_before_seconds < self.lease_ttl_seconds:
            raise LeaseError("renew_before_seconds must fit inside the lease TTL")
        if self.in_flight_drain_seconds < 0 or self.self_fence_grace_seconds < 0:
            raise LeaseError("drain and self-fence grace must be non-negative")
        if not self.source_name.strip():
            raise LeaseError("source_name is required")


@dataclass(frozen=True)
class LeaseDecision:
    """Result returned by the authority for one mutation or query."""

    ok: bool
    state: LeaseState
    phase: LeasePhase
    reason: str
    fencing_proof: dict[str, object] | None = None
    request_permit: bool = False


def empty_lease_state() -> LeaseState:
    """Initial unowned authority state."""
    return LeaseState(
        schema_version=1,
        owner_node_id=None,
        epoch=0,
        generation=None,
        lease_expires_at=None,
        takeover_pending=False,
        takeover_requested_at=None,
        previous_owner_node_id=None,
        previous_epoch=None,
        previous_generation=None,
        self_fence_grace_until=None,
        in_flight_drain_until=None,
        proof_id=None,
    )


def phase_of(state: LeaseState, *, now: datetime) -> LeasePhase:
    """Classify the durable state relative to wall clock."""
    _require_aware(now)
    if state.takeover_pending:
        if _ready_to_acquire(state, now=now):
            return LeasePhase.ACQUIRABLE
        if (
            state.in_flight_drain_until is not None
            and now < state.in_flight_drain_until
        ):
            return LeasePhase.DRAINING
        return LeasePhase.TAKEOVER_PENDING
    if state.owner_node_id and state.lease_expires_at and now < state.lease_expires_at:
        return LeasePhase.ACTIVE
    if state.owner_node_id and state.lease_expires_at and now >= state.lease_expires_at:
        return LeasePhase.ACQUIRABLE
    return LeasePhase.UNOWNED


def bootstrap_owner(
    state: LeaseState,
    *,
    node_id: str,
    generation: str,
    now: datetime,
    policy: LeasePolicy,
) -> LeaseDecision:
    """Grant the first epoch when the authority is empty."""
    _require_identity(node_id, generation)
    _require_aware(now)
    current = phase_of(state, now=now)
    if (
        state.owner_node_id
        or state.takeover_pending
        or current not in {LeasePhase.UNOWNED, LeasePhase.ACQUIRABLE}
    ):
        return LeaseDecision(
            ok=False,
            state=state,
            phase=current,
            reason="authority_not_empty_for_bootstrap",
        )
    next_state = LeaseState(
        schema_version=1,
        owner_node_id=node_id,
        epoch=max(state.epoch, 0) + 1,
        generation=generation,
        lease_expires_at=now + timedelta(seconds=policy.lease_ttl_seconds),
        takeover_pending=False,
        takeover_requested_at=None,
        previous_owner_node_id=None,
        previous_epoch=None,
        previous_generation=None,
        self_fence_grace_until=None,
        in_flight_drain_until=None,
        proof_id=None,
    )
    return LeaseDecision(
        ok=True,
        state=next_state,
        phase=LeasePhase.ACTIVE,
        reason="bootstrap_granted",
        request_permit=True,
    )


def renew_lease(
    state: LeaseState,
    *,
    node_id: str,
    epoch: int,
    generation: str,
    readiness_ok: bool,
    now: datetime,
    policy: LeasePolicy,
) -> LeaseDecision:
    """Extend the active owner's lease when readiness still passes."""
    _require_identity(node_id, generation)
    _require_aware(now)
    current = phase_of(state, now=now)
    if not readiness_ok:
        return LeaseDecision(
            ok=False,
            state=state,
            phase=current,
            reason="local_readiness_failed",
        )
    if state.takeover_pending:
        return LeaseDecision(
            ok=False,
            state=state,
            phase=current,
            reason="takeover_pending_renewal_refused",
        )
    if (
        state.owner_node_id != node_id
        or state.epoch != epoch
        or state.generation != generation
        or state.lease_expires_at is None
        or now >= state.lease_expires_at
    ):
        return LeaseDecision(
            ok=False,
            state=state,
            phase=current,
            reason="not_current_owner_or_lease_expired",
        )
    next_state = replace(
        state,
        lease_expires_at=now + timedelta(seconds=policy.lease_ttl_seconds),
    )
    return LeaseDecision(
        ok=True,
        state=next_state,
        phase=LeasePhase.ACTIVE,
        reason="lease_renewed",
        request_permit=True,
    )


def request_takeover(
    state: LeaseState,
    *,
    requester_node_id: str,
    target_node_id: str,
    target_generation: str,
    now: datetime,
    policy: LeasePolicy,
    reason: str = "dual_probe_failure",
) -> LeaseDecision:
    """Mark takeover pending and stop renewals for the current owner."""
    del reason  # retained for journal callers; authority stores timestamps only
    if not requester_node_id.strip() or requester_node_id == target_node_id:
        raise LeaseError("Takeover requester must be a different node")
    _require_identity(target_node_id, target_generation)
    _require_aware(now)
    current = phase_of(state, now=now)
    if state.takeover_pending:
        if (
            state.previous_owner_node_id == target_node_id
            and state.previous_generation == target_generation
        ):
            return LeaseDecision(
                ok=True,
                state=state,
                phase=current,
                reason="takeover_already_pending",
                fencing_proof=_fencing_proof(state, policy=policy, now=now),
            )
        return LeaseDecision(
            ok=False,
            state=state,
            phase=current,
            reason="conflicting_takeover_pending",
        )
    if state.owner_node_id is None:
        return LeaseDecision(
            ok=False,
            state=state,
            phase=current,
            reason="no_active_owner_to_take_over",
        )
    if state.owner_node_id != target_node_id or state.generation != target_generation:
        return LeaseDecision(
            ok=False,
            state=state,
            phase=current,
            reason="takeover_target_mismatch",
        )

    lease_deadline = state.lease_expires_at or now
    drain_until = now + timedelta(seconds=policy.in_flight_drain_seconds)
    grace_until = max(lease_deadline, now) + timedelta(
        seconds=policy.self_fence_grace_seconds
    )
    proof_id = f"lease-takeover-{state.epoch}-{int(now.timestamp())}"
    next_state = LeaseState(
        schema_version=1,
        owner_node_id=None,
        epoch=state.epoch,
        generation=None,
        lease_expires_at=lease_deadline,
        takeover_pending=True,
        takeover_requested_at=now,
        previous_owner_node_id=state.owner_node_id,
        previous_epoch=state.epoch,
        previous_generation=state.generation,
        self_fence_grace_until=grace_until,
        in_flight_drain_until=drain_until,
        proof_id=proof_id,
    )
    phase = phase_of(next_state, now=now)
    return LeaseDecision(
        ok=True,
        state=next_state,
        phase=phase,
        reason="takeover_pending",
        fencing_proof=_fencing_proof(next_state, policy=policy, now=now),
        request_permit=False,
    )


def acquire_lease(
    state: LeaseState,
    *,
    node_id: str,
    generation: str,
    previous_epoch: int,
    now: datetime,
    policy: LeasePolicy,
) -> LeaseDecision:
    """Grant the next epoch after drain + self-fence grace complete."""
    _require_identity(node_id, generation)
    _require_aware(now)
    current = phase_of(state, now=now)
    if not _ready_to_acquire(state, now=now):
        return LeaseDecision(
            ok=False,
            state=state,
            phase=current,
            reason="lease_not_yet_acquirable",
        )
    if state.takeover_pending:
        if state.previous_epoch != previous_epoch:
            return LeaseDecision(
                ok=False,
                state=state,
                phase=current,
                reason="previous_epoch_mismatch",
            )
        if node_id == state.previous_owner_node_id:
            return LeaseDecision(
                ok=False,
                state=state,
                phase=current,
                reason="previous_owner_cannot_reacquire_during_takeover",
            )
    elif state.owner_node_id is not None and state.epoch != previous_epoch:
        return LeaseDecision(
            ok=False,
            state=state,
            phase=current,
            reason="previous_epoch_mismatch",
        )

    next_state = LeaseState(
        schema_version=1,
        owner_node_id=node_id,
        epoch=state.epoch + 1,
        generation=generation,
        lease_expires_at=now + timedelta(seconds=policy.lease_ttl_seconds),
        takeover_pending=False,
        takeover_requested_at=None,
        previous_owner_node_id=None,
        previous_epoch=None,
        previous_generation=None,
        self_fence_grace_until=None,
        in_flight_drain_until=None,
        proof_id=None,
    )
    return LeaseDecision(
        ok=True,
        state=next_state,
        phase=LeasePhase.ACTIVE,
        reason="lease_acquired",
        request_permit=True,
    )


def request_permit(
    state: LeaseState,
    *,
    origin_node_id: str,
    epoch: int,
    now: datetime,
) -> LeaseDecision:
    """Decide whether the public Worker may proxy to a host origin."""
    _require_aware(now)
    current = phase_of(state, now=now)
    allowed = (
        current == LeasePhase.ACTIVE
        and state.owner_node_id == origin_node_id
        and state.epoch == epoch
        and state.lease_expires_at is not None
        and now < state.lease_expires_at
        and not state.takeover_pending
    )
    return LeaseDecision(
        ok=allowed,
        state=state,
        phase=current,
        reason="permit_granted" if allowed else "permit_denied",
        request_permit=allowed,
    )


def status(state: LeaseState, *, now: datetime, policy: LeasePolicy) -> LeaseDecision:
    """Read-only classification plus optional fence proof during takeover."""
    current = phase_of(state, now=now)
    proof = None
    if state.takeover_pending or current == LeasePhase.ACQUIRABLE:
        proof = _fencing_proof(state, policy=policy, now=now)
    return LeaseDecision(
        ok=True,
        state=state,
        phase=current,
        reason="status",
        fencing_proof=proof,
        request_permit=current == LeasePhase.ACTIVE,
    )


class InMemoryLeaseAuthority:
    """Process-local authority for unit tests and isolated lab rehearsal."""

    def __init__(self, policy: LeasePolicy | None = None) -> None:
        self.policy = policy or LeasePolicy()
        self._state = empty_lease_state()

    @property
    def state(self) -> LeaseState:
        return self._state

    def bootstrap(
        self, *, node_id: str, generation: str, now: datetime
    ) -> LeaseDecision:
        decision = bootstrap_owner(
            self._state,
            node_id=node_id,
            generation=generation,
            now=now,
            policy=self.policy,
        )
        if decision.ok:
            self._state = decision.state
        return decision

    def renew(
        self,
        *,
        node_id: str,
        epoch: int,
        generation: str,
        readiness_ok: bool,
        now: datetime,
    ) -> LeaseDecision:
        decision = renew_lease(
            self._state,
            node_id=node_id,
            epoch=epoch,
            generation=generation,
            readiness_ok=readiness_ok,
            now=now,
            policy=self.policy,
        )
        if decision.ok:
            self._state = decision.state
        return decision

    def request_takeover(
        self,
        *,
        requester_node_id: str,
        target_node_id: str,
        target_generation: str,
        now: datetime,
        reason: str = "dual_probe_failure",
    ) -> LeaseDecision:
        decision = request_takeover(
            self._state,
            requester_node_id=requester_node_id,
            target_node_id=target_node_id,
            target_generation=target_generation,
            now=now,
            policy=self.policy,
            reason=reason,
        )
        if decision.ok:
            self._state = decision.state
        return decision

    def acquire(
        self,
        *,
        node_id: str,
        generation: str,
        previous_epoch: int,
        now: datetime,
    ) -> LeaseDecision:
        decision = acquire_lease(
            self._state,
            node_id=node_id,
            generation=generation,
            previous_epoch=previous_epoch,
            now=now,
            policy=self.policy,
        )
        if decision.ok:
            self._state = decision.state
        return decision

    def permit(
        self,
        *,
        origin_node_id: str,
        epoch: int,
        now: datetime,
    ) -> LeaseDecision:
        return request_permit(
            self._state,
            origin_node_id=origin_node_id,
            epoch=epoch,
            now=now,
        )

    def status(self, *, now: datetime) -> LeaseDecision:
        return status(self._state, now=now, policy=self.policy)


def _fencing_proof(
    state: LeaseState,
    *,
    policy: LeasePolicy,
    now: datetime,
) -> dict[str, object] | None:
    if not state.previous_owner_node_id or not state.previous_generation:
        return None
    if not state.proof_id:
        return None
    expires = state.self_fence_grace_until or state.lease_expires_at or now
    verified = state.takeover_requested_at or now
    return {
        "schema_version": 1,
        "target_node_id": state.previous_owner_node_id,
        "target_generation": state.previous_generation,
        "source": policy.source_name,
        "proof_id": state.proof_id,
        "verified_at_utc": _iso(verified),
        "expires_at_utc": _iso(expires + timedelta(seconds=policy.lease_ttl_seconds)),
        "previous_epoch": state.previous_epoch,
        "phase": phase_of(state, now=now).value,
        "acquirable": _ready_to_acquire(state, now=now),
    }


def _ready_to_acquire(state: LeaseState, *, now: datetime) -> bool:
    if state.takeover_pending:
        lease_done = state.lease_expires_at is None or now >= state.lease_expires_at
        drain_done = (
            state.in_flight_drain_until is None or now >= state.in_flight_drain_until
        )
        grace_done = (
            state.self_fence_grace_until is None or now >= state.self_fence_grace_until
        )
        return lease_done and drain_done and grace_done
    return (
        state.owner_node_id is not None
        and state.lease_expires_at is not None
        and now >= state.lease_expires_at
    )


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LeaseError("Timestamps must be timezone-aware")


def _require_identity(node_id: str, generation: str) -> None:
    if not node_id.strip() or not generation.strip():
        raise LeaseError("node_id and generation are required")
    if "REPLACE_WITH" in generation:
        raise LeaseError("generation placeholder is not allowed")


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _required_nonneg_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LeaseError(f"{field} must be a non-negative integer")
    return value


def _optional_nonneg_int(value: object) -> int | None:
    if value is None:
        return None
    return _required_nonneg_int(value, field="optional_int")


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        _require_aware(value)
        return value.astimezone(UTC)
    if not isinstance(value, str) or not value:
        raise LeaseError("Invalid datetime value")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require_aware(parsed)
    return parsed.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
