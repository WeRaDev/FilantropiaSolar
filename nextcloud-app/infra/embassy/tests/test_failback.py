"""Failback branch selection and execute-gate tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest
from unittest.mock import patch

from embassy.failback import FailbackBranch, execute_failback, plan_failback
from embassy.lease import InMemoryLeaseAuthority, LeasePolicy
from embassy.lease_client import MemoryLeaseClient
from embassy.promote import PromoteContext, PromoteError


class FailbackPlanTests(unittest.TestCase):
    def test_no_writes_branch_does_not_preserve_frank_as_authority(self):
        plan = plan_failback(
            frank_accepted_writes=False,
            returning_generation="g-return",
            previous_epoch=3,
        )
        self.assertEqual(plan.branch, FailbackBranch.NO_STANDBY_WRITES)
        self.assertFalse(plan.preserve_current_writer_data)
        self.assertEqual(plan.returning_node_id, "trl5")

    def test_uncertain_or_true_writes_require_preserve_and_operator_reseed(self):
        for value in (True, None):
            with self.subTest(frank_accepted_writes=value):
                plan = plan_failback(
                    frank_accepted_writes=value,
                    returning_generation="g-return",
                    previous_epoch=4,
                )
                self.assertEqual(
                    plan.branch,
                    FailbackBranch.STANDBY_WRITES_OR_UNCERTAIN,
                )
                self.assertTrue(plan.preserve_current_writer_data)


class FailbackExecuteTests(unittest.TestCase):
    def test_execute_requires_explicit_safety_gates(self):
        plan = plan_failback(
            frank_accepted_writes=False,
            returning_generation="g-return",
            previous_epoch=1,
        )
        authority = InMemoryLeaseAuthority(LeasePolicy(lease_ttl_seconds=30))
        client = MemoryLeaseClient(authority)
        context = PromoteContext(
            standby_node_id="trl5",
            new_generation="g-return",
            previous_epoch=1,
            arm_lease_guard=False,
        )
        with self.assertRaises(PromoteError):
            execute_failback(plan=plan, client=client, context=context)

    def test_uncertain_branch_pauses_even_with_gates(self):
        plan = plan_failback(
            frank_accepted_writes=True,
            returning_generation="g-return",
            previous_epoch=2,
        )
        authority = InMemoryLeaseAuthority(LeasePolicy(lease_ttl_seconds=30))
        client = MemoryLeaseClient(authority)
        context = PromoteContext(
            standby_node_id="trl5",
            new_generation="g-return",
            previous_epoch=2,
            arm_lease_guard=False,
        )
        with (
            patch("embassy.failback.fence_current_writer"),
            patch.dict("os.environ", {"FS_EMBASSY_NODE_ID": "trl5"}, clear=False),
        ):
            result = execute_failback(
                plan=plan,
                client=client,
                context=context,
                allow_destructive_execute=True,
                confirm_remote_writer_fenced=True,
                confirm_local_host_is_returning_node=True,
            )
        self.assertEqual(result["status"], "awaiting_operator_reseed_and_validation")

    def test_no_writes_branch_is_lease_only_without_db_promote(self):
        now = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
        authority = InMemoryLeaseAuthority(
            LeasePolicy(
                lease_ttl_seconds=30,
                renew_before_seconds=5,
                in_flight_drain_seconds=0,
                self_fence_grace_seconds=0,
            )
        )
        boot = authority.bootstrap(node_id="frank", generation="g-frank", now=now)
        authority.request_takeover(
            requester_node_id="trl5",
            target_node_id="frank",
            target_generation="g-frank",
            now=now + timedelta(seconds=1),
        )
        later = now + timedelta(seconds=40)
        client = MemoryLeaseClient(authority)
        client.status = lambda: authority.status(now=later)
        client.acquire = lambda **kwargs: authority.acquire(now=later, **kwargs)

        plan = plan_failback(
            frank_accepted_writes=False,
            returning_generation="g-return",
            previous_epoch=boot.state.epoch,
        )
        context = PromoteContext(
            standby_node_id="trl5",
            new_generation="g-return",
            previous_epoch=boot.state.epoch,
            arm_lease_guard=False,
        )
        with (
            patch("embassy.failback.fence_current_writer"),
            patch("embassy.promote.promote_database") as promote_db,
            patch.dict("os.environ", {"FS_EMBASSY_NODE_ID": "trl5"}, clear=False),
        ):
            result = execute_failback(
                plan=plan,
                client=client,
                context=context,
                start_writer=False,
                allow_destructive_execute=True,
                confirm_remote_writer_fenced=True,
                confirm_local_host_is_returning_node=True,
            )
        promote_db.assert_not_called()
        self.assertTrue(result["database_promote_skipped"])
        self.assertFalse(result["database_promoted"])
        self.assertEqual(result["standby_node_id"], "trl5")


if __name__ == "__main__":
    unittest.main()
