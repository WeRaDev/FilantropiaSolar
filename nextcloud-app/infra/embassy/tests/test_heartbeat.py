"""Unit tests for the PostgreSQL replication heartbeat writer."""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from embassy.heartbeat import (
    HeartbeatError,
    build_heartbeat_sql,
    write_primary_heartbeat,
)


class ReplicationHeartbeatTests(unittest.TestCase):
    def test_sql_is_primary_only_and_records_generation_and_wal_position(self):
        sql = build_heartbeat_sql(
            node_id="trl5",
            generation="generation-7",
        )

        self.assertLess(sql.index("IF pg_is_in_recovery()"), sql.index("CREATE TABLE"))
        self.assertIn("writer_generation text NOT NULL", sql)
        self.assertIn("pg_current_wal_lsn()", sql)
        self.assertIn("'trl5', 'generation-7'", sql)

    def test_untrusted_sql_values_are_rejected(self):
        for value in ("trl5'; DROP TABLE ir_attachment; --", "bad generation"):
            with self.subTest(value=value), self.assertRaises(HeartbeatError):
                build_heartbeat_sql(node_id=value, generation="generation-7")

    def test_container_name_is_validated_before_docker_execution(self):
        with (
            patch("embassy.heartbeat.subprocess.run") as run,
            self.assertRaises(HeartbeatError),
        ):
            write_primary_heartbeat(
                container="db; rm -rf /",
                node_id="trl5",
                generation="generation-7",
            )
        run.assert_not_called()

    def test_nonzero_psql_exit_fails_without_exposing_command_output(self):
        result = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="sensitive database error",
        )
        with (
            patch("embassy.heartbeat.subprocess.run", return_value=result),
            self.assertRaisesRegex(HeartbeatError, "command failed"),
        ):
            write_primary_heartbeat(
                container="filantropia-odoo-db",
                node_id="trl5",
                generation="generation-7",
            )


if __name__ == "__main__":
    unittest.main()
