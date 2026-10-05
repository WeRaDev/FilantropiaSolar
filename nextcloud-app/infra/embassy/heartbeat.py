"""Write a tiny database heartbeat on the active PostgreSQL primary only."""

from __future__ import annotations

import logging
import os
import re
import subprocess

_IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_CONTAINER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_LOGGER = logging.getLogger("filantropia_embassy_heartbeat")


class HeartbeatError(RuntimeError):
    """Raised when an active-writer heartbeat cannot be persisted."""


def _validate(value: str, *, pattern: re.Pattern[str], field: str) -> str:
    if not pattern.fullmatch(value):
        raise HeartbeatError(f"Invalid {field} configuration")
    return value


def build_heartbeat_sql(*, node_id: str, generation: str) -> str:
    """Build SQL using values restricted to an identifier-safe character set."""
    _validate(node_id, pattern=_IDENTITY_PATTERN, field="node identity")
    _validate(generation, pattern=_IDENTITY_PATTERN, field="writer generation")
    return f"""
DO $embassy$
BEGIN
    IF pg_is_in_recovery() THEN
        RETURN;
    END IF;
    CREATE SCHEMA IF NOT EXISTS fs_ops;
    CREATE TABLE IF NOT EXISTS fs_ops.replication_heartbeat (
        node_id text PRIMARY KEY,
        writer_generation text NOT NULL,
        heartbeat_at timestamptz NOT NULL,
        wal_lsn pg_lsn NOT NULL
    );
    INSERT INTO fs_ops.replication_heartbeat
        (node_id, writer_generation, heartbeat_at, wal_lsn)
    VALUES
        ('{node_id}', '{generation}', clock_timestamp(), pg_current_wal_lsn())
    ON CONFLICT (node_id) DO UPDATE
    SET writer_generation = EXCLUDED.writer_generation,
        heartbeat_at = EXCLUDED.heartbeat_at,
        wal_lsn = EXCLUDED.wal_lsn;
END
$embassy$;
"""


def write_primary_heartbeat(
    *,
    container: str,
    node_id: str,
    generation: str,
) -> None:
    """Run the idempotent, recovery-aware SQL inside the configured DB container."""
    _validate(container, pattern=_CONTAINER_PATTERN, field="database container")
    sql = build_heartbeat_sql(node_id=node_id, generation=generation)
    command = [
        "docker",
        "exec",
        container,
        "psql",
        "--no-psqlrc",
        "--set=ON_ERROR_STOP=1",
        "-U",
        "odoo",
        "-d",
        "filantropia_public",
        "-c",
        sql,
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HeartbeatError("Database heartbeat command did not complete") from exc
    if result.returncode:
        raise HeartbeatError("Database heartbeat command failed")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    container = os.environ.get(
        "FS_REPLICATION_DB_CONTAINER",
        "filantropia-odoo-db",
    )
    node_id = os.environ.get("FS_REPLICATION_NODE_ID", "")
    generation = os.environ.get("FS_WRITER_GENERATION", "")
    try:
        write_primary_heartbeat(
            container=container,
            node_id=node_id,
            generation=generation,
        )
    except HeartbeatError as exc:
        _LOGGER.error("Odoo replication heartbeat failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
