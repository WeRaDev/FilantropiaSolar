"""Lease guard self-fence decision tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from embassy.lease import InMemoryLeaseAuthority, LeasePolicy
from embassy.lease_client import LeaseClientError, MemoryLeaseClient
from embassy.lease_guard import (
    arm_lease_guard_as_writer,
    is_intentional_standby_fence,
    is_recoverable_fence_reason,
    run_once,
    should_self_fence,
    startup_allowed,
    write_active_guard_state,
)

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

    def test_authority_error_soft_retry_before_threshold(self):
        fence, reason = should_self_fence(
            node_id="trl5",
            generation="g1",
            local_state={
                "highest_epoch_seen": 1,
                "fenced": False,
                "authority_failures": 1,
            },
            decision=None,
            authority_error=True,
        )
        self.assertFalse(fence)
        self.assertTrue(reason.startswith("authority_retry_"))

    def test_authority_error_self_fences_at_threshold(self):
        fence, reason = should_self_fence(
            node_id="trl5",
            generation="g1",
            local_state={
                "highest_epoch_seen": 1,
                "fenced": False,
                "authority_failures": 2,
            },
            decision=None,
            authority_error=True,
        )
        self.assertTrue(fence)
        self.assertEqual(reason, "lease_authority_unreachable")


    def test_intentional_standby_fence_matrix(self):
        self.assertTrue(is_intentional_standby_fence("failback_to_trl5"))
        self.assertTrue(is_intentional_standby_fence("standby_awaiting_promote"))
        self.assertFalse(is_intentional_standby_fence("lease_authority_unreachable"))
        self.assertFalse(is_intentional_standby_fence("lease_owned_by_other_node"))

    def test_recoverable_fence_reason_matrix(self):
        self.assertTrue(is_recoverable_fence_reason("lease_authority_unreachable"))
        self.assertTrue(is_recoverable_fence_reason("lease_phase_acquirable"))
        self.assertFalse(is_recoverable_fence_reason("failback_to_trl5"))
        self.assertFalse(is_recoverable_fence_reason("lease_owned_by_other_node"))
        self.assertFalse(is_recoverable_fence_reason("standby_awaiting_promote"))

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

    def test_run_once_authority_retry_then_fence(self):
        client = MagicMock()
        client.status.side_effect = LeaseClientError("authority down")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            state_path = root / "guard.json"
            with (
                patch.dict(
                    os.environ,
                    {
                        "FS_EMBASSY_NODE_ID": "trl5",
                        "FS_WRITER_GENERATION": "g1",
                        "FS_LEASE_AUTHORITY_FAILURE_THRESHOLD": "2",
                        "FS_LEASE_GUARD_SKIP_ENSURE_CONTAINERS": "1",
                    },
                    clear=False,
                ),
                patch("embassy.lease_guard.fence_writer") as fence_writer,
            ):
                first = run_once(
                    client=client, state_path=state_path, perform_fence=True
                )
                self.assertEqual(first, "authority_retry:1")
                fence_writer.assert_not_called()
                guard = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertFalse(guard.get("fenced"))

                second = run_once(
                    client=client, state_path=state_path, perform_fence=True
                )
                self.assertEqual(second, "fenced:lease_authority_unreachable")
                fence_writer.assert_called_once()
                guard = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertTrue(guard["fenced"])
                self.assertEqual(
                    guard["fence_reason"], "lease_authority_unreachable"
                )

    def test_run_once_recovers_from_authority_fence(self):
        authority = InMemoryLeaseAuthority(LeasePolicy(lease_ttl_seconds=30))
        boot = authority.bootstrap(node_id="trl5", generation="g1", now=NOW)
        client = MemoryLeaseClient(authority)
        client.status = lambda: authority.status(now=NOW + timedelta(seconds=1))
        client.renew = lambda **kwargs: authority.renew(
            now=NOW + timedelta(seconds=2), **kwargs
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            state_path = root / "guard.json"
            fence_path = root / "odoo-fenced.json"
            fence_path.write_text(
                '{"schema_version":1,"state":"fenced"}\n', encoding="utf-8"
            )
            fence_path.chmod(0o600)
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "fenced": True,
                        "fence_reason": "lease_authority_unreachable",
                        "highest_epoch_seen": boot.state.epoch,
                        "active_epoch": boot.state.epoch,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            state_path.chmod(0o600)
            with (
                patch.dict(
                    os.environ,
                    {
                        "FS_EMBASSY_NODE_ID": "trl5",
                        "FS_WRITER_GENERATION": "g1",
                        "FILANTROPIA_ODOO_FENCE_FILE": str(fence_path),
                        "FS_LEASE_GUARD_SKIP_ENSURE_CONTAINERS": "1",
                    },
                    clear=False,
                ),
                patch("embassy.lease_guard.ensure_writer_containers") as ensure,
            ):
                result = run_once(
                    client=client, state_path=state_path, perform_fence=True
                )
            self.assertEqual(result, "recovered:active")
            ensure.assert_called_once()
            self.assertFalse(fence_path.exists())
            guard = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertFalse(guard["fenced"])
            self.assertEqual(guard.get("authority_failures"), 0)
            self.assertTrue(startup_allowed(state_path=state_path))

    def test_run_once_reacquires_after_transient_fence_when_expired(self):
        authority = InMemoryLeaseAuthority(LeasePolicy(lease_ttl_seconds=30))
        boot = authority.bootstrap(node_id="trl5", generation="g1", now=NOW)
        client = MemoryLeaseClient(authority)
        expired = NOW + timedelta(seconds=40)
        client.status = lambda: authority.status(now=expired)
        client.acquire = lambda **kwargs: authority.acquire(
            now=expired + timedelta(seconds=1), **kwargs
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            state_path = root / "guard.json"
            fence_path = root / "odoo-fenced.json"
            fence_path.write_text(
                '{"schema_version":1,"state":"fenced"}\n', encoding="utf-8"
            )
            fence_path.chmod(0o600)
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "fenced": True,
                        "fence_reason": "lease_authority_unreachable",
                        "highest_epoch_seen": boot.state.epoch,
                        "active_epoch": boot.state.epoch,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            state_path.chmod(0o600)
            with patch.dict(
                os.environ,
                {
                    "FS_EMBASSY_NODE_ID": "trl5",
                    "FS_WRITER_GENERATION": "g1",
                    "FILANTROPIA_ODOO_FENCE_FILE": str(fence_path),
                    "FS_LEASE_GUARD_SKIP_ENSURE_CONTAINERS": "1",
                },
                clear=False,
            ):
                result = run_once(
                    client=client, state_path=state_path, perform_fence=False
                )
            self.assertEqual(result, "recovered:reacquired")
            self.assertFalse(fence_path.exists())
            guard = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertFalse(guard["fenced"])
            self.assertGreaterEqual(guard["active_epoch"], boot.state.epoch)

    def test_run_once_keeps_failback_fence_sticky(self):
        authority = InMemoryLeaseAuthority(LeasePolicy(lease_ttl_seconds=30))
        boot = authority.bootstrap(node_id="trl5", generation="g1", now=NOW)
        client = MemoryLeaseClient(authority)
        client.status = lambda: authority.status(now=NOW + timedelta(seconds=1))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            state_path = root / "guard.json"
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "fenced": True,
                        "fence_reason": "failback_to_trl5",
                        "highest_epoch_seen": boot.state.epoch,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            state_path.chmod(0o600)
            with patch.dict(
                os.environ,
                {
                    "FS_EMBASSY_NODE_ID": "trl5",
                    "FS_WRITER_GENERATION": "g1",
                    "FS_LEASE_GUARD_SKIP_ENSURE_CONTAINERS": "1",
                },
                clear=False,
            ):
                result = run_once(
                    client=client, state_path=state_path, perform_fence=False
                )
            self.assertEqual(result, "fenced:failback_to_trl5")
            guard = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertTrue(guard["fenced"])
            self.assertEqual(guard["fence_reason"], "failback_to_trl5")

    def test_arm_refuses_before_clearing_fence_if_not_owner(self):
        authority = InMemoryLeaseAuthority(LeasePolicy(lease_ttl_seconds=30))
        authority.bootstrap(node_id="trl5", generation="g1", now=NOW)
        client = MemoryLeaseClient(authority)
        client.status = lambda: authority.status(now=NOW + timedelta(seconds=1))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            state_path = root / "guard.json"
            fence_path = root / "odoo-fenced.json"
            fence_path.write_text(
                '{"schema_version":1,"state":"fenced"}\n', encoding="utf-8"
            )
            fence_path.chmod(0o600)
            with self.assertRaisesRegex(
                Exception, "not active for the promoted writer"
            ):
                arm_lease_guard_as_writer(
                    client=client,
                    node_id="frank",
                    generation="g2",
                    epoch=1,
                    state_path=state_path,
                    fence_file=fence_path,
                    enable_timer=False,
                    renew_now=False,
                )
            self.assertTrue(fence_path.exists())

    def test_arm_lease_guard_as_writer_clears_fence_and_renews(self):
        authority = InMemoryLeaseAuthority(LeasePolicy(lease_ttl_seconds=30))
        boot = authority.bootstrap(node_id="frank", generation="g2", now=NOW)
        client = MemoryLeaseClient(authority)
        # Keep authority clock near bootstrap so renew is not TTL-expired.
        client.status = lambda: authority.status(now=NOW + timedelta(seconds=1))
        client.renew = lambda **kwargs: authority.renew(
            now=NOW + timedelta(seconds=2), **kwargs
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            state_path = root / "guard.json"
            fence_path = root / "odoo-fenced.json"
            fence_path.write_text(
                '{"schema_version":1,"state":"fenced"}\n', encoding="utf-8"
            )
            fence_path.chmod(0o600)
            write_active_guard_state(
                state_path=state_path,
                epoch=1,
                lease_expires_at=None,
            )
            # Force fenced standby posture.
            data = json.loads(state_path.read_text(encoding="utf-8"))
            data["fenced"] = True
            data["fence_reason"] = "failback_to_trl5"
            state_path.write_text(json.dumps(data) + "\n", encoding="utf-8")
            state_path.chmod(0o600)

            with patch("embassy.lease_guard.enable_lease_guard_timer") as enable_timer:
                result = arm_lease_guard_as_writer(
                    client=client,
                    node_id="frank",
                    generation="g2",
                    epoch=boot.state.epoch,
                    lease_expires_at=boot.state.lease_expires_at,
                    state_path=state_path,
                    fence_file=fence_path,
                    enable_timer=True,
                    renew_now=True,
                )
            self.assertTrue(result["armed"])
            self.assertTrue(result["renewed"])
            enable_timer.assert_called_once()
            self.assertFalse(fence_path.exists())
            guard = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertFalse(guard["fenced"])
            self.assertEqual(guard["active_epoch"], boot.state.epoch)
            self.assertTrue(startup_allowed(state_path=state_path))


if __name__ == "__main__":
    unittest.main()
