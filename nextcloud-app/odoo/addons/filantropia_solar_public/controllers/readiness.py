"""Private origin readiness endpoint for the Embassy failover observer."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path

from odoo import http
from odoo.http import request
from odoo.tools import config

_logger = logging.getLogger(__name__)
_READINESS_TOKEN_ENV = "FS_EMBASSY_READINESS_TOKEN"
_NODE_ID_ENV = "FS_EMBASSY_NODE_ID"
_WRITER_GENERATION_ENV = "FS_WRITER_GENERATION"
_MAINTENANCE_FILE_ENV = "FS_EMBASSY_MAINTENANCE_FILE"
_MAINTENANCE_SCHEMA_VERSION = 1
_MAX_HEARTBEAT_AGE_SECONDS = 60.0
_HASH_CHUNK_BYTES = 1024 * 1024
_READINESS_PATH = "/filantropia/embassy/readiness"
_CACHE_HEADERS = [
    ("Cache-Control", "no-store, no-cache, max-age=0, must-revalidate"),
    ("Pragma", "no-cache"),
    ("Expires", "0"),
    ("Vary", "Authorization"),
    ("Content-Type", "application/json; charset=utf-8"),
]


def _response(payload: dict[str, object], *, status: int):
    return request.make_response(
        json.dumps(payload, separators=(",", ":"), sort_keys=True),
        headers=_CACHE_HEADERS,
        status=status,
    )


def _authorized() -> bool:
    expected = os.environ.get(_READINESS_TOKEN_ENV, "")
    supplied = request.httprequest.headers.get("Authorization", "")
    return bool(expected) and hmac.compare_digest(supplied, f"Bearer {expected}")


def _maintenance_active() -> bool:
    marker = os.environ.get(_MAINTENANCE_FILE_ENV, "")
    if not marker:
        return False
    path = Path(marker)
    if path.is_symlink() or path.parent.is_symlink():
        return True
    if not path.exists():
        return False
    if not path.is_file():
        return True
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        schema_version = (
            payload.get("schema_version") if isinstance(payload, dict) else None
        )
        expires_value = (
            payload.get("expires_at_utc") if isinstance(payload, dict) else None
        )
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != _MAINTENANCE_SCHEMA_VERSION
            or not isinstance(expires_value, str)
        ):
            return True
        expires_at = datetime.fromisoformat(expires_value.replace("Z", "+00:00"))
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return True
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        return True
    return datetime.now(UTC) < expires_at.astimezone(UTC)


def _addon_source_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise OSError("Add-on source contains a symlink")
        if not path.is_file():
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(_HASH_CHUNK_BYTES), b""):
                digest.update(chunk)
    return digest.hexdigest()


class EmbassyReadinessController(http.Controller):
    @http.route(
        _READINESS_PATH,
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        sitemap=False,
    )
    def embassy_readiness(self):
        if not _authorized():
            return _response({"ready": False}, status=404)

        node_id = os.environ.get(_NODE_ID_ENV, "").strip()
        generation = os.environ.get(_WRITER_GENERATION_ENV, "").strip()
        if not all((node_id, generation)):
            return _response(
                {"ready": False, "reason": "readiness_identity_unconfigured"},
                status=503,
            )

        try:
            request.env.cr.execute(
                "SELECT NOT pg_is_in_recovery(), pg_current_wal_lsn()::text"
            )
            row = request.env.cr.fetchone()
            if row is None:
                raise RuntimeError("database role probe returned no row")
            database_is_primary, current_wal_lsn = row
            request.env.cr.execute(
                """
                SELECT writer_generation, heartbeat_at, wal_lsn::text
                FROM fs_ops.replication_heartbeat
                WHERE node_id = %s
                """,
                (node_id,),
            )
            heartbeat_row = request.env.cr.fetchone()
            database_name = request.env.cr.dbname
            filestore = Path(config.filestore(database_name))
            filestore_available = filestore.is_dir() and os.access(
                filestore, os.R_OK | os.X_OK
            )
            request.env.cr.execute(
                """
                SELECT latest_version
                FROM ir_module_module
                WHERE name = %s AND state = %s
                LIMIT 1
                """,
                ("filantropia_solar_public", "installed"),
            )
            addon_row = request.env.cr.fetchone()
            addon_version = addon_row[0] if addon_row else None
            source_sha256 = _addon_source_sha256(Path(__file__).resolve().parents[1])
        except Exception as exc:
            _logger.warning(
                "Embassy readiness check failed (%s)",
                type(exc).__name__,
            )
            return _response(
                {"ready": False, "reason": "readiness_probe_failed"},
                status=503,
            )

        maintenance_active = _maintenance_active()
        heartbeat_generation = heartbeat_row[0] if heartbeat_row else None
        heartbeat_at = heartbeat_row[1] if heartbeat_row else None
        heartbeat_wal_lsn = heartbeat_row[2] if heartbeat_row else None
        heartbeat_age_seconds = None
        if (
            isinstance(heartbeat_at, datetime)
            and heartbeat_at.tzinfo is not None
            and heartbeat_at.utcoffset() is not None
        ):
            heartbeat_age_seconds = (
                datetime.now(UTC) - heartbeat_at.astimezone(UTC)
            ).total_seconds()
        heartbeat_ready = (
            heartbeat_generation == generation
            and heartbeat_age_seconds is not None
            and 0 <= heartbeat_age_seconds <= _MAX_HEARTBEAT_AGE_SECONDS
        )
        ready = (
            bool(database_is_primary)
            and filestore_available
            and bool(addon_version)
            and heartbeat_ready
            and not maintenance_active
        )
        payload = {
            "addon_source_sha256": source_sha256,
            "addon_version": addon_version,
            "current_wal_lsn": current_wal_lsn,
            "database_is_primary": bool(database_is_primary),
            "filestore_available": filestore_available,
            "replication_heartbeat_age_seconds": heartbeat_age_seconds,
            "replication_heartbeat_generation": heartbeat_generation,
            "replication_heartbeat_wal_lsn": heartbeat_wal_lsn,
            "maintenance_active": maintenance_active,
            "node_id": node_id,
            "ready": ready,
            "writer_generation": generation,
        }
        return _response(payload, status=200 if ready else 503)
