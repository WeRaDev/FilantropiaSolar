"""Local TRL5 writer controls; these do not provide independent fence proof."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import fcntl
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

_FENCE_FILE = Path(
    os.environ.get(
        "FILANTROPIA_ODOO_FENCE_FILE",
        "/etc/filantropia-embassy/odoo-fenced.json",
    )
)
_CONTROL_LOCK = Path(
    os.environ.get(
        "FILANTROPIA_ODOO_CONTROL_LOCK",
        "/run/lock/filantropia-odoo-control.lock",
    )
)
_ODOO_CONTAINER = "filantropia-odoo"
_DATABASE_CONTAINER = "filantropia-odoo-db"
_DATABASE = "filantropia_public"
_NODE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_REASON_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_HEARTBEAT_ROW_FIELDS = 3
_MAX_HEARTBEAT_AGE_SECONDS = 60.0
_LOGGER = logging.getLogger("filantropia_embassy_writer_control")


class WriterControlError(RuntimeError):
    """Raised when a local writer control cannot be verified safely."""


def _identity() -> tuple[str, str]:
    node_id = os.environ.get("FS_EMBASSY_NODE_ID", "").strip()
    generation = os.environ.get("FS_WRITER_GENERATION", "").strip()
    if (
        not _NODE_ID_PATTERN.fullmatch(node_id)
        or not _NODE_ID_PATTERN.fullmatch(generation)
        or "REPLACE_WITH" in generation
    ):
        raise WriterControlError("Writer identity is missing or invalid")
    return node_id, generation


@contextmanager
def _control_lock() -> Iterator[None]:
    if _CONTROL_LOCK.is_symlink():
        raise WriterControlError("Odoo control lock must not be a symlink")
    _CONTROL_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with _CONTROL_LOCK.open("a", encoding="ascii") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        yield


def _run_checked(command: list[str], *, label: str, timeout: int = 60) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WriterControlError(f"{label} did not complete") from exc
    if result.returncode:
        raise WriterControlError(f"{label} failed")
    return result.stdout.strip()


def _write_fence_marker(
    *,
    node_id: str,
    generation: str,
    reason: str,
) -> None:
    parent = _FENCE_FILE.parent
    if parent.is_symlink():
        raise WriterControlError("Odoo fence directory must not be a symlink")
    parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    parent_stat = parent.stat()
    if parent_stat.st_uid != 0 or parent_stat.st_mode & 0o022:
        raise WriterControlError("Odoo fence directory must be root-owned and private")
    if _FENCE_FILE.is_symlink():
        raise WriterControlError("Existing Odoo fence marker is a symlink")

    payload = {
        "schema_version": 1,
        "state": "fenced",
        "node_id": node_id,
        "writer_generation": generation,
        "reason": reason,
        "fenced_at_utc": datetime.now(UTC).isoformat(),
    }
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{_FENCE_FILE.name}.",
        suffix=".tmp",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            json.dump(payload, output, sort_keys=True, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(_FENCE_FILE)
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
        raise WriterControlError("Could not atomically persist the Odoo fence") from exc


def _read_fence_marker(*, node_id: str, generation: str) -> dict[str, object]:
    if _FENCE_FILE.is_symlink() or not _FENCE_FILE.is_file():
        raise WriterControlError("A regular persistent Odoo fence marker is required")
    marker_stat = _FENCE_FILE.stat()
    if marker_stat.st_uid != 0 or marker_stat.st_mode & 0o077:
        raise WriterControlError("Odoo fence marker must be root-owned and private")
    try:
        marker = json.loads(_FENCE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WriterControlError("Odoo fence marker is invalid") from exc
    if (
        not isinstance(marker, dict)
        or isinstance(marker.get("schema_version"), bool)
        or not isinstance(marker.get("schema_version"), int)
        or marker.get("schema_version") != 1
        or marker.get("state") != "fenced"
        or marker.get("node_id") != node_id
        or marker.get("writer_generation") != generation
    ):
        raise WriterControlError("Odoo fence marker identity does not match")
    return marker


def _container_state() -> tuple[bool, str] | None:
    names = _run_checked(
        ["docker", "ps", "-a", "--format", "{{.Names}}"],
        label="Docker container inventory",
    ).splitlines()
    if _ODOO_CONTAINER not in names:
        return None
    value = _run_checked(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Running}}|{{.HostConfig.RestartPolicy.Name}}",
            _ODOO_CONTAINER,
        ],
        label="Odoo container inspection",
    )
    running, separator, restart_policy = value.partition("|")
    if not separator or running not in {"true", "false"} or not restart_policy:
        raise WriterControlError("Odoo container state is invalid")
    return running == "true", restart_policy


def _verify_local_database(*, node_id: str, generation: str) -> None:
    query = f"""
SELECT json_build_array(
    NOT pg_is_in_recovery(),
    writer_generation,
    heartbeat_at
)::text
FROM fs_ops.replication_heartbeat
WHERE node_id = '{node_id}'
ORDER BY heartbeat_at DESC
LIMIT 1;
"""
    output = _run_checked(
        [
            "docker",
            "exec",
            _DATABASE_CONTAINER,
            "psql",
            "--no-psqlrc",
            "--quiet",
            "--tuples-only",
            "--no-align",
            "--set=ON_ERROR_STOP=1",
            "-U",
            "odoo",
            "-d",
            _DATABASE,
            "-c",
            query,
        ],
        label="Local Odoo database identity check",
    )
    try:
        row = json.loads(output)
    except json.JSONDecodeError as exc:
        raise WriterControlError("Local Odoo database identity is invalid") from exc
    if (
        not isinstance(row, list)
        or len(row) != _HEARTBEAT_ROW_FIELDS
        or row[0] is not True
        or row[1] != generation
        or not isinstance(row[2], str)
    ):
        raise WriterControlError("Local database is not the configured TRL5 writer")
    try:
        heartbeat_at = datetime.fromisoformat(row[2].replace("Z", "+00:00"))
    except ValueError as exc:
        raise WriterControlError("Local writer heartbeat timestamp is invalid") from exc
    if heartbeat_at.tzinfo is None or heartbeat_at.utcoffset() is None:
        raise WriterControlError("Local writer heartbeat must be timezone-aware")
    age_seconds = (datetime.now(UTC) - heartbeat_at.astimezone(UTC)).total_seconds()
    if not 0 <= age_seconds <= _MAX_HEARTBEAT_AGE_SECONDS:
        raise WriterControlError("Local writer heartbeat is stale or future-dated")


def _remove_fence_marker() -> None:
    if _FENCE_FILE.is_symlink():
        raise WriterControlError("Odoo fence marker became a symlink")
    _FENCE_FILE.unlink()
    directory_fd = os.open(
        _FENCE_FILE.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def fence_writer(*, reason: str = "operator_fence") -> None:
    if os.geteuid() != 0:
        raise WriterControlError("Odoo fencing must run as root")
    if not _REASON_PATTERN.fullmatch(reason):
        raise WriterControlError("Odoo fence reason is invalid")
    node_id, generation = _identity()
    with _control_lock():
        _write_fence_marker(
            node_id=node_id,
            generation=generation,
            reason=reason,
        )
        state = _container_state()
        if state is None:
            _LOGGER.warning("Odoo container is absent; persistent fence remains")
            return
        running, _restart_policy = state
        _run_checked(
            ["docker", "update", "--restart=no", _ODOO_CONTAINER],
            label="Odoo restart-policy disable",
        )
        if running:
            _run_checked(
                ["docker", "stop", "--time", "30", _ODOO_CONTAINER],
                label="Odoo writer stop",
            )
        state = _container_state()
        if state is None or state[0] or state[1] != "no":
            raise WriterControlError(
                "Odoo is not verifiably stopped with Docker restart disabled; "
                "persistent fence remains"
            )


def unfence_writer(*, confirm_other_writer_fenced: bool) -> None:
    if os.geteuid() != 0:
        raise WriterControlError("Odoo unfencing must run as root")
    if not confirm_other_writer_fenced:
        raise WriterControlError(
            "Explicit confirmation that every other writer is fenced is required"
        )
    node_id, generation = _identity()
    with _control_lock():
        _read_fence_marker(node_id=node_id, generation=generation)
        _verify_local_database(node_id=node_id, generation=generation)
        state = _container_state()
        if state is not None and (state[0] or state[1] != "no"):
            raise WriterControlError(
                "Odoo must remain stopped with Docker restart disabled before unfencing"
            )
        _remove_fence_marker()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fence", "unfence"))
    parser.add_argument("--reason", default="operator_fence")
    parser.add_argument(
        "--confirm-other-writer-fenced",
        action="store_true",
        help="operator attestation only; this is not independent fence evidence",
    )
    arguments = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        if arguments.action == "fence":
            fence_writer(reason=arguments.reason)
        else:
            unfence_writer(
                confirm_other_writer_fenced=arguments.confirm_other_writer_fenced,
            )
    except (WriterControlError, OSError) as exc:
        _LOGGER.error("Odoo writer control failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
