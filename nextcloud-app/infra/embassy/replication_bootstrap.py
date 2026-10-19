"""Guarded PostgreSQL physical-replication bootstrap helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SLOT = re.compile(r"^[a-z0-9_]{1,63}$")
_MAX_TCP_PORT = 65535


class ReplicationBootstrapError(RuntimeError):
    """Raised when a standby seed would be unsafe."""


@dataclass(frozen=True)
class ReplicationBootstrapConfig:
    primary_host: str
    primary_port: int
    replication_user: str
    replication_password_env: str
    data_directory: Path
    backup_directory: Path
    slot_name: str
    application_name: str
    status_path: Path

    def __post_init__(self) -> None:
        for value, label in (
            (self.primary_host, "primary_host"),
            (self.replication_user, "replication_user"),
            (self.application_name, "application_name"),
        ):
            if not _SAFE.fullmatch(value):
                raise ValueError(f"Invalid {label}")
        if not _SLOT.fullmatch(self.slot_name):
            raise ValueError("Invalid replication slot name")
        if self.primary_port <= 0 or self.primary_port > _MAX_TCP_PORT:
            raise ValueError("Invalid primary port")
        if not _SAFE.fullmatch(self.replication_password_env):
            raise ValueError("Invalid password environment name")


def _private_write_json(path: Path, payload: dict[str, object]) -> None:
    parent = path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise ReplicationBootstrapError("Status directory is not private")
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
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
        raise ReplicationBootstrapError("Could not publish bootstrap status") from exc


def data_directory_is_empty(path: Path) -> bool:
    if not path.exists():
        return True
    if path.is_symlink() or not path.is_dir():
        raise ReplicationBootstrapError("Data directory is invalid")
    return not any(path.iterdir())


def preserve_existing_data(config: ReplicationBootstrapConfig) -> Path | None:
    """Move a non-empty data directory aside instead of overwriting it."""
    if data_directory_is_empty(config.data_directory):
        return None
    config.backup_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = config.backup_directory / f"pgdata-before-seed-{stamp}"
    if target.exists():
        raise ReplicationBootstrapError("Backup target already exists")
    config.data_directory.replace(target)
    return target


def build_basebackup_command(config: ReplicationBootstrapConfig) -> list[str]:
    """Construct a pg_basebackup invocation; password stays in the environment."""
    return [
        "pg_basebackup",
        "-h",
        config.primary_host,
        "-p",
        str(config.primary_port),
        "-U",
        config.replication_user,
        "-D",
        str(config.data_directory),
        "-X",
        "stream",
        "-R",
        "-C",
        "-S",
        config.slot_name,
        "-A",
        "scram-sha-256",
        "--checkpoint=fast",
        "--progress",
    ]


def write_standby_signal_files(
    data_directory: Path,
    *,
    primary_conninfo: str,
) -> None:
    """Ensure standby.signal and a minimal postgresql.auto.conf exist."""
    if data_directory.is_symlink() or not data_directory.is_dir():
        raise ReplicationBootstrapError("Data directory is invalid")
    (data_directory / "standby.signal").write_text("", encoding="utf-8")
    auto = data_directory / "postgresql.auto.conf"
    content = f"primary_conninfo = '{primary_conninfo}'\n"
    auto.write_text(content, encoding="utf-8")
    auto.chmod(0o600)


def seed_standby(
    config: ReplicationBootstrapConfig,
    *,
    dry_run: bool = False,
    runner=subprocess.run,
) -> dict[str, object]:
    """Preserve existing data, then optionally run pg_basebackup."""
    password = os.environ.get(config.replication_password_env, "")
    if not password and not dry_run:
        raise ReplicationBootstrapError("Replication password environment is empty")

    preserved = None
    if not data_directory_is_empty(config.data_directory):
        # Refuse silent overwrite; caller must pass force via preserve step.
        raise ReplicationBootstrapError(
            "Refusing to overwrite non-empty PostgreSQL data directory; "
            "call preserve_existing_data first or empty the directory intentionally"
        )

    config.data_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    command = build_basebackup_command(config)
    payload: dict[str, object] = {
        "schema_version": 1,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "primary_host": config.primary_host,
        "slot_name": config.slot_name,
        "application_name": config.application_name,
        "command": command,
        "dry_run": dry_run,
        "preserved_data_directory": None,
    }
    if dry_run:
        payload["completed_at_utc"] = datetime.now(UTC).isoformat()
        payload["status"] = "dry_run"
        _private_write_json(config.status_path, payload)
        return payload

    env = {**os.environ, "LC_ALL": "C", "PGPASSWORD": password}
    try:
        result = runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=3600,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReplicationBootstrapError("pg_basebackup did not complete") from exc
    if result.returncode:
        raise ReplicationBootstrapError("pg_basebackup failed")
    payload["completed_at_utc"] = datetime.now(UTC).isoformat()
    payload["status"] = "seeded"
    payload["preserved_data_directory"] = str(preserved) if preserved else None
    _private_write_json(config.status_path, payload)
    return payload


def promote_standby_sql() -> str:
    """SQL used after lease acquisition to promote a physical standby."""
    return "SELECT pg_promote(wait_seconds => 60);"
