"""Guarded replication bootstrap tests."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from embassy.replication_bootstrap import (
    ReplicationBootstrapConfig,
    ReplicationBootstrapError,
    build_basebackup_command,
    data_directory_is_empty,
    preserve_existing_data,
    seed_standby,
)


class ReplicationBootstrapTests(unittest.TestCase):
    def test_refuses_non_empty_data_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "pgdata"
            data.mkdir()
            (data / "PG_VERSION").write_text("16\n", encoding="utf-8")
            config = ReplicationBootstrapConfig(
                primary_host="100.64.0.10",
                primary_port=5432,
                replication_user="replicator",
                replication_password_env="FS_PG_REPL_PASSWORD",
                data_directory=data,
                backup_directory=root / "backup",
                slot_name="frank_odoo",
                application_name="frank",
                status_path=root / "status.json",
            )
            self.assertFalse(data_directory_is_empty(data))
            with self.assertRaises(ReplicationBootstrapError):
                seed_standby(config, dry_run=True)
            preserved = preserve_existing_data(config)
            self.assertIsNotNone(preserved)
            self.assertTrue(data_directory_is_empty(data))
            result = seed_standby(config, dry_run=True)
            self.assertEqual(result["status"], "dry_run")
            command = build_basebackup_command(config)
            self.assertIn("-R", command)
            self.assertIn("frank_odoo", command)


if __name__ == "__main__":
    unittest.main()
