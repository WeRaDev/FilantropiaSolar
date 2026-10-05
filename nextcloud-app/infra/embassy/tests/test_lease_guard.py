"""Lease guard self-fence decision tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from embassy.lease import InMemoryLeaseAuthority, LeasePolicy
from embassy.lease_client import MemoryLeaseClient
from embassy.lease_guard import run_once, should_self_fence, startup_allowed

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


class LeaseGuardTests(unittest.TestCase):
    def test_active_owner_does_not_self_fence(self):
        authority = InMemoryLeaseAuthority(LeasePolicy(lease_ttl_seconds=30))
        boot = authority.bootstrap(node_id="trl5", generation="g1", now=NOW)
        fence, reason = should_self_fence(
            node_id="trl5",
            generation="g1",
            local_state={"highest_epoch_seen": boot.state.epoch, "fenced": False},
            decision=authority.status(now=NOW + timedelta(seconds=1)),
            authority_error=False,
        )
        self.assertFalse(fence)
        self.assertEqual(reason, "lease_active")

    def test_authority_error_self_fences(self):
        fence, reason = should_self_fence(
            node_id="trl5",
            generation="g1",
            local_state={"highest_epoch_seen": 1, "fenced": False},
            decision=None,
            authority_error=True,
        )
        self.assertTrue(fence)
        self.assertEqual(reason, "lease_authority_unreachable")

    def test_run_once_fences_when_not_owner(self):
        authority = InMemoryLeaseAuthority(LeasePolicy(lease_ttl_seconds=30))
        authority.bootstrap(node_id="trl5", generation="g1", now=NOW)
        client = MemoryLeaseClient(authority)
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "guard.json"
            with (
                patch.dict(
                    os.environ,
                    {"FS_EMBASSY_NODE_ID": "frank", "FS_WRITER_GENERATION": "g2"},
                ),
                patch("embassy.lease_guard.fence_writer") as fence_writer,
            ):
                result = run_once(
                    client=client,
                    state_path=state_path,
                    perform_fence=True,
                )
            self.assertTrue(result.startswith("fenced:"))
            fence_writer.assert_called_once()
            self.assertFalse(startup_allowed(state_path=state_path))


if __name__ == "__main__":
    unittest.main()
