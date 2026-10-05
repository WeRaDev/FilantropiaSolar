"""Read-only PostgreSQL lineage and Odoo filestore verification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import hmac
from pathlib import Path, PurePosixPath
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

_WAL_LSN_PATTERN = re.compile(r"^[0-9A-Fa-f]{1,8}/[0-9A-Fa-f]{1,8}$")
_SHA1_PATTERN = re.compile(r"^[0-9A-Fa-f]{40}$")
_HASH_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class AttachmentReference:
    """Database metadata required to validate one filestore attachment."""

    store_fname: str
    checksum: str | None = None
    file_size: int | None = None


@dataclass(frozen=True)
class FilestoreVerification:
    """Aggregate result without exposing attachment names or customer data."""

    total: int
    verified: int
    missing: int
    invalid_path: int
    checksum_mismatch: int
    size_mismatch: int

    @property
    def ok(self) -> bool:
        return self.verified == self.total and not any(
            (
                self.missing,
                self.invalid_path,
                self.checksum_mismatch,
                self.size_mismatch,
            )
        )


def parse_wal_lsn(value: str) -> int:
    """Convert PostgreSQL's ``HEX/HEX`` LSN notation to an ordered byte offset."""
    if not _WAL_LSN_PATTERN.fullmatch(value):
        raise ValueError("Invalid PostgreSQL WAL LSN")
    high, low = (int(part, 16) for part in value.split("/", maxsplit=1))
    return (high << 32) | low


def wal_lag_bytes(primary_lsn: str, standby_lsn: str) -> int:
    """Return the byte gap; reject an impossible standby-ahead observation."""
    primary_offset = parse_wal_lsn(primary_lsn)
    standby_offset = parse_wal_lsn(standby_lsn)
    if standby_offset > primary_offset:
        raise ValueError("Standby WAL position is ahead of the configured primary")
    return primary_offset - standby_offset


def heartbeat_age_seconds(timestamp: str, *, now: datetime) -> float:
    """Calculate source heartbeat age without accepting naive or future timestamps."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Current time must be timezone-aware")
    normalized = timestamp[:-1] + "+00:00" if timestamp.endswith("Z") else timestamp
    heartbeat = datetime.fromisoformat(normalized)
    if heartbeat.tzinfo is None or heartbeat.utcoffset() is None:
        raise ValueError("Heartbeat timestamp must be timezone-aware")
    return (now.astimezone(UTC) - heartbeat.astimezone(UTC)).total_seconds()


def _safe_attachment_path(root: Path, name: str) -> Path | None:
    if not name or "\\" in name:
        return None
    relative = PurePosixPath(name)
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        return None

    candidate = root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            return None
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        return None
    return resolved


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_attachment_files(
    root: Path,
    references: Iterable[AttachmentReference],
) -> FilestoreVerification:
    """Check each DB reference, path, size, and Odoo SHA-1 content checksum."""
    resolved_root = root.resolve(strict=True)
    if not resolved_root.is_dir():
        raise ValueError("Filestore root must be a directory")

    counts = {
        "total": 0,
        "verified": 0,
        "missing": 0,
        "invalid_path": 0,
        "checksum_mismatch": 0,
        "size_mismatch": 0,
    }
    file_metadata: dict[Path, tuple[int, str]] = {}

    for reference in references:
        counts["total"] += 1
        path = _safe_attachment_path(resolved_root, reference.store_fname)
        if path is None:
            counts["invalid_path"] += 1
            continue
        if not path.is_file():
            counts["missing"] += 1
            continue
        metadata = file_metadata.get(path)
        if metadata is None:
            metadata = (path.stat().st_size, _sha1(path))
            file_metadata[path] = metadata
        file_size, checksum = metadata

        failed = False
        if (
            reference.file_size is not None
            and reference.file_size >= 0
            and file_size != reference.file_size
        ):
            counts["size_mismatch"] += 1
            failed = True
        if reference.checksum and (
            not _SHA1_PATTERN.fullmatch(reference.checksum)
            or not hmac.compare_digest(
                checksum.lower(),
                reference.checksum.lower(),
            )
        ):
            counts["checksum_mismatch"] += 1
            failed = True
        if not failed:
            counts["verified"] += 1

    return FilestoreVerification(**counts)
