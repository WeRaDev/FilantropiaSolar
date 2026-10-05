"""Collect bounded, read-only recovery evidence from the local Odoo standby."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess

from embassy.filestore import _write_marker
from embassy.replication import (
    AttachmentReference,
    heartbeat_age_seconds,
    parse_wal_lsn,
    verify_attachment_files,
    wal_lag_bytes,
)

_CONTAINER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_DATABASE_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,63}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_MAX_ATTACHMENT_REFERENCES = 50_000
_HEARTBEAT_ROW_FIELDS = 6
_ATTACHMENT_ROW_FIELDS = 3
_HASH_CHUNK_BYTES = 1024 * 1024


class StandbyStatusError(RuntimeError):
    """Raised when the standby evidence collector is misconfigured."""


def _required_path(config: dict[str, object], key: str) -> Path:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise StandbyStatusError(f"Standby path setting is missing: {key}")
    return Path(value)


def _private_json(path: Path) -> dict[str, object] | None:
    if path.is_symlink():
        raise StandbyStatusError(f"Standby marker must not be a symlink: {path.name}")
    if not path.exists():
        return None
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise StandbyStatusError(f"Standby marker is not private: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StandbyStatusError(f"Standby marker is invalid: {path.name}") from exc
    return value if isinstance(value, dict) else None


def _parse_json_output(output: str) -> object:
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise StandbyStatusError("Standby database returned invalid JSON") from exc


def _run_query(
    *,
    container: str,
    database: str,
    query: str,
    timeout_seconds: float,
) -> str:
    command = [
        "docker",
        "exec",
        container,
        "psql",
        "--no-psqlrc",
        "--quiet",
        "--tuples-only",
        "--no-align",
        "--set=ON_ERROR_STOP=1",
        "-U",
        "odoo",
        "-d",
        database,
        "-c",
        query,
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StandbyStatusError("Standby database query did not complete") from exc
    if result.returncode:
        raise StandbyStatusError("Standby database query failed")
    return result.stdout.strip()


def _addon_source_sha256(root: Path) -> str:
    resolved_root = root.resolve(strict=True)
    if not resolved_root.is_dir():
        raise ValueError("Odoo add-on source must be a directory")
    digest = hashlib.sha256()
    for path in sorted(resolved_root.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError("Odoo add-on source contains a symlink")
        if not path.is_file():
            continue
        digest.update(path.relative_to(resolved_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(_HASH_CHUNK_BYTES), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _addon_manifest_version(path: Path) -> str | None:
    try:
        manifest = ast.literal_eval(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None
    if not isinstance(manifest, dict):
        return None
    version = manifest.get("version")
    return version if isinstance(version, str) and version else None


def _positive_timeout(config: dict[str, object]) -> float:
    value = config.get("query_timeout_seconds", 30)
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise StandbyStatusError("Standby database query timeout must be positive")
    return float(value)


def _validate_config(config: dict[str, object]) -> tuple[str, str, float]:
    container = config.get("database_container", "filantropia-odoo-db")
    database = config.get("database_name", "filantropia_public")
    timeout = _positive_timeout(config)
    if not isinstance(container, str) or not _CONTAINER_PATTERN.fullmatch(container):
        raise StandbyStatusError("Standby database container name is invalid")
    if not isinstance(database, str) or not _DATABASE_PATTERN.fullmatch(database):
        raise StandbyStatusError("Standby database name is invalid")
    return container, database, timeout


def _source_row(
    *,
    container: str,
    database: str,
    timeout_seconds: float,
) -> tuple[
    str | None,
    str | None,
    float | None,
    int | None,
    str | None,
    str | None,
    str | None,
]:
    output = _run_query(
        container=container,
        database=database,
        query="""
SELECT json_build_array(
    node_id,
    writer_generation,
    heartbeat_at,
    wal_lsn::text,
    pg_last_wal_receive_lsn()::text,
    pg_last_wal_replay_lsn()::text
)::text
FROM fs_ops.replication_heartbeat
ORDER BY heartbeat_at DESC
LIMIT 1;
""",
        timeout_seconds=timeout_seconds,
    )
    row = _parse_json_output(output) if output else None
    if not isinstance(row, list) or len(row) != _HEARTBEAT_ROW_FIELDS:
        return None, None, None, None, None, None, None
    node_id, generation, timestamp, source_lsn, receive_lsn, replay_lsn = row
    if not all(isinstance(item, str) for item in (node_id, generation, timestamp)):
        return None, None, None, None, None, None, None
    try:
        age = heartbeat_age_seconds(timestamp, now=datetime.now(UTC))
    except ValueError:
        age = None
    lag = None
    if all(isinstance(item, str) for item in (source_lsn, receive_lsn, replay_lsn)):
        try:
            parse_wal_lsn(source_lsn)
            lag = wal_lag_bytes(receive_lsn, replay_lsn)
        except ValueError:
            lag = None
    return (
        node_id,
        generation,
        age,
        lag,
        source_lsn if isinstance(source_lsn, str) else None,
        receive_lsn if isinstance(receive_lsn, str) else None,
        replay_lsn if isinstance(replay_lsn, str) else None,
    )


def _installed_addon_version(
    *,
    container: str,
    database: str,
    timeout_seconds: float,
) -> str | None:
    output = _run_query(
        container=container,
        database=database,
        query="""
SELECT json_build_array(latest_version)::text
FROM ir_module_module
WHERE name = 'filantropia_solar_public'
  AND state = 'installed'
LIMIT 1;
""",
        timeout_seconds=timeout_seconds,
    )
    row = _parse_json_output(output) if output else None
    if not isinstance(row, list) or len(row) != 1:
        return None
    version = row[0]
    return version if isinstance(version, str) and version else None


def _attachment_references(
    *,
    container: str,
    database: str,
    timeout_seconds: float,
) -> list[AttachmentReference] | None:
    output = _run_query(
        container=container,
        database=database,
        query=f"""
SELECT COALESCE(json_agg(json_build_array(store_fname, checksum, file_size))::text, '[]')
FROM (
    SELECT store_fname, checksum, file_size
    FROM ir_attachment
    WHERE store_fname IS NOT NULL AND store_fname <> ''
    ORDER BY id
    LIMIT {_MAX_ATTACHMENT_REFERENCES + 1}
) AS attachments;
""",
        timeout_seconds=timeout_seconds,
    )
    rows = _parse_json_output(output)
    if not isinstance(rows, list) or len(rows) > _MAX_ATTACHMENT_REFERENCES:
        return None

    references: list[AttachmentReference] = []
    for row in rows:
        if not isinstance(row, list) or len(row) != _ATTACHMENT_ROW_FIELDS:
            return None
        store_fname, checksum, file_size = row
        if (
            not isinstance(store_fname, str)
            or not store_fname
            or not isinstance(checksum, str)
            or not re.fullmatch(r"[0-9a-fA-F]{40}", checksum)
            or isinstance(file_size, bool)
            or not isinstance(file_size, int)
            or file_size < 0
        ):
            return None
        references.append(
            AttachmentReference(
                store_fname=store_fname,
                checksum=checksum,
                file_size=file_size,
            )
        )
    return references


def _filestore_evidence(
    *,
    config: dict[str, object],
    container: str,
    database: str,
    timeout_seconds: float,
) -> tuple[str | None, float | None, bool, str | None, str | None]:
    marker = _private_json(_required_path(config, "filestore_marker"))
    source_node_id = marker.get("source_node_id") if marker else None
    source_generation = marker.get("source_generation") if marker else None
    completed_at = marker.get("completed_at_utc") if marker else None
    filestore_age = None
    if isinstance(completed_at, str):
        try:
            filestore_age = heartbeat_age_seconds(
                completed_at,
                now=datetime.now(UTC),
            )
        except ValueError:
            filestore_age = None

    verified_at = None
    all_verified = False
    try:
        references = _attachment_references(
            container=container,
            database=database,
            timeout_seconds=timeout_seconds,
        )
        if references is not None:
            summary = verify_attachment_files(
                _required_path(config, "filestore_root"),
                references,
            )
            if summary.ok:
                verified_at = datetime.now(UTC).isoformat()
                all_verified = True
    except (OSError, StandbyStatusError, ValueError):
        all_verified = False
    return (
        source_generation if isinstance(source_generation, str) else None,
        filestore_age,
        all_verified,
        verified_at,
        source_node_id if isinstance(source_node_id, str) else None,
    )


def _code_compatible(
    config: dict[str, object],
    *,
    installed_version: str | None,
) -> tuple[bool, str | None, str | None]:
    expected_version = config.get("expected_addon_version")
    expected_hash = config.get("expected_addon_source_sha256")
    source_dir = _required_path(config, "addon_source_directory")
    manifest_path = _required_path(config, "addon_manifest_path")
    if (
        not isinstance(expected_version, str)
        or not expected_version
        or not isinstance(expected_hash, str)
        or not _SHA256_PATTERN.fullmatch(expected_hash)
        or not manifest_path.resolve(strict=False).is_relative_to(
            source_dir.resolve(strict=False)
        )
    ):
        return False, None, None
    try:
        source_hash = _addon_source_sha256(source_dir)
    except (OSError, ValueError):
        return False, None, None
    manifest_version = _addon_manifest_version(manifest_path)
    compatible = (
        installed_version == expected_version
        and manifest_version == expected_version
        and source_hash.lower() == expected_hash.lower()
    )
    return compatible, installed_version, source_hash


def _base_status(now: datetime) -> dict[str, object]:
    return {
        "schema_version": 1,
        "observed_at_utc": now.isoformat(),
        "database_reachable": False,
        "database_in_recovery": None,
        "source_node_id": None,
        "source_generation": None,
        "replication_heartbeat_age_seconds": None,
        "replication_lag_bytes": None,
        "source_heartbeat_wal_lsn": None,
        "replication_receive_lsn": None,
        "replication_replay_lsn": None,
        "filestore_source_node_id": None,
        "filestore_source_generation": None,
        "filestore_generation_age_seconds": None,
        "all_attachments_verified": False,
        "attachment_verified_at_utc": None,
        "attachment_verification_age_seconds": None,
        "code_compatible": False,
        "addon_version": None,
        "addon_source_sha256": None,
    }


def collect_standby_status(
    config: dict[str, object],
    *,
    require_encrypted_mount: bool = True,
) -> dict[str, object]:
    """Refresh one private status file; unavailable evidence is reported as unknown."""
    if require_encrypted_mount:
        data_root = Path("/data")
        if not data_root.is_mount():
            raise StandbyStatusError("Encrypted /data mount is unavailable")
        encrypted_root = data_root.resolve(strict=True)
        for key in ("filestore_root", "filestore_marker"):
            if (
                not _required_path(config, key)
                .resolve(strict=False)
                .is_relative_to(encrypted_root)
            ):
                raise StandbyStatusError(
                    "Standby filestore must remain on encrypted /data"
                )

    container, database, timeout_seconds = _validate_config(config)
    status_path = _required_path(config, "status_file")
    if status_path.is_symlink():
        raise StandbyStatusError("Standby status file must not be a symlink")
    now = datetime.now(UTC)
    status = _base_status(now)
    try:
        role_output = _run_query(
            container=container,
            database=database,
            query="SELECT json_build_array(pg_is_in_recovery())::text;",
            timeout_seconds=timeout_seconds,
        )
        role = _parse_json_output(role_output)
    except StandbyStatusError:
        _write_marker(status_path, status)
        return status

    if not isinstance(role, list) or len(role) != 1 or not isinstance(role[0], bool):
        _write_marker(status_path, status)
        return status
    status["database_reachable"] = True
    status["database_in_recovery"] = role[0]
    if not role[0]:
        _write_marker(status_path, status)
        return status

    try:
        (
            source_node_id,
            source_generation,
            replication_age,
            replication_lag,
            source_heartbeat_wal_lsn,
            replication_receive_lsn,
            replication_replay_lsn,
        ) = _source_row(
            container=container,
            database=database,
            timeout_seconds=timeout_seconds,
        )
        installed_version = _installed_addon_version(
            container=container,
            database=database,
            timeout_seconds=timeout_seconds,
        )
        (
            filestore_generation,
            filestore_age,
            all_attachments_verified,
            attachment_verified_at,
            filestore_source_node_id,
        ) = _filestore_evidence(
            config=config,
            container=container,
            database=database,
            timeout_seconds=timeout_seconds,
        )
        code_compatible, addon_version, addon_source_hash = _code_compatible(
            config,
            installed_version=installed_version,
        )
    except (OSError, StandbyStatusError, ValueError):
        _write_marker(status_path, status)
        return status

    status.update(
        {
            "observed_at_utc": datetime.now(UTC).isoformat(),
            "source_node_id": source_node_id,
            "source_generation": source_generation,
            "replication_heartbeat_age_seconds": replication_age,
            "replication_lag_bytes": replication_lag,
            "source_heartbeat_wal_lsn": source_heartbeat_wal_lsn,
            "replication_receive_lsn": replication_receive_lsn,
            "replication_replay_lsn": replication_replay_lsn,
            "filestore_source_node_id": filestore_source_node_id,
            "filestore_source_generation": filestore_generation,
            "filestore_generation_age_seconds": filestore_age,
            "all_attachments_verified": all_attachments_verified,
            "attachment_verified_at_utc": attachment_verified_at,
            "attachment_verification_age_seconds": (
                0.0 if attachment_verified_at is not None else None
            ),
            "code_compatible": code_compatible,
            "addon_version": addon_version,
            "addon_source_sha256": addon_source_hash,
        }
    )
    _write_marker(status_path, status)
    return status
