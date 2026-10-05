"""Unit tests for protected Embassy state and action journaling."""

from __future__ import annotations

import json
from pathlib import Path
import stat
import tempfile
import unittest

from embassy.journal import (
    EventJournal,
    JournalError,
    StateStore,
    operation_lock,
)


class EmbassyJournalTests(unittest.TestCase):
    def test_state_round_trips_atomically_with_private_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state" / "state.json"
            store = StateStore(path)
            state = {
                "consecutive_primary_failures": 2,
                "last_decision": "blocked_unfenced",
            }

            store.write(state)

            self.assertEqual(store.read()["last_decision"], "blocked_unfenced")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_corrupt_state_fails_closed_instead_of_resetting(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            path.write_text("{not-json", encoding="utf-8")
            path.chmod(0o600)

            with self.assertRaises(JournalError):
                StateStore(path).read()

    def test_insecure_state_permissions_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "consecutive_primary_failures": 0,
                    }
                ),
                encoding="utf-8",
            )
            path.chmod(0o644)

            with self.assertRaises(JournalError):
                StateStore(path).read()

    def test_sensitive_event_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            journal = EventJournal(Path(temporary) / "state" / "actions.jsonl")

            with self.assertRaises(JournalError):
                journal.append({"event": "probe", "readiness_token": "must-not-log"})

    def test_operation_lock_serializes_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "run" / "embassy.lock"

            with (
                operation_lock(lock),
                self.assertRaises(JournalError),
                operation_lock(lock),
            ):
                self.fail("A second Embassy run acquired the same lock")


if __name__ == "__main__":
    unittest.main()
