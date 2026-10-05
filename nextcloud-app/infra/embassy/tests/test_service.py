"""Unit tests for the fail-closed Embassy observe-only runner."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from embassy.journal import StateStore
from embassy.probe import ProbeResult
from embassy.service import EmbassyServiceError, run_once

_TOKEN_ENV = "FS_EMBASSY_TEST_READINESS_TOKEN"
_READY_PAYLOAD = {
    "ready": True,
    "node_id": "trl5",
    "writer_generation": "generation-7",
    "database_is_primary": True,
    "filestore_available": True,
    "maintenance_active": False,
}


class EmbassyServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config_path = self.root / "embassy.toml"
        self.state_dir = self.root / "state"
        self.state_path = self.state_dir / "state.json"
        self.journal_path = self.state_dir / "journal.jsonl"
        self.lock_path = self.state_dir / "run.lock"
        self.standby_status_path = self.root / "standby.json"
        self.fence_path = self.root / "fence.json"
        self._write_config()

    def _write_config(self, *, routes: list[str] | None = None) -> None:
        route_values = ", ".join(json.dumps(url) for url in routes or [])
        config = f"""
[primary]
node_id = "trl5"
writer_generation = "generation-7"
readiness_url = "http://100.82.252.18:8069/filantropia/embassy/readiness"
readiness_token_env = "{_TOKEN_ENV}"
timeout_seconds = 2
public_routes = [{route_values}]

[standby]
status_file = {json.dumps(str(self.standby_status_path))}
refresh_status = false

[fencing]
proof_file = {json.dumps(str(self.fence_path))}
trusted_sources = ["test-provider-fence"]

[state]
directory = {json.dumps(str(self.state_dir))}
state_file = {json.dumps(str(self.state_path))}
journal_file = {json.dumps(str(self.journal_path))}
lock_file = {json.dumps(str(self.lock_path))}

[policy]
failure_confirmation_cycles = 2
maximum_recovery_gap_seconds = 60
maximum_filestore_generation_age_seconds = 60
require_lease_acquirable = false
"""
        self.config_path.write_text(config, encoding="utf-8")
        self.config_path.chmod(0o600)

    def _write_private_json(self, path: Path, value: dict[str, object]) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")
        path.chmod(0o600)

    def _write_complete_standby_and_fence(self) -> None:
        now = datetime.now(UTC)
        self._write_private_json(
            self.standby_status_path,
            {
                "schema_version": 1,
                "observed_at_utc": now.isoformat(),
                "database_reachable": True,
                "database_in_recovery": True,
                "source_node_id": "trl5",
                "source_generation": "generation-7",
                "replication_heartbeat_age_seconds": 5,
                "replication_lag_bytes": 0,
                "filestore_source_generation": "generation-7",
                "filestore_generation_age_seconds": 5,
                "all_attachments_verified": True,
                "attachment_verified_at_utc": now.isoformat(),
                "code_compatible": True,
            },
        )
        self._write_private_json(
            self.fence_path,
            {
                "schema_version": 1,
                "target_node_id": "trl5",
                "target_generation": "generation-7",
                "source": "test-provider-fence",
                "proof_id": "test-proof-1",
                "verified_at_utc": (now - timedelta(seconds=1)).isoformat(),
                "expires_at_utc": (now + timedelta(minutes=5)).isoformat(),
                "acquirable": True,
            },
        )

    def test_healthy_origin_is_observed_without_standby_dependency(self):
        with (
            patch.dict(os.environ, {_TOKEN_ENV: "test-token"}),
            patch(
                "embassy.service.probe_readiness",
                return_value=ProbeResult(True, 200, _READY_PAYLOAD),
            ),
        ):
            state = run_once(self.config_path, require_encrypted_mount=False)

        self.assertEqual(state, "primary_healthy")
        self.assertEqual(
            StateStore(self.state_path).read()["consecutive_primary_failures"],
            0,
        )
        event = json.loads(self.journal_path.read_text(encoding="utf-8"))
        self.assertEqual(event["state"], "primary_healthy")
        self.assertNotIn("test-token", self.journal_path.read_text(encoding="utf-8"))
        self.assertEqual(stat.S_IMODE(self.journal_path.stat().st_mode), 0o600)

    def test_missing_readiness_token_is_inconclusive_not_a_primary_failure(self):
        with (
            patch.dict(os.environ, {_TOKEN_ENV: ""}),
            patch("embassy.service.probe_readiness") as probe,
        ):
            state = run_once(self.config_path, require_encrypted_mount=False)

        self.assertEqual(state, "primary_uncertain")
        self.assertEqual(
            StateStore(self.state_path).read()["consecutive_primary_failures"],
            0,
        )
        probe.assert_not_called()

    def test_two_unreachable_cycles_with_all_evidence_still_require_operator(self):
        self._write_config(routes=["https://solar.example/inicio"])
        self._write_complete_standby_and_fence()
        unreachable = ProbeResult(False, None, error_kind="TimeoutError")
        public_down = ProbeResult(False, None, error_kind="TimeoutError")
        with (
            patch.dict(os.environ, {_TOKEN_ENV: "test-token"}),
            patch("embassy.service.probe_readiness", return_value=unreachable),
            patch("embassy.service.probe_public_route", return_value=public_down),
        ):
            first_state = run_once(
                self.config_path,
                require_encrypted_mount=False,
            )
            second_state = run_once(
                self.config_path,
                require_encrypted_mount=False,
            )

        self.assertEqual(first_state, "primary_suspect")
        self.assertEqual(second_state, "ready_for_operator")
        self.assertEqual(
            StateStore(self.state_path).read()["consecutive_primary_failures"],
            2,
        )
        events = [
            json.loads(line)
            for line in self.journal_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(events[-1]["proposed_action"], "promote")
        self.assertEqual(events[-1]["state"], "ready_for_operator")

    def test_public_route_failure_is_separate_from_origin_failure(self):
        self._write_config(routes=["https://solar.example/inicio"])
        with (
            patch.dict(os.environ, {_TOKEN_ENV: "test-token"}),
            patch(
                "embassy.service.probe_readiness",
                return_value=ProbeResult(True, 200, _READY_PAYLOAD),
            ),
            patch(
                "embassy.service.probe_public_route",
                return_value=ProbeResult(True, 503),
            ),
        ):
            state = run_once(self.config_path, require_encrypted_mount=False)

        self.assertEqual(state, "ingress_degraded")

    def test_insecure_status_file_is_rejected(self):
        self._write_private_json(
            self.standby_status_path,
            {"schema_version": 1},
        )
        self.standby_status_path.chmod(0o644)
        with (
            patch.dict(os.environ, {_TOKEN_ENV: "test-token"}),
            patch(
                "embassy.service.probe_readiness",
                return_value=ProbeResult(True, 200, _READY_PAYLOAD),
            ),
            self.assertRaises(EmbassyServiceError),
        ):
            run_once(self.config_path, require_encrypted_mount=False)

    def test_state_paths_must_be_under_encrypted_mount(self):
        with (
            patch("pathlib.Path.is_mount", return_value=True),
            patch.dict(os.environ, {_TOKEN_ENV: "test-token"}),
            patch(
                "embassy.service.probe_readiness",
                return_value=ProbeResult(True, 200, _READY_PAYLOAD),
            ),
            self.assertRaisesRegex(EmbassyServiceError, "encrypted /data"),
        ):
            run_once(self.config_path)


if __name__ == "__main__":
    unittest.main()
