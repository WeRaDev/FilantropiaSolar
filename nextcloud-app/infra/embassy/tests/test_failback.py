"""Failback branch selection tests."""

from __future__ import annotations

import unittest

from embassy.failback import FailbackBranch, plan_failback


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


if __name__ == "__main__":
    unittest.main()
