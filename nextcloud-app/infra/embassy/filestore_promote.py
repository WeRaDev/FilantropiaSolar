"""Staged, reversible promotion of the mirrored Odoo filestore."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

from embassy.replication import AttachmentReference, verify_attachment_files


class FilestorePromoteError(RuntimeError):
    """Raised when a filestore promotion cannot complete safely."""


@dataclass(frozen=True)
class FilestorePromoteConfig:
    mirror_root: Path
    active_root: Path
    staging_root: Path
    backup_root: Path
    status_path: Path
    source_node_id: str
    source_generation: str

    def __post_init__(self) -> None:
        if not self.source_node_id or not self.source_generation:
            raise ValueError("Filestore promotion source identity is required")
        for path in (
            self.mirror_root,
            self.active_root,
            self.staging_root,
            self.backup_root,
            self.status_path,
        ):
            if path.is_symlink():
                raise ValueError(f"Filestore path must not be a symlink: {path}")


def _assert_private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise FilestorePromoteError(f"Directory must not be a symlink: {path}")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise FilestorePromoteError(f"Directory is not private: {path}")


def _write_status(path: Path, payload: dict[str, object]) -> None:
    parent = path.parent
    _assert_private_dir(parent)
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise FilestorePromoteError("Could not publish filestore promotion status") from exc


def promote_filestore(
    config: FilestorePromoteConfig,
    references: list[AttachmentReference],
    *,
    require_encrypted_mount: bool = True,
) -> dict[str, object]:
    """Copy mirror -> staging, verify attachments, then swap into active path."""
    if require_encrypted_mount:
        data_root = Path("/data")
        if not data_root.is_mount():
            raise FilestorePromoteError("Encrypted /data mount is unavailable")
        encrypted = data_root.resolve(strict=True)
        for path in (
            config.mirror_root,
            config.staging_root,
            config.backup_root,
            config.status_path,
        ):
            if not path.resolve(strict=False).is_relative_to(encrypted):
                raise FilestorePromoteError(
                    "Filestore promotion paths must remain under encrypted /data"
                )

    if not config.mirror_root.is_dir():
        raise FilestorePromoteError("Mirror filestore root is missing")

    _assert_private_dir(config.staging_root.parent)
    if config.staging_root.exists():
        shutil.rmtree(config.staging_root)
    shutil.copytree(config.mirror_root, config.staging_root, symlinks=False)

    summary = verify_attachment_files(config.staging_root, references)
    if not summary.ok:
        raise FilestorePromoteError(
            "Staged filestore failed attachment verification "
            f"(verified={summary.verified} total={summary.total} missing={summary.missing})"
        )

    _assert_private_dir(config.backup_root.parent)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = config.backup_root / f"active-before-promote-{timestamp}"
    if config.active_root.exists():
        if backup_path.exists():
            raise FilestorePromoteError("Backup path already exists")
        config.active_root.replace(backup_path)
    else:
        backup_path = None
        _assert_private_dir(config.active_root.parent)

    config.staging_root.replace(config.active_root)
    payload = {
        "schema_version": 1,
        "promoted_at_utc": datetime.now(UTC).isoformat(),
        "source_node_id": config.source_node_id,
        "source_generation": config.source_generation,
        "active_root": str(config.active_root),
        "backup_root": str(backup_path) if backup_path else None,
        "attachments_verified": summary.verified,
        "attachments_total": summary.total,
    }
    _write_status(config.status_path, payload)
    return payload


def rollback_filestore(config: FilestorePromoteConfig, backup_root: Path) -> None:
    """Restore a previously displaced active filestore directory."""
    if backup_root.is_symlink() or not backup_root.is_dir():
        raise FilestorePromoteError("Backup filestore path is invalid")
    if config.active_root.exists():
        failed = config.active_root.parent / f".failed-active-{os.getpid()}"
        config.active_root.replace(failed)
    backup_root.replace(config.active_root)
