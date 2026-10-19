"""Unit tests for fail-closed Embassy decisions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from embassy.policy import (
    DecisionState,
    EmbassyPolicy,
    FencingEvidence,
    PrimaryObservation,
    StandbyObservation,
    evaluate,
)

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _policy(**overrides):
    values = {
        "primary_node_id": "trl5",
        "primary_generation": "generation-7",
        "trusted_fencing_sources": frozenset(
            {"provider-power-fence", "cloudflare-durable-object-lease"}
        ),
        "require_lease_acquirable": False,
    }
    values.update(overrides)
    return EmbassyPolicy(**values)


def _healthy_primary(**overrides):
    values = {
        "reachable": True,
        "ready": True,
        "node_id": "trl5",
        "generation": "generation-7",
        "database_is_primary": True,
        "filestore_available": True,
        "public_routes_ready": True,
    }
    values.update(overrides)
    return PrimaryObservation(**values)


def _ready_standby(**overrides):
    values = {
        "database_reachable": True,
        "database_in_recovery": True,
        "source_node_id": "trl5",
        "source_generation": "generation-7",
        "replication_heartbeat_age_seconds": 15.0,
        "replication_lag_bytes": 0,
        "filestore_source_generation": "generation-7",
        "filestore_generation_age_seconds": 5.0,
        "all_attachments_verified": True,
        "code_compatible": True,
        "status_age_seconds": 5.0,
        "attachment_verification_age_seconds": 5.0,
    }
    values.update(overrides)
    return StandbyObservation(**values)


def _fence(**overrides):
    values = {
        "target_node_id": "trl5",
        "target_generation": "generation-7",
        "source": "provider-power-fence",
        "proof_id": "fence-20261001-1200",
        "verified_at": NOW - timedelta(seconds=5),
        "expires_at": NOW + timedelta(seconds=30),
        "acquirable": True,
    }
    values.update(overrides)
    return FencingEvidence(**values)


def _down_primary(**overrides):
    values = {"reachable": False, "public_routes_ready": False}
    values.update(overrides)
    return PrimaryObservation(**values)


class EmbassyPolicyTests(unittest.TestCase):
    def test_healthy_primary_never_depends_on_standby_or_actions(self):
        decision = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_healthy_primary(),
            standby=_ready_standby(database_reachable=False),
            now=NOW,
        )

        self.assertEqual(decision.state, DecisionState.PRIMARY_HEALTHY)
        self.assertIsNone(decision.proposed_action)
        self.assertEqual(decision.consecutive_primary_failures, 0)

    def test_reachable_but_degraded_primary_does_not_trigger_promotion(self):
        decision = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_healthy_primary(ready=False),
            standby=_ready_standby(),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(),
        )

        self.assertEqual(decision.state, DecisionState.PRIMARY_DEGRADED)
        self.assertIsNone(decision.proposed_action)
        self.assertEqual(decision.consecutive_primary_failures, 0)

    def test_public_edge_failure_is_not_classified_as_writer_failure(self):
        decision = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_healthy_primary(public_routes_ready=False),
            standby=_ready_standby(),
            now=NOW,
            fencing_evidence=_fence(),
        )

        self.assertEqual(decision.state, DecisionState.INGRESS_DEGRADED)
        self.assertIsNone(decision.proposed_action)

    def test_inconclusive_observation_does_not_increment_failure_count(self):
        decision = evaluate(
            policy=_policy(),
            primary=PrimaryObservation(reachable=None),
            standby=_ready_standby(),
            now=NOW,
            previous_failure_cycles=1,
        )

        self.assertEqual(decision.state, DecisionState.PRIMARY_UNCERTAIN)
        self.assertEqual(decision.consecutive_primary_failures, 1)
        self.assertIsNone(decision.proposed_action)

    def test_first_unreachable_cycle_only_marks_primary_suspect(self):
        decision = evaluate(
            policy=_policy(),
            primary=_down_primary(),
            standby=_ready_standby(),
            now=NOW,
        )

        self.assertEqual(decision.state, DecisionState.PRIMARY_SUSPECT)
        self.assertEqual(decision.consecutive_primary_failures, 1)
        self.assertIsNone(decision.proposed_action)

    def test_unreachable_primary_without_positive_fence_is_outage_candidate(self):
        decision = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_down_primary(),
            standby=_ready_standby(),
            now=NOW,
            previous_failure_cycles=1,
        )

        self.assertEqual(decision.state, DecisionState.OUTAGE_CANDIDATE)
        self.assertEqual(decision.proposed_action, "request_lease_takeover")

    def test_expired_or_wrong_identity_fence_is_rejected(self):
        for evidence in (
            _fence(expires_at=NOW),
            _fence(target_generation="generation-6"),
            _fence(source="http-probe"),
        ):
            with self.subTest(evidence=evidence):
                decision = evaluate(
                    policy=_policy(actions_enabled=True),
                    primary=_down_primary(),
                    standby=_ready_standby(),
                    now=NOW,
                    previous_failure_cycles=1,
                    fencing_evidence=evidence,
                )
                self.assertEqual(decision.state, DecisionState.BLOCKED_UNFENCED)
                self.assertIsNone(decision.proposed_action)

    def test_stale_standby_local_evidence_still_blocks_after_valid_fence(self):
        # Primary-originated heartbeat age freezes after outage and is waived once
        # the lease fence is valid and WAL lag is 0. Standby-local freshness and
        # attachment integrity remain hard gates.
        decision = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_down_primary(),
            standby=_ready_standby(
                replication_heartbeat_age_seconds=61.0,
                filestore_generation_age_seconds=120.0,
                all_attachments_verified=False,
                status_age_seconds=61.0,
                attachment_verification_age_seconds=61.0,
            ),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(),
        )

        self.assertEqual(decision.state, DecisionState.BLOCKED_STANDBY)
        self.assertNotIn("replication_heartbeat_stale_or_unknown", decision.reasons)
        self.assertNotIn("filestore_generation_stale_or_unknown", decision.reasons)
        self.assertIn("standby_status_stale_or_unknown", decision.reasons)
        self.assertIn("attachment_integrity_unverified", decision.reasons)
        self.assertIn(
            "attachment_verification_stale_or_unknown",
            decision.reasons,
        )
        self.assertIsNone(decision.proposed_action)

    def test_valid_fence_waives_frozen_primary_source_ages_when_lag_is_zero(self):
        decision = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_down_primary(),
            standby=_ready_standby(
                replication_heartbeat_age_seconds=900.0,
                filestore_generation_age_seconds=900.0,
                replication_lag_bytes=0,
            ),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(),
        )

        self.assertEqual(decision.state, DecisionState.PROMOTION_AUTHORIZED)
        self.assertEqual(decision.proposed_action, "promote")

    def test_stale_primary_source_ages_still_block_when_wal_lag_nonzero(self):
        decision = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_down_primary(),
            standby=_ready_standby(
                replication_heartbeat_age_seconds=900.0,
                filestore_generation_age_seconds=900.0,
                replication_lag_bytes=1,
            ),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(),
        )

        self.assertEqual(decision.state, DecisionState.BLOCKED_STANDBY)
        self.assertIn(
            "replication_wal_apply_lag_nonzero_or_unknown",
            decision.reasons,
        )
        self.assertIn("replication_heartbeat_stale_or_unknown", decision.reasons)
        self.assertIn("filestore_generation_stale_or_unknown", decision.reasons)

    def test_heartbeat_age_budget_applies_only_before_valid_lease_fence(self):
        # Without a valid fence the outage path never reaches standby blockers;
        # with a fence and lag=0 the primary heartbeat age is waived. The RPO
        # heartbeat budget is therefore enforced only while lag is nonzero.
        authorized = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_down_primary(),
            standby=_ready_standby(replication_heartbeat_age_seconds=46.0),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(),
        )
        blocked_with_lag = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_down_primary(),
            standby=_ready_standby(
                replication_heartbeat_age_seconds=46.0,
                replication_lag_bytes=1,
            ),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(),
        )

        self.assertEqual(authorized.state, DecisionState.PROMOTION_AUTHORIZED)
        self.assertEqual(blocked_with_lag.state, DecisionState.BLOCKED_STANDBY)
        self.assertIn(
            "replication_heartbeat_stale_or_unknown",
            blocked_with_lag.reasons,
        )

    def test_unknown_or_unapplied_received_wal_blocks_promotion(self):
        for lag_bytes in (None, 1):
            with self.subTest(lag_bytes=lag_bytes):
                decision = evaluate(
                    policy=_policy(actions_enabled=True),
                    primary=_down_primary(),
                    standby=_ready_standby(replication_lag_bytes=lag_bytes),
                    now=NOW,
                    previous_failure_cycles=1,
                    fencing_evidence=_fence(),
                )

                self.assertEqual(decision.state, DecisionState.BLOCKED_STANDBY)
                self.assertIn(
                    "replication_wal_apply_lag_nonzero_or_unknown",
                    decision.reasons,
                )

    def test_complete_evidence_with_default_policy_remains_operator_gated(self):
        decision = evaluate(
            policy=_policy(),
            primary=_down_primary(),
            standby=_ready_standby(),
            now=NOW,
            previous_failure_cycles=1,
fencing_evidence=_fence(),
        )

        self.assertEqual(decision.state, DecisionState.READY_FOR_OPERATOR)
        self.assertEqual(
            decision.reasons,
            ("dual_probe_failure_confirmed", "automatic_actions_disabled"),
        )
        self.assertEqual(decision.proposed_action, "promote")

    def test_promotion_is_only_authorized_when_every_gate_is_enabled_and_valid(self):
        decision = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_down_primary(),
            standby=_ready_standby(),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(),
        )

        self.assertEqual(decision.state, DecisionState.PROMOTION_AUTHORIZED)
        self.assertEqual(decision.proposed_action, "promote")

    def test_planned_maintenance_suppresses_outage_classification(self):
        decision = evaluate(
            policy=_policy(actions_enabled=True),
            primary=PrimaryObservation(
                reachable=False,
                maintenance_active=True,
            ),
            standby=_ready_standby(),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(),
        )

        self.assertEqual(decision.state, DecisionState.MAINTENANCE)
        self.assertEqual(decision.consecutive_primary_failures, 0)
        self.assertIsNone(decision.proposed_action)


    def test_tailnet_down_public_up_blocks_promotion(self):
        decision = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_down_primary(public_routes_ready=True),
            standby=_ready_standby(),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(),
        )
        self.assertEqual(decision.state, DecisionState.PRIMARY_UNCERTAIN)
        self.assertIsNone(decision.proposed_action)

    def test_software_lease_requires_acquirable_proof(self):
        blocked = evaluate(
            policy=_policy(
                actions_enabled=True,
                require_lease_acquirable=True,
                trusted_fencing_sources=frozenset({"cloudflare-durable-object-lease"}),
            ),
            primary=_down_primary(),
            standby=_ready_standby(),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(
                source="cloudflare-durable-object-lease",
                acquirable=False,
            ),
        )
        allowed = evaluate(
            policy=_policy(
                actions_enabled=True,
                require_lease_acquirable=True,
                trusted_fencing_sources=frozenset({"cloudflare-durable-object-lease"}),
            ),
            primary=_down_primary(),
            standby=_ready_standby(),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(
                source="cloudflare-durable-object-lease",
                acquirable=True,
            ),
        )
        self.assertEqual(blocked.state, DecisionState.BLOCKED_UNFENCED)
        self.assertEqual(allowed.state, DecisionState.PROMOTION_AUTHORIZED)

    def test_filestore_source_node_mismatch_blocks_standby(self):
        decision = evaluate(
            policy=_policy(actions_enabled=True),
            primary=_down_primary(),
            standby=_ready_standby(filestore_source_node_id="other-node"),
            now=NOW,
            previous_failure_cycles=1,
            fencing_evidence=_fence(),
        )
        self.assertEqual(decision.state, DecisionState.BLOCKED_STANDBY)
        self.assertIn("filestore_source_node_mismatch", decision.reasons)


if __name__ == "__main__":
    unittest.main()
