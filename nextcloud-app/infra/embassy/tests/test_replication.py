"""Unit tests for replication metadata and filestore safety checks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
from pathlib import Path
import tempfile
import unittest

from embassy.replication import (
    AttachmentReference,
    heartbeat_age_seconds,
    parse_wal_lsn,
    verify_attachment_files,
    wal_lag_bytes,
)


class ReplicationHelperTests(unittest.TestCase):
    def test_wal_lsn_parses_and_compares_positions(self):
        self.assertEqual(parse_wal_lsn("0/10"), 16)
        self.assertEqual(parse_wal_lsn("1/0"), 1 << 32)
        self.assertEqual(wal_lag_bytes("1/20", "1/10"), 16)

    def test_invalid_or_standby_ahead_lsn_is_rejected(self):
        for value in ("", "0", "1/2/3", "100000000/0", "1/100000000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_wal_lsn(value)
        with self.assertRaises(ValueError):
            wal_lag_bytes("0/10", "0/11")

    def test_heartbeat_age_requires_aware_timestamp(self):
        now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
        self.assertEqual(
            heartbeat_age_seconds(
                (now - timedelta(seconds=30)).isoformat(),
                now=now,
            ),
            30.0,
        )
        with self.assertRaises(ValueError):
            heartbeat_age_seconds("2026-10-01T11:59:30", now=now)
        self.assertEqual(
            heartbeat_age_seconds(
                (now + timedelta(seconds=5)).isoformat(),
                now=now,
            ),
            -5.0,
        )

    def test_attachment_check_verifies_sha1_size_and_reports_missing_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            attachment = root / "ab" / "content.bin"
            attachment.parent.mkdir()
            content = b"verified fixture"
            attachment.write_bytes(content)
            summary = verify_attachment_files(
                root,
                [
                    AttachmentReference(
                        "ab/content.bin",
                        hashlib.sha1(content).hexdigest(),
                        len(content),
                    ),
                    AttachmentReference("cd/missing.bin"),
                ],
            )

        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.verified, 1)
        self.assertEqual(summary.missing, 1)
        self.assertFalse(summary.ok)

    def test_traversal_symlink_bad_checksum_and_wrong_size_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file_path = root / "ab" / "file.bin"
            file_path.parent.mkdir()
            file_path.write_bytes(b"content")
            outside = root.parent / f"{root.name}-outside"
            outside.write_bytes(b"outside")
            (root / "link").symlink_to(outside)
            try:
                summary = verify_attachment_files(
                    root,
                    [
                        AttachmentReference("../outside"),
                        AttachmentReference("link"),
                        AttachmentReference("ab/file.bin", "0" * 40),
                        AttachmentReference("ab/file.bin", file_size=8),
                    ],
                )
            finally:
                outside.unlink(missing_ok=True)

        self.assertEqual(summary.invalid_path, 2)
        self.assertEqual(summary.checksum_mismatch, 1)
        self.assertEqual(summary.size_mismatch, 1)
        self.assertEqual(summary.verified, 0)


if __name__ == "__main__":
    unittest.main()
