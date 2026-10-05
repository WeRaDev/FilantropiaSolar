"""Configuration loader and CLI for the pull-based filestore mirror."""

from __future__ import annotations

import logging
import os
from pathlib import Path, PurePosixPath
import re

from embassy.filestore import FilestoreSyncConfig, FilestoreSyncError, sync_filestore

_REMOTE_PATH_PATTERN = re.compile(r"^/[A-Za-z0-9_./-]+$")
_LOGGER = logging.getLogger("filantropia_embassy_filestore")


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise FilestoreSyncError(f"Required filestore setting is missing: {name}")
    return value


def load_config() -> FilestoreSyncConfig:
    remote_path = _required("FS_FILESTORE_REMOTE_PATH")
    if not _REMOTE_PATH_PATTERN.fullmatch(remote_path):
        raise FilestoreSyncError("Remote filestore path contains invalid characters")
    return FilestoreSyncConfig(
        remote_user=_required("FS_FILESTORE_REMOTE_USER"),
        remote_host=_required("FS_FILESTORE_REMOTE_HOST"),
        remote_path=PurePosixPath(remote_path),
        local_path=Path(_required("FS_FILESTORE_LOCAL_PATH")),
        ssh_key=Path(_required("FS_FILESTORE_SSH_KEY")),
        known_hosts=Path(_required("FS_FILESTORE_KNOWN_HOSTS")),
        status_path=Path(_required("FS_FILESTORE_STATUS_PATH")),
        source_node_id=_required("FS_FILESTORE_SOURCE_NODE_ID"),
        source_generation=_required("FS_FILESTORE_SOURCE_GENERATION"),
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        marker = sync_filestore(load_config())
    except (FilestoreSyncError, ValueError) as exc:
        _LOGGER.error("Odoo filestore mirror failed: %s", exc)
        return 1
    _LOGGER.info(
        "Filestore generation complete: source=%s generation=%s duration=%ss",
        marker["source_node_id"],
        marker["source_generation"],
        marker["duration_seconds"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
