"""Local writer-control ordering and refusal tests."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from embassy import writer_control


class WriterControlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.lock_path = self.root / "control.lock"
        self.fence_path = self.root / "odoo-fenced.json"
        self.identity = {
            "FS_EMBASSY_NODE_ID": "trl5",
            "FS_WRITER_GENERATION": "generation-7",
        }

    def tearDown(self):
        self.temporary.cleanup()

    def _patch_paths(self):
        return (
            patch.object(writer_control, "_CONTROL_LOCK", self.lock_path),
            patch.object(writer_control, "_FENCE_FILE", self.fence_path),
        )

    def test_fence_marker_precedes_restart_disable_and_stop(self):
        events = []
        lock_patch, fence_patch = self._patch_paths()
        with (
            patch.dict(os.environ, self.identity, clear=False),
            patch.object(writer_control.os, "geteuid", return_value=0),
            lock_patch,
            fence_patch,
            patch.object(
                writer_control,
                "_write_fence_marker",
                side_effect=lambda **_kwargs: events.append("marker"),
            ),
            patch.object(
                writer_control,
                "_container_state",
                side_effect=[(True, "unless-stopped"), (False, "no")],
            ),
            patch.object(
                writer_control,
                "_run_checked",
                side_effect=lambda command, **_kwargs: events.append(command[1]),
            ),
        ):
            writer_control.fence_writer(reason="approved_window")

        self.assertEqual(events, ["marker", "update", "stop"])

    def test_fence_failure_keeps_the_persistent_marker(self):
        events = []
        lock_patch, fence_patch = self._patch_paths()
        with (
            patch.dict(os.environ, self.identity, clear=False),
            patch.object(writer_control.os, "geteuid", return_value=0),
            lock_patch,
            fence_patch,
            patch.object(
                writer_control,
                "_write_fence_marker",
                side_effect=lambda **_kwargs: events.append("marker"),
            ),
            patch.object(
                writer_control,
                "_container_state",
                return_value=(True, "unless-stopped"),
            ),
            patch.object(
                writer_control,
                "_run_checked",
                side_effect=writer_control.WriterControlError("docker failure"),
            ),
            self.assertRaises(writer_control.WriterControlError),
        ):
            writer_control.fence_writer()

        self.assertEqual(events, ["marker"])

    def test_unfence_requires_explicit_other_writer_attestation(self):
        lock_patch, fence_patch = self._patch_paths()
        with (
            patch.object(writer_control.os, "geteuid", return_value=0),
            lock_patch,
            fence_patch,
            patch.object(writer_control, "_remove_fence_marker") as remove_marker,
            self.assertRaisesRegex(
                writer_control.WriterControlError,
                "Explicit confirmation",
            ),
        ):
            writer_control.unfence_writer(confirm_other_writer_fenced=False)

        remove_marker.assert_not_called()

    def test_unfence_requires_local_writer_evidence_before_removing_marker(self):
        lock_patch, fence_patch = self._patch_paths()
        with (
            patch.dict(os.environ, self.identity, clear=False),
            patch.object(writer_control.os, "geteuid", return_value=0),
            lock_patch,
            fence_patch,
            patch.object(writer_control, "_read_fence_marker"),
            patch.object(
                writer_control,
                "_verify_local_database",
                side_effect=writer_control.WriterControlError("standby database"),
            ),
            patch.object(
                writer_control, "_container_state", return_value=(False, "no")
            ),
            patch.object(writer_control, "_remove_fence_marker") as remove_marker,
            self.assertRaisesRegex(
                writer_control.WriterControlError,
                "standby database",
            ),
        ):
            writer_control.unfence_writer(confirm_other_writer_fenced=True)

        remove_marker.assert_not_called()

    def test_unfence_does_not_start_odoo_after_removing_the_fence(self):
        events = []
        lock_patch, fence_patch = self._patch_paths()
        with (
            patch.dict(os.environ, self.identity, clear=False),
            patch.object(writer_control.os, "geteuid", return_value=0),
            lock_patch,
            fence_patch,
            patch.object(writer_control, "_read_fence_marker"),
            patch.object(writer_control, "_verify_local_database"),
            patch.object(
                writer_control, "_container_state", return_value=(False, "no")
            ),
            patch.object(
                writer_control,
                "_remove_fence_marker",
                side_effect=lambda: events.append("unfence"),
            ),
            patch.object(writer_control, "_run_checked") as run_checked,
        ):
            writer_control.unfence_writer(confirm_other_writer_fenced=True)

        self.assertEqual(events, ["unfence"])
        run_checked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
