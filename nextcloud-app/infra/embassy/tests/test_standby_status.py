"""Unit tests for read-only standby health and attachment evidence collection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from embassy.filestore import _write_marker
from embassy.standby_status import (
    StandbyStatusError,
    _addon_source_sha256,
    collect_standby_status,
)


class StandbyStatusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.status_path = self.root / "run" / "standby-status.json"
        self.marker_path = self.root / "encrypted-data" / "filestore-marker.json"
        self.filestore_root = self.root / "encrypted-data" / "filestore"
        self.marker_path.parent.mkdir(mode=0o700, parents=True)
        self.marker_path.parent.chmod(0o700)
        self.filestore_root.mkdir(mode=0o700)
        self.addon_root = self.root / "addon" / "filantropia_solar_public"
        self.addon_root.mkdir(parents=True)
        self.manifest_path = self.addon_root / "__manifest__.py"
        self.manifest_path.write_text(
            '{"version": "19.0.2.35.0"}\n',
            encoding="utf-8",
        )
        now = datetime.now(UTC)
        _write_marker(
            self.marker_path,
            {
                "schema_version": 1,
                "source_node_id": "trl5",
                "source_generation": "generation-7",
                "completed_at_utc": (now - timedelta(seconds=5)).isoformat(),
            },
        )
        self.config = {
            "status_file": str(self.status_path),
            "database_container": "filantropia-odoo-db",
            "database_name": "filantropia_public",
            "query_timeout_seconds": 10,
            "filestore_root": str(self.filestore_root),
            "filestore_marker": str(self.marker_path),
            "addon_source_directory": str(self.addon_root),
            "addon_manifest_path": str(self.manifest_path),
            "expected_addon_version": "19.0.2.35.0",
            "expected_addon_source_sha256": _addon_source_sha256(self.addon_root),
        }

    def _database_responses(
        self,
        *,
        heartbeat_age_seconds: int = 5,
        receive_lsn: str = "0/30",
        replay_lsn: str = "0/20",
    ):
        now = datetime.now(UTC)
        attachment = self.filestore_root / "ab" / "content.bin"
        attachment.parent.mkdir(parents=True, exist_ok=True)
        content = b"verified fixture"
        attachment.write_bytes(content)
        return {
            "pg_is_in_recovery": "[true]",
            "FROM fs_ops.replication_heartbeat": json.dumps(
                [
                    "trl5",
                    "generation-7",
                    (now - timedelta(seconds=heartbeat_age_seconds)).isoformat(),
                    "0/20",
                    receive_lsn,
                    replay_lsn,
                ]
            ),
            "FROM ir_module_module": json.dumps(["19.0.2.35.0"]),
            "FROM ir_attachment": json.dumps(
                [["ab/content.bin", hashlib.sha1(content).hexdigest(), len(content)]]
            ),
        }

    def _query_mock(self, responses: dict[str, str]):
        def run(command, **_kwargs):
            query = command[-1]
            matching_response = next(
                (value for marker, value in responses.items() if marker in query),
                None,
            )
            if matching_response is None:
                return subprocess.CompletedProcess(command, 1, "", "")
            return subprocess.CompletedProcess(command, 0, matching_response, "")

        return run

    def test_collects_fresh_lineage_code_and_complete_attachment_evidence(self):
        responses = self._database_responses()
        with patch(
            "embassy.standby_status.subprocess.run",
            side_effect=self._query_mock(responses),
        ):
            status = collect_standby_status(
                self.config,
                require_encrypted_mount=False,
            )

        self.assertTrue(status["database_reachable"])
        self.assertTrue(status["database_in_recovery"])
        self.assertEqual(status["source_node_id"], "trl5")
        self.assertEqual(status["source_generation"], "generation-7")
        self.assertLessEqual(status["replication_heartbeat_age_seconds"], 10)
        self.assertEqual(status["replication_lag_bytes"], 16)
        self.assertEqual(status["source_heartbeat_wal_lsn"], "0/20")
        self.assertEqual(status["replication_receive_lsn"], "0/30")
        self.assertEqual(status["replication_replay_lsn"], "0/20")
        self.assertEqual(status["filestore_source_generation"], "generation-7")
        self.assertTrue(status["all_attachments_verified"])
        self.assertTrue(status["code_compatible"])
        self.assertEqual(status["addon_version"], "19.0.2.35.0")
        self.assertTrue(self.status_path.is_file())
        self.assertEqual(stat.S_IMODE(self.status_path.stat().st_mode), 0o600)

    def test_invalid_receive_or_replay_positions_leave_apply_lag_unknown(self):
        responses = self._database_responses(
            receive_lsn="0/10",
            replay_lsn="0/20",
        )
        with patch(
            "embassy.standby_status.subprocess.run",
            side_effect=self._query_mock(responses),
        ):
            status = collect_standby_status(
                self.config,
                require_encrypted_mount=False,
            )

        self.assertIsNone(status["replication_lag_bytes"])
        self.assertEqual(status["replication_receive_lsn"], "0/10")
        self.assertEqual(status["replication_replay_lsn"], "0/20")

    def test_database_failure_publishes_fresh_negative_status(self):
        with patch(
            "embassy.standby_status.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, "", "hidden error"),
        ):
            status = collect_standby_status(
                self.config,
                require_encrypted_mount=False,
            )

        self.assertFalse(status["database_reachable"])
        self.assertFalse(status["all_attachments_verified"])
        self.assertTrue(self.status_path.is_file())

    def test_primary_database_is_not_accepted_as_a_standby(self):
        with patch(
            "embassy.standby_status.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, "[false]", ""),
        ):
            status = collect_standby_status(
                self.config,
                require_encrypted_mount=False,
            )

        self.assertTrue(status["database_reachable"])
        self.assertFalse(status["database_in_recovery"])
        self.assertFalse(status["all_attachments_verified"])

    def test_unsafe_database_container_name_is_rejected_before_execution(self):
        self.config["database_container"] = "database;touch-pwned"
        with (
            patch("embassy.standby_status.subprocess.run") as run,
            self.assertRaises(StandbyStatusError),
        ):
            collect_standby_status(
                self.config,
                require_encrypted_mount=False,
            )
        run.assert_not_called()

    def test_encrypted_mount_is_mandatory_for_production_collection(self):
        with (
            patch("pathlib.Path.is_mount", return_value=False),
            self.assertRaisesRegex(StandbyStatusError, "Encrypted /data"),
        ):
            collect_standby_status(self.config)


if __name__ == "__main__":
    unittest.main()
