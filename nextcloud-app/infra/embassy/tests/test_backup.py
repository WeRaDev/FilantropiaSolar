"""Unit tests for the TRL5 Odoo backup capture lifecycle."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

BACKUP_SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts" / "backup-odoo-to-frank.py"
)


def _load_backup_module():
    spec = importlib.util.spec_from_file_location(
        "filantropia_odoo_backup_test",
        BACKUP_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load backup script from {BACKUP_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BackupLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_backup_module()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    @contextmanager
    def _quiesce_patches(self, marker: Path, events: list[str]):
        def check_readiness(
            *,
            node_id: str,
            generation: str,
            maintenance_active: bool,
            timeout_seconds: int = 30,
        ) -> None:
            del node_id, generation, timeout_seconds
            actual = self.module._existing_maintenance_active(datetime.now(UTC))
            self.assertEqual(actual, maintenance_active)
            events.append(f"readiness:{maintenance_active}")

        def run_checked(command: list[str], *, label: str, **_kwargs) -> None:
            del label
            if command[:2] == ["docker", "stop"]:
                events.append("docker:stop")
            elif command[:2] == ["docker", "start"]:
                events.append("docker:start")

        with (
            patch.object(self.module, "_MAINTENANCE_FILE", marker),
            patch.object(
                self.module,
                "_container_running",
                side_effect=[True, False, False],
            ),
            patch.object(
                self.module,
                "_wait_for_readiness",
                side_effect=check_readiness,
            ),
            patch.object(
                self.module,
                "_run_checked",
                side_effect=run_checked,
            ),
            patch.object(
                self.module,
                "_wait_for_web_login",
                side_effect=lambda: events.append("web:ready"),
            ),
        ):
            yield

    def test_backup_lock_rejects_a_concurrent_capture(self):
        lock_path = self.root / "backup.lock"
        with (
            self.module._exclusive_lock(lock_path, label="Odoo backup"),
            self.assertRaisesRegex(
                self.module.BackupError,
                "already running",
            ),
            self.module._exclusive_lock(lock_path, label="Odoo backup"),
        ):
            self.fail("the second backup lock unexpectedly succeeded")

    def test_backup_lock_rejects_symlinked_lock_files(self):
        target = self.root / "target.lock"
        target.touch()
        lock_path = self.root / "backup.lock"
        lock_path.symlink_to(target)

        with (
            self.assertRaisesRegex(
                self.module.BackupError,
                "must not be a symlink",
            ),
            self.module._exclusive_lock(lock_path, label="Odoo backup"),
        ):
            self.fail("the symlinked backup lock unexpectedly succeeded")

    def test_maintenance_marker_covers_capture_and_is_removed_after_resume(self):
        marker = self.root / "maintenance" / "maintenance.json"
        events: list[str] = []
        with (
            self._quiesce_patches(marker, events),
            self.module._quiesced_writer(
                node_id="trl5",
                generation="generation-7",
            ),
        ):
            self.assertTrue(self.module._existing_maintenance_active(datetime.now(UTC)))
            events.append("capture")

        self.assertFalse(marker.exists())
        self.assertEqual(
            events,
            [
                "readiness:False",
                "readiness:True",
                "docker:stop",
                "capture",
                "docker:start",
                "web:ready",
                "readiness:False",
            ],
        )
        self.assertEqual(marker.parent.stat().st_mode & 0o777, 0o755)

    def test_capture_failure_still_resumes_odoo_and_clears_marker(self):
        marker = self.root / "maintenance" / "maintenance.json"
        events: list[str] = []
        with (
            self._quiesce_patches(marker, events),
            self.assertRaisesRegex(
                self.module.BackupError,
                "capture failed",
            ),
            self.module._quiesced_writer(
                node_id="trl5",
                generation="generation-7",
            ),
        ):
            raise self.module.BackupError("capture failed")

        self.assertIn("docker:start", events)
        self.assertIn("web:ready", events)
        self.assertFalse(marker.exists())

    def test_capture_resumes_before_bundle_validation_and_network_publication(self):
        filestore = self.root / "filestore" / "filantropia_public"
        filestore.mkdir(parents=True)
        addon_source = self.root / "addon"
        addon_source.mkdir()
        (addon_source / "__manifest__.py").write_text(
            "{'version': '19.0.2.35.0'}\n",
            encoding="utf-8",
        )
        ssh_key = self.root / "id_ed25519"
        known_hosts = self.root / "known_hosts"
        ssh_key.touch()
        known_hosts.touch()
        marker = self.root / "maintenance" / "maintenance.json"
        lock_dir = self.root / "locks"
        lock_dir.mkdir()
        runtime_dir = self.root / "runtime"
        runtime_dir.mkdir()
        events: list[str] = []
        database_metadata = {
            "database_is_primary": True,
            "wal_lsn": "0/16B6C50",
            "postgresql_server_version": "16.14",
            "installed_addon_version": "19.0.2.35.0",
            "heartbeat": None,
        }
        image_metadata = [
            ("odoo:19", "sha256:odoo"),
            ("postgres:16", "sha256:postgres"),
            ("odoo:19", "sha256:odoo"),
            ("postgres:16", "sha256:postgres"),
        ]
        real_temporary_directory = tempfile.TemporaryDirectory

        def temporary_directory_factory(*, prefix: str, dir: str):
            del dir
            return real_temporary_directory(prefix=prefix, dir=runtime_dir)

        def run_checked(
            command: list[str],
            *,
            label: str,
            stdout=None,
            **_kwargs,
        ) -> None:
            del label
            if "pg_dump" in command:
                stdout.write(b"database dump")
                events.append("database:capture")
            elif command[0] == "tar":
                Path(command[3]).write_bytes(b"filestore archive")
                events.append("filestore:capture")
            elif command[:2] == ["docker", "stop"]:
                events.append("writer:stop")
            elif command[:2] == ["docker", "start"]:
                events.append("writer:resume")

        def check_readiness(
            *,
            node_id: str,
            generation: str,
            maintenance_active: bool,
            timeout_seconds: int = 30,
        ) -> None:
            del node_id, generation, timeout_seconds
            actual = self.module._existing_maintenance_active(datetime.now(UTC))
            self.assertEqual(actual, maintenance_active)
            events.append(f"readiness:{maintenance_active}")

        def assemble(work_dir: Path, metadata: dict[str, object]):
            events.append("bundle:validate")
            bundle_path = work_dir / "bundle.tar"
            bundle_path.write_bytes(b"verified bundle")
            created_at = datetime.fromisoformat(str(metadata["capture_started_at_utc"]))
            return bundle_path, "a" * 64, created_at

        def publish(*_args):
            events.append("bundle:publish")
            return "filantropia-odoo-test.tar", datetime.now(UTC)

        with (
            patch.dict(
                os.environ,
                {
                    "FS_ADDON_SOURCE_DIRECTORY": str(addon_source),
                    "FS_EMBASSY_READINESS_TOKEN": "test-token",
                    "FS_BACKUP_SSH_HOST": "backup-peer.invalid",
                    "FS_BACKUP_SSH_USER": "test-backup",
                    "FS_BACKUP_SSH_PORT": "22",
                },
                clear=False,
            ),
            patch.object(self.module.os, "geteuid", return_value=0),
            patch.object(self.module.os, "umask", return_value=0o022),
            patch.multiple(
                self.module,
                _FILESTORE_DIR=filestore,
                _ADDON_SOURCE_DIR=addon_source,
            ),
            patch.object(self.module, "_SSH_KEY", ssh_key),
            patch.object(self.module, "_KNOWN_HOSTS", known_hosts),
            patch.object(self.module, "_MAINTENANCE_FILE", marker),
            patch.object(self.module, "_LOCK_FILE", lock_dir / "backup.lock"),
            patch.object(
                self.module,
                "_CONTROL_LOCK_FILE",
                lock_dir / "control.lock",
            ),
            patch.object(
                self.module, "_writer_identity", return_value=("trl5", "generation-7")
            ),
            patch.object(self.module, "_assert_not_fenced"),
            patch.object(
                self.module,
                "_container_running",
                side_effect=[True, False, False],
            ),
            patch.object(
                self.module,
                "_wait_for_readiness",
                side_effect=check_readiness,
            ),
            patch.object(
                self.module,
                "_wait_for_web_login",
                side_effect=lambda: events.append("web:ready"),
            ),
            patch.object(
                self.module,
                "_run_checked",
                side_effect=run_checked,
            ),
            patch.object(
                self.module,
                "_database_metadata",
                side_effect=[database_metadata, database_metadata],
            ),
            patch.object(
                self.module,
                "_container_image_metadata",
                side_effect=image_metadata,
            ),
            patch.object(
                self.module.tempfile,
                "TemporaryDirectory",
                side_effect=temporary_directory_factory,
            ),
            patch.object(
                self.module,
                "_assemble_recovery_set",
                side_effect=assemble,
            ),
            patch.object(
                self.module,
                "_publish",
                side_effect=publish,
            ),
            patch.object(
                self.module,
                "_prune_remote",
                side_effect=lambda _published_at: events.append("retention"),
            ),
        ):
            self.module.backup()

        self.assertLess(events.index("writer:resume"), events.index("bundle:validate"))
        self.assertLess(events.index("bundle:validate"), events.index("bundle:publish"))
        self.assertLess(
            events.index("filestore:capture"), events.index("writer:resume")
        )
        self.assertEqual(events[-2:], ["bundle:publish", "retention"])


if __name__ == "__main__":
    unittest.main()
