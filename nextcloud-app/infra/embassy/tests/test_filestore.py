"""Unit tests for safe filestore mirror command and marker behavior."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import stat
import tempfile
import unittest

from embassy.filestore import (
    FilestoreSyncConfig,
    _write_marker,
    build_rsync_command,
)


def _config(local_path: Path, status_path: Path):
    return FilestoreSyncConfig(
        remote_user="filestore-replica",
        remote_host="100.82.252.18",
        remote_path=PurePosixPath(
            "/var/lib/docker/volumes/odoo_data/_data/filestore/filantropia_public"
        ),
        local_path=local_path,
        ssh_key=Path("/etc/filantropia-embassy/filestore-readonly"),
        known_hosts=Path("/etc/filantropia-embassy/known_hosts"),
        status_path=status_path,
        source_node_id="trl5",
        source_generation="generation-7",
    )


class FilestoreSyncTests(unittest.TestCase):
    def test_rsync_command_is_atomic_per_file_and_never_deletes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command = build_rsync_command(
                _config(root / "filestore", root / "status.json")
            )

        self.assertIn("--delay-updates", command)
        self.assertIn("--partial", command)
        self.assertIn("--no-links", command)
        self.assertIn("--numeric-ids", command)
        self.assertFalse(any("delete" in argument for argument in command))
        self.assertIn("StrictHostKeyChecking=yes", command[command.index("-e") + 1])

    def test_marker_is_atomically_written_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            status_path = root / "private" / "filestore-status.json"
            _write_marker(
                status_path,
                {
                    "schema_version": 1,
                    "source_node_id": "trl5",
                    "source_generation": "generation-7",
                },
            )

            self.assertTrue(status_path.is_file())
            self.assertEqual(stat.S_IMODE(status_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(status_path.parent.stat().st_mode), 0o700)

    def test_remote_path_traversal_and_untrusted_host_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                FilestoreSyncConfig(
                    remote_user="replica",
                    remote_host="host;touch-pwned",
                    remote_path=PurePosixPath("/safe/path"),
                    local_path=root / "data",
                    ssh_key=root / "key",
                    known_hosts=root / "hosts",
                    status_path=root / "status",
                    source_node_id="trl5",
                    source_generation="generation-7",
                )
            with self.assertRaises(ValueError):
                FilestoreSyncConfig(
                    remote_user="replica",
                    remote_host="host",
                    remote_path=PurePosixPath("/safe/../outside"),
                    local_path=root / "data",
                    ssh_key=root / "key",
                    known_hosts=root / "hosts",
                    status_path=root / "status",
                    source_node_id="trl5",
                    source_generation="generation-7",
                )


if __name__ == "__main__":
    unittest.main()
