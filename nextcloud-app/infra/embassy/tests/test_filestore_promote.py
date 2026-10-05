"""Staged filestore promotion tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from embassy.filestore_promote import FilestorePromoteConfig, promote_filestore
from embassy.replication import AttachmentReference


class FilestorePromoteTests(unittest.TestCase):
    def test_promote_verifies_and_swaps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mirror = root / "mirror"
            active = root / "active"
            staging = root / "staging"
            backup = root / "backup"
            status = root / "status.json"
            content = b"attachment-bytes"
            target = mirror / "ab" / "file.bin"
            target.parent.mkdir(parents=True)
            target.write_bytes(content)
            config = FilestorePromoteConfig(
                mirror_root=mirror,
                active_root=active,
                staging_root=staging,
                backup_root=backup,
                status_path=status,
                source_node_id="trl5",
                source_generation="g1",
            )
            result = promote_filestore(
                config,
                [
                    AttachmentReference(
                        "ab/file.bin",
                        hashlib.sha1(content).hexdigest(),
                        len(content),
                    )
                ],
                require_encrypted_mount=False,
            )
            self.assertTrue((active / "ab" / "file.bin").is_file())
            self.assertEqual(result["attachments_verified"], 1)
            self.assertTrue(status.is_file())


if __name__ == "__main__":
    unittest.main()
