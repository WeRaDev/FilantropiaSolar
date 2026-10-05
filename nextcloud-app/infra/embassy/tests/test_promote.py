"""Promotion executor gate tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest
from unittest.mock import patch

from embassy.lease import InMemoryLeaseAuthority, LeasePolicy
from embassy.lease_client import MemoryLeaseClient
from embassy.promote import PromoteContext, PromoteError, execute_promotion


class PromoteTests(unittest.TestCase):
    def test_execute_promotion_requires_authorized_decision_state(self):
        authority = InMemoryLeaseAuthority(LeasePolicy(lease_ttl_seconds=30))
        client = MemoryLeaseClient(authority)
        with self.assertRaises(PromoteError):
            execute_promotion(
                decision_state="ready_for_operator",
                client=client,
                context=PromoteContext(
                    standby_node_id="frank",
                    new_generation="g2",
                    previous_epoch=1,
                ),
                start_writer=False,
            )

    def test_authorized_promotion_acquires_next_epoch(self):
        now = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
        authority = InMemoryLeaseAuthority(
            LeasePolicy(
                lease_ttl_seconds=30,
                renew_before_seconds=5,
                in_flight_drain_seconds=0,
                self_fence_grace_seconds=0,
            )
        )
        boot = authority.bootstrap(node_id="trl5", generation="g1", now=now)
        authority.request_takeover(
            requester_node_id="frank",
            target_node_id="trl5",
            target_generation="g1",
            now=now + timedelta(seconds=1),
        )
        later = now + timedelta(seconds=40)
        client = MemoryLeaseClient(authority)
        client.status = lambda: authority.status(now=later)
        client.acquire = lambda **kwargs: authority.acquire(now=later, **kwargs)

        with (
            patch("embassy.promote.promote_database"),
            patch("embassy.promote.start_odoo_writer") as start_writer,
        ):
            result = execute_promotion(
                decision_state="promotion_authorized",
                client=client,
                context=PromoteContext(
                    standby_node_id="frank",
                    new_generation="g2",
                    previous_epoch=boot.state.epoch,
                ),
                start_writer=False,
            )
        self.assertEqual(result["standby_node_id"], "frank")
        self.assertEqual(result["epoch"], boot.state.epoch + 1)
        start_writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
