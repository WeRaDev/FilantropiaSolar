"""Unit tests for the cooperative software-lease authority."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from embassy.lease import InMemoryLeaseAuthority, LeasePhase, LeasePolicy

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


class LeaseAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.authority = InMemoryLeaseAuthority(
            LeasePolicy(
                lease_ttl_seconds=30,
                in_flight_drain_seconds=5,
                self_fence_grace_seconds=10,
            )
        )

    def test_bootstrap_renew_and_permit(self):
        boot = self.authority.bootstrap(node_id="trl5", generation="g1", now=NOW)
        self.assertTrue(boot.ok)
        self.assertEqual(boot.phase, LeasePhase.ACTIVE)
        renew = self.authority.renew(
            node_id="trl5",
            epoch=boot.state.epoch,
            generation="g1",
            readiness_ok=True,
            now=NOW + timedelta(seconds=10),
        )
        self.assertTrue(renew.ok)
        permit = self.authority.permit(
            origin_node_id="trl5",
            epoch=boot.state.epoch,
            now=NOW + timedelta(seconds=11),
        )
        self.assertTrue(permit.request_permit)
        denied = self.authority.permit(
            origin_node_id="frank",
            epoch=boot.state.epoch,
            now=NOW + timedelta(seconds=11),
        )
        self.assertFalse(denied.request_permit)

    def test_takeover_refuses_renewal_and_grants_after_grace(self):
        boot = self.authority.bootstrap(node_id="trl5", generation="g1", now=NOW)
        takeover = self.authority.request_takeover(
            requester_node_id="frank",
            target_node_id="trl5",
            target_generation="g1",
            now=NOW + timedelta(seconds=1),
        )
        self.assertTrue(takeover.ok)
        self.assertIsNotNone(takeover.fencing_proof)
        refused = self.authority.renew(
            node_id="trl5",
            epoch=boot.state.epoch,
            generation="g1",
            readiness_ok=True,
            now=NOW + timedelta(seconds=2),
        )
        self.assertFalse(refused.ok)
        early = self.authority.acquire(
            node_id="frank",
            generation="g2",
            previous_epoch=boot.state.epoch,
            now=NOW + timedelta(seconds=2),
        )
        self.assertFalse(early.ok)
        ready_at = NOW + timedelta(seconds=1 + 30 + 10)
        acquired = self.authority.acquire(
            node_id="frank",
            generation="g2",
            previous_epoch=boot.state.epoch,
            now=ready_at,
        )
        self.assertTrue(acquired.ok)
        self.assertEqual(acquired.state.owner_node_id, "frank")
        self.assertEqual(acquired.state.epoch, boot.state.epoch + 1)

    def test_previous_owner_cannot_reacquire_during_takeover(self):
        boot = self.authority.bootstrap(node_id="trl5", generation="g1", now=NOW)
        self.authority.request_takeover(
            requester_node_id="frank",
            target_node_id="trl5",
            target_generation="g1",
            now=NOW + timedelta(seconds=1),
        )
        ready_at = NOW + timedelta(seconds=50)
        denied = self.authority.acquire(
            node_id="trl5",
            generation="g1",
            previous_epoch=boot.state.epoch,
            now=ready_at,
        )
        self.assertFalse(denied.ok)
        self.assertEqual(
            denied.reason,
            "previous_owner_cannot_reacquire_during_takeover",
        )


if __name__ == "__main__":
    unittest.main()
