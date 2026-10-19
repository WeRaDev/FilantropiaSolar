"""Promotion executor gate tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from embassy.lease import InMemoryLeaseAuthority, LeasePolicy
from embassy.lease_client import MemoryLeaseClient
from embassy.lease_guard import LeaseGuardError
from embassy.promote import (
    PromoteContext,
    PromoteError,
    execute_promotion,
    request_takeover_and_persist_proof,
    wait_for_acquirable_fencing_proof,
)

_MIN_ACQUIRABLE_STATUS_CALLS = 2


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
            patch("embassy.promote.promote_database") as promote_db,
            patch("embassy.promote.start_odoo_writer") as start_writer,
        ):
            result = execute_promotion(
                decision_state="promotion_authorized",
                client=client,
                context=PromoteContext(
                    standby_node_id="frank",
                    new_generation="g2",
                    previous_epoch=boot.state.epoch,
                    arm_lease_guard=False,
                ),
                start_writer=False,
            )
        self.assertEqual(result["standby_node_id"], "frank")
        self.assertEqual(result["epoch"], boot.state.epoch + 1)
        self.assertFalse(result["lease_guard_armed"])
        self.assertTrue(result["database_promoted"])
        promote_db.assert_called_once()
        start_writer.assert_not_called()

    def test_authorized_promotion_starts_writer_and_origin_after_arm(self):
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

        order: list[str] = []

        def track(name: str):
            def _inner(*_args, **_kwargs):
                order.append(name)

            return _inner

        with (
            patch("embassy.promote.promote_database", side_effect=track("db")),
            patch("embassy.promote.start_odoo_writer", side_effect=track("odoo")),
            patch(
                "embassy.promote.start_origin_connector",
                side_effect=track("origin"),
            ),
            patch(
                "embassy.promote.arm_lease_guard_as_writer",
                side_effect=lambda **_k: order.append("arm") or {"armed": True},
            ),
        ):
            result = execute_promotion(
                decision_state="promotion_authorized",
                client=client,
                context=PromoteContext(
                    standby_node_id="frank",
                    new_generation="g2",
                    previous_epoch=boot.state.epoch,
                    arm_lease_guard=True,
                ),
                start_writer=True,
            )
        self.assertTrue(result["origin_started"])
        self.assertTrue(result["lease_guard_armed"])
        self.assertEqual(order, ["arm", "db", "odoo", "origin"])

    def test_authorized_promotion_arms_lease_guard_and_renews(self):
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
        client.renew = lambda **kwargs: authority.renew(
            now=later + timedelta(seconds=1), **kwargs
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            state_path = root / "lease-guard-state.json"
            fence_path = root / "odoo-fenced.json"
            fence_path.write_text(
                '{"schema_version":1,"state":"fenced","node_id":"frank"}\n',
                encoding="utf-8",
            )
            fence_path.chmod(0o600)
            state_path.write_text(
                '{"schema_version":1,"fenced":true,"fence_reason":"standby",'
                '"highest_epoch_seen":1}\n',
                encoding="utf-8",
            )
            state_path.chmod(0o600)

            with (
                patch("embassy.promote.promote_database"),
                patch("embassy.promote.start_odoo_writer"),
                patch("embassy.promote.start_origin_connector"),
                patch("embassy.lease_guard.enable_lease_guard_timer") as enable_timer,
                patch.dict(
                    "os.environ",
                    {"FILANTROPIA_ODOO_FENCE_FILE": str(fence_path)},
                    clear=False,
                ),
            ):
                result = execute_promotion(
                    decision_state="promotion_authorized",
                    client=client,
                    context=PromoteContext(
                        standby_node_id="frank",
                        new_generation="g2",
                        previous_epoch=boot.state.epoch,
                        arm_lease_guard=True,
                        lease_guard_state_path=state_path,
                        lease_guard_enable_timer=True,
                        lease_guard_renew_now=True,
                    ),
                    start_writer=True,
                )

            self.assertTrue(result["lease_guard_armed"])
            self.assertTrue(result["lease_guard"]["renewed"])
            enable_timer.assert_called_once()
            self.assertFalse(fence_path.exists())
            import json

            guard = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertFalse(guard["fenced"])
            self.assertEqual(guard["active_epoch"], result["epoch"])
            self.assertNotIn("fence_reason", guard)

    def test_promotion_arm_failure_does_not_start_writer_or_promote_db(self):
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
            patch("embassy.promote.promote_database") as promote_db,
            patch("embassy.promote.start_odoo_writer") as start_writer,
            patch("embassy.promote.start_origin_connector") as start_origin,
            patch(
                "embassy.promote.arm_lease_guard_as_writer",
                side_effect=LeaseGuardError("timer missing"),
            ),
            patch("embassy.promote._compensate_partial_promotion") as compensate,
            self.assertRaises(PromoteError) as raised,
        ):
            execute_promotion(
                decision_state="promotion_authorized",
                client=client,
                context=PromoteContext(
                    standby_node_id="frank",
                    new_generation="g2",
                    previous_epoch=boot.state.epoch,
                    arm_lease_guard=True,
                ),
                start_writer=True,
            )
        self.assertIn("arm lease-guard", str(raised.exception))
        promote_db.assert_not_called()
        start_writer.assert_not_called()
        start_origin.assert_not_called()
        compensate.assert_called_once()
        self.assertEqual(
            compensate.call_args.kwargs,
            {"writer_started": False, "origin_started": False},
        )

    def test_wait_for_acquirable_proof_polls_until_ready(self):
        class _Client:
            def __init__(self) -> None:
                self.calls = 0

            def status(self):
                self.calls += 1
                acquirable = self.calls >= _MIN_ACQUIRABLE_STATUS_CALLS

                return SimpleNamespace(
                    fencing_proof={
                        "schema_version": 1,
                        "target_node_id": "trl5",
                        "target_generation": "g1",
                        "source": "cloudflare-durable-object-lease",
                        "proof_id": "p1",
                        "verified_at_utc": "2026-10-17T12:00:00Z",
                        "expires_at_utc": "2026-10-17T12:05:00Z",
                        "previous_epoch": 1,
                        "phase": "acquirable" if acquirable else "draining",
                        "acquirable": acquirable,
                    },
                    phase=SimpleNamespace(
                        value="acquirable" if acquirable else "draining"
                    ),
                    reason="status",
                )

        with tempfile.TemporaryDirectory() as tmp:
            proof_path = Path(tmp) / "fence.json"
            proof_path.parent.chmod(0o700)
            client = _Client()
            decision = wait_for_acquirable_fencing_proof(
                client,
                proof_path=proof_path,
                timeout_seconds=5.0,
                poll_seconds=0.01,
            )
            self.assertTrue(decision.fencing_proof["acquirable"])
            self.assertGreaterEqual(client.calls, _MIN_ACQUIRABLE_STATUS_CALLS)
            self.assertTrue(proof_path.is_file())

    def test_wait_for_acquirable_proof_times_out_fail_closed(self):
        class _Client:
            def status(self):
                return SimpleNamespace(
                    fencing_proof={
                        "schema_version": 1,
                        "target_node_id": "trl5",
                        "target_generation": "g1",
                        "source": "cloudflare-durable-object-lease",
                        "proof_id": "p1",
                        "verified_at_utc": "2026-10-17T12:00:00Z",
                        "expires_at_utc": "2026-10-17T12:05:00Z",
                        "previous_epoch": 1,
                        "phase": "draining",
                        "acquirable": False,
                    },
                    phase=SimpleNamespace(value="draining"),
                    reason="status",
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o700)
            proof_path = root / "fence.json"
            with self.assertRaises(PromoteError) as raised:
                wait_for_acquirable_fencing_proof(
                    _Client(),
                    proof_path=proof_path,
                    timeout_seconds=0.05,
                    poll_seconds=0.01,
                )
            self.assertIn("acquirable", str(raised.exception))

    def test_request_takeover_waits_for_acquirable_proof(self):
        class _Phase:
            def __init__(self, value: str) -> None:
                self.value = value

        class _Decision:
            def __init__(self, *, ok: bool, phase: str, proof: dict) -> None:
                self.ok = ok
                self.reason = "takeover_pending" if phase != "acquirable" else "status"
                self.phase = _Phase(phase)
                self.fencing_proof = proof

        class _Client:
            def __init__(self) -> None:
                self.status_calls = 0

            def request_takeover(self, **_kwargs):
                return _Decision(
                    ok=True,
                    phase="draining",
                    proof={
                        "schema_version": 1,
                        "target_node_id": "trl5",
                        "target_generation": "g1",
                        "source": "cloudflare-durable-object-lease",
                        "proof_id": "p1",
                        "verified_at_utc": "2026-10-17T12:00:00Z",
                        "expires_at_utc": "2026-10-17T12:05:00Z",
                        "previous_epoch": 1,
                        "phase": "draining",
                        "acquirable": False,
                    },
                )

            def status(self):
                self.status_calls += 1
                return _Decision(
                    ok=True,
                    phase="acquirable",
                    proof={
                        "schema_version": 1,
                        "target_node_id": "trl5",
                        "target_generation": "g1",
                        "source": "cloudflare-durable-object-lease",
                        "proof_id": "p1",
                        "verified_at_utc": "2026-10-17T12:00:10Z",
                        "expires_at_utc": "2026-10-17T12:05:10Z",
                        "previous_epoch": 1,
                        "phase": "acquirable",
                        "acquirable": True,
                    },
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o700)
            proof_path = root / "fence.json"
            client = _Client()
            decision = request_takeover_and_persist_proof(
                client,
                requester_node_id="frank",
                target_node_id="trl5",
                target_generation="g1",
                proof_path=proof_path,
                wait_for_acquirable=True,
                acquirable_timeout_seconds=5.0,
            )
            self.assertTrue(decision.fencing_proof["acquirable"])
            self.assertGreaterEqual(client.status_calls, 1)
            self.assertTrue(proof_path.is_file())


if __name__ == "__main__":
    unittest.main()
