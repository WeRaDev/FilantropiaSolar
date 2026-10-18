"""Promotion executor gate tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest
from unittest.mock import patch

from embassy.lease import InMemoryLeaseAuthority, LeasePolicy
from embassy.lease_client import MemoryLeaseClient
from embassy.promote import (
    PromoteContext,
    PromoteError,
    execute_promotion,
    request_takeover_and_persist_proof,
    wait_for_acquirable_fencing_proof,
)


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

    def test_authorized_promotion_starts_writer_and_origin(self):
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
            patch("embassy.promote.start_origin_connector") as start_origin,
        ):
            result = execute_promotion(
                decision_state="promotion_authorized",
                client=client,
                context=PromoteContext(
                    standby_node_id="frank",
                    new_generation="g2",
                    previous_epoch=boot.state.epoch,
                ),
                start_writer=True,
            )
        self.assertTrue(result["origin_started"])
        start_writer.assert_called_once()
        start_origin.assert_called_once()

    def test_wait_for_acquirable_proof_polls_until_ready(self):
        import tempfile
        from pathlib import Path

        class _Client:
            def __init__(self) -> None:
                self.calls = 0

            def status(self):
                self.calls += 1
                acquirable = self.calls >= 2

                class _Decision:
                    fencing_proof = {
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
                    }
                    phase = type("P", (), {"value": "acquirable" if acquirable else "draining"})()
                    reason = "status"

                return _Decision()

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
            self.assertGreaterEqual(client.calls, 2)
            self.assertTrue(proof_path.is_file())

    def test_request_takeover_waits_for_acquirable_proof(self):
        import tempfile
        from pathlib import Path

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
