"""One-way, no-delete filestore mirroring with atomic completed-generation state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import tempfile
import time

_SAFE_REMOTE_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class FilestoreSyncError(RuntimeError):
    """Raised when an encrypted, verified filestore sync cannot complete."""


@dataclass(frozen=True)
class FilestoreSyncConfig:
    remote_user: str
    remote_host: str
    remote_path: PurePosixPath
    local_path: Path
    ssh_key: Path
    known_hosts: Path
    status_path: Path
    source_node_id: str
    source_generation: str

    def __post_init__(self) -> None:
        if not _SAFE_REMOTE_PART.fullmatch(self.remote_user):
            raise ValueError("Invalid filestore replication user")
        if not _SAFE_REMOTE_PART.fullmatch(self.remote_host):
            raise ValueError("Invalid filestore replication host")
        if not self.remote_path.is_absolute() or ".." in self.remote_path.parts:
            raise ValueError(
                "Remote filestore path must be absolute and traversal-free"
            )
        if not self.source_node_id or not self.source_generation:
            raise ValueError("Filestore source identity and generation are required")


def build_rsync_command(config: FilestoreSyncConfig) -> list[str]:
    """Build an rsync command that never deletes and only publishes complete files."""
    ssh_command = shlex.join(
        [
            "ssh",
            "-i",
            str(config.ssh_key),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            f"UserKnownHostsFile={config.known_hosts}",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=2",
        ]
    )
    remote_source = (
        f"{config.remote_user}@{config.remote_host}:"
        f"{config.remote_path.as_posix().rstrip('/')}/"
    )
    return [
        "rsync",
        "--archive",
        "--numeric-ids",
        "--no-links",
        "--delay-updates",
        "--partial",
        "--partial-dir=.rsync-partial",
        "--timeout=45",
        "--quiet",
        "-e",
        ssh_command,
        remote_source,
        f"{config.local_path}/",
    ]


def _assert_encrypted_destination(path: Path) -> None:
    data_root = Path("/data")
    if not data_root.is_mount():
        raise FilestoreSyncError("Encrypted /data mount is unavailable")
    resolved_root = data_root.resolve(strict=True)
    if not path.resolve(strict=False).is_relative_to(resolved_root):
        raise FilestoreSyncError("Filestore target is outside encrypted /data")
    if path.exists() and path.is_symlink():
        raise FilestoreSyncError("Filestore target must not be a symlink")


def _write_marker(path: Path, marker: dict[str, object]) -> None:
    parent = path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if parent.stat().st_mode & 0o077:
        raise FilestoreSyncError("Filestore marker directory is not private")
    payload = (json.dumps(marker, sort_keys=True, separators=(",", ":")) + "\n").encode(
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
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
        directory_fd = os.open(
            parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise FilestoreSyncError(
            "Could not atomically publish filestore status"
        ) from exc


def sync_filestore(config: FilestoreSyncConfig) -> dict[str, object]:
    """Pull one complete rsync generation and publish its freshness marker."""
    _assert_encrypted_destination(config.local_path)
    _assert_encrypted_destination(config.status_path)
    if not config.ssh_key.is_file() or not config.known_hosts.is_file():
        raise FilestoreSyncError("Pinned SSH key or known-hosts file is missing")

    config.local_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if config.local_path.stat().st_mode & 0o077:
        raise FilestoreSyncError("Standby filestore directory is not private")

    started_at = datetime.now(UTC)
    started_monotonic = time.monotonic()
    try:
        result = subprocess.run(
            build_rsync_command(config),
            check=False,
            capture_output=True,
            timeout=60,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FilestoreSyncError("Filestore rsync did not complete") from exc
    if result.returncode:
        raise FilestoreSyncError(
            f"Filestore rsync failed with exit status {result.returncode}"
        )

    completed_at = datetime.now(UTC)
    marker = {
        "schema_version": 1,
        "source_node_id": config.source_node_id,
        "source_generation": config.source_generation,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": completed_at.isoformat(),
        "duration_seconds": round(time.monotonic() - started_monotonic, 3),
    }
    _write_marker(config.status_path, marker)
    return marker
