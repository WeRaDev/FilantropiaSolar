#!/usr/bin/env python3
"""Create verified Odoo DB+filestore bundles on TRL5 and off-host on Frank.

TRL5 retains complete local bundles under /opt/FilantropiaSolar/backups/odoo.
Frank stores verified off-host copies under the SFTP home only (not standby
runtime volumes). Intended for the daily 02:00 UTC timer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import fcntl
import hashlib
import logging
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile

_DATABASE = "filantropia_public"
_DB_CONTAINER = "filantropia-odoo-db"
_FILESTORE_DIR = Path(
    f"/var/lib/docker/volumes/nextcloud-app_odoo_data/_data/filestore/{_DATABASE}"
)
_SSH_HOST = "wera-ss-pt-sn-1.tailfb390c.ts.net"
_SSH_USER = "filantropia-backup"
_SSH_PORT = "22"
_SSH_KEY = Path("/etc/filantropia-backup/id_ed25519")
_KNOWN_HOSTS = Path("/etc/filantropia-backup/known_hosts")
_REMOTE_PREFIX = "filantropia-odoo-"
_BACKUP_NAME = re.compile(
    r"^filantropia-odoo-(?:(?:trl5|frank)-)?(\d{8}T\d{6}Z)\.tar$"
)
_PARTIAL_NAME = re.compile(
    r"^filantropia-odoo-(?:(?:trl5|frank)-)?(\d{8}T\d{6}Z)\.tar\.part$"
)
_RETENTION_DAYS = 30
_PARTIAL_RETENTION_DAYS = 2
_LOCK_FILE = Path("/run/lock/filantropia-odoo-backup.lock")
_LOCAL_BACKUP_DIR = Path(
    os.environ.get("FS_LOCAL_BACKUP_DIR", "/opt/FilantropiaSolar/backups/odoo")
)
_WRITER_NODE = os.environ.get("FS_EMBASSY_NODE_ID", "trl5").strip() or "trl5"

_LOGGER = logging.getLogger("filantropia_odoo_backup")


class BackupError(RuntimeError):
    """Raised when the recovery set cannot be safely published."""


def _run_checked(
    command: list[str],
    *,
    label: str,
    stdin=None,
    stdout=None,
    timeout: int = 3600,
) -> None:
    try:
        subprocess.run(
            command,
            check=True,
            stdin=stdin,
            stdout=stdout,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise BackupError(f"{label} failed") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_members(path: Path, *, expected: set[str] | None = None) -> list[str]:
    names: list[str] = []
    try:
        with tarfile.open(path, mode="r:") as archive:
            members = archive.getmembers()
            for member in members:
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts:
                    raise BackupError(f"Unsafe path in archive: {member.name}")
                if not (member.isfile() or member.isdir()):
                    raise BackupError(f"Unsupported entry in archive: {member.name}")
                names.append(member.name)
                if member.isfile():
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise BackupError(f"Unreadable archive entry: {member.name}")
                    with stream:
                        while stream.read(1024 * 1024):
                            pass
    except (OSError, tarfile.TarError) as exc:
        raise BackupError(f"Invalid archive: {path.name}") from exc

    if not names:
        raise BackupError(f"Empty archive: {path.name}")
    if expected is not None and set(names) != expected:
        raise BackupError(f"Unexpected contents in archive: {path.name}")
    return names


def _sftp(commands: list[str], *, timeout: int = 3600) -> str:
    command = [
        "sftp",
        "-b",
        "-",
        "-P",
        _SSH_PORT,
        "-i",
        str(_SSH_KEY),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        f"UserKnownHostsFile={_KNOWN_HOSTS}",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=6",
        f"{_SSH_USER}@{_SSH_HOST}",
    ]
    batch = "\n".join([*commands, "quit", ""])
    try:
        result = subprocess.run(
            command,
            input=batch,
            text=True,
            check=False,
            capture_output=True,
            timeout=timeout,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackupError("SFTP operation could not complete") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip().replace("\n", " | ")
        detail = detail[-500:] or "no-stderr"
        raise BackupError(f"SFTP batch failed (exit {result.returncode}): {detail}")
    return result.stdout


def _remote_names() -> list[str]:
    output = _sftp(["ls -1"])
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip() and not line.lstrip().startswith("sftp>")
    ]


def _prune_remote(now: datetime) -> None:
    cutoff = now - timedelta(days=_RETENTION_DAYS)
    partial_cutoff = now - timedelta(days=_PARTIAL_RETENTION_DAYS)
    expired: list[str] = []
    for name in _remote_names():
        backup_match = _BACKUP_NAME.fullmatch(name)
        partial_match = _PARTIAL_NAME.fullmatch(name)
        match = backup_match or partial_match
        if match is None:
            continue
        try:
            created = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(
                tzinfo=UTC
            )
        except ValueError:
            continue
        threshold = cutoff if backup_match else partial_cutoff
        if created < threshold:
            expired.append(name)
    if not expired:
        return
    try:
        _sftp([f"rm {name}" for name in expired])
    except BackupError:
        _LOGGER.warning("Backup published, but remote retention cleanup failed")
        return
    _LOGGER.info("Removed %s expired remote recovery set(s)", len(expired))


def _create_recovery_set(work_dir: Path, created_at: datetime) -> tuple[Path, str]:
    database_dump = work_dir / "odoo.dump"
    with database_dump.open("wb") as output:
        _run_checked(
            [
                "docker",
                "exec",
                _DB_CONTAINER,
                "pg_dump",
                "-U",
                "odoo",
                "-Fc",
                "--no-owner",
                "-d",
                _DATABASE,
            ],
            label="PostgreSQL dump",
            stdout=output,
        )
        output.flush()
        os.fsync(output.fileno())
    if database_dump.stat().st_size == 0:
        raise BackupError("PostgreSQL dump is empty")

    with database_dump.open("rb") as source:
        _run_checked(
            ["docker", "exec", "-i", _DB_CONTAINER, "pg_restore", "--list"],
            label="pg_restore validation",
            stdin=source,
            stdout=subprocess.DEVNULL,
            timeout=600,
        )

    filestore_archive = work_dir / "filestore.tar"
    try:
        with tarfile.open(
            filestore_archive, mode="w", format=tarfile.PAX_FORMAT
        ) as tar:
            tar.add(_FILESTORE_DIR, arcname=_DATABASE, recursive=True)
    except (OSError, tarfile.TarError) as exc:
        raise BackupError("Odoo filestore archive failed") from exc
    if filestore_archive.stat().st_size == 0:
        raise BackupError("Odoo filestore archive is empty")

    filestore_names = _validate_members(filestore_archive)
    if not any(
        PurePosixPath(name).parts[:1] == (_DATABASE,) for name in filestore_names
    ):
        raise BackupError("Filestore archive does not contain the database filestore")

    manifest = {
        "created_at_utc": created_at.isoformat(),
        "database": _DATABASE,
        "database_dump": database_dump.name,
        "database_sha256": _sha256(database_dump),
        "filestore_archive": filestore_archive.name,
        "filestore_sha256": _sha256(filestore_archive),
        "format_version": 1,
        "writer_node": _WRITER_NODE,
        "role": "trl5_complete_bundle",
    }
    manifest_path = work_dir / "MANIFEST.json"
    manifest_path.write_text(
        __import__("json").dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksums_path = work_dir / "SHA256SUMS.txt"
    checksums_path.write_text(
        f"{manifest['database_sha256']}  {database_dump.name}\n"
        f"{manifest['filestore_sha256']}  {filestore_archive.name}\n",
        encoding="ascii",
    )

    stamp = created_at.strftime("%Y%m%dT%H%M%SZ")
    node = _WRITER_NODE if _WRITER_NODE in {"trl5", "frank"} else "trl5"
    bundle_path = work_dir / f"{_REMOTE_PREFIX}{node}-{stamp}.tar"
    try:
        with tarfile.open(bundle_path, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for item in (
                database_dump,
                filestore_archive,
                manifest_path,
                checksums_path,
            ):
                tar.add(item, arcname=item.name, recursive=False)
    except (OSError, tarfile.TarError) as exc:
        raise BackupError("Recovery bundle creation failed") from exc

    _validate_members(
        bundle_path,
        expected={"odoo.dump", "filestore.tar", "MANIFEST.json", "SHA256SUMS.txt"},
    )
    return bundle_path, _sha256(bundle_path)


def _retain_local(bundle_path: Path, bundle_sha256: str, created_at: datetime) -> Path:
    if _LOCAL_BACKUP_DIR.is_symlink():
        raise BackupError("Local backup directory must not be a symlink")
    _LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    destination = _LOCAL_BACKUP_DIR / bundle_path.name
    tmp = destination.with_suffix(destination.suffix + ".part")
    tmp.write_bytes(bundle_path.read_bytes())
    with tmp.open("rb+") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    if _sha256(tmp) != bundle_sha256:
        tmp.unlink(missing_ok=True)
        raise BackupError("Local retained bundle checksum mismatch")
    tmp.replace(destination)
    destination.chmod(0o600)

    cutoff = created_at - timedelta(days=_RETENTION_DAYS)
    for path in _LOCAL_BACKUP_DIR.glob(f"{_REMOTE_PREFIX}*.tar"):
        match = _BACKUP_NAME.fullmatch(path.name)
        if match is None:
            continue
        try:
            created = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(
                tzinfo=UTC
            )
        except ValueError:
            continue
        if created < cutoff:
            path.unlink(missing_ok=True)
    return destination


def _publish(bundle_path: Path, bundle_sha256: str, created_at: datetime) -> str:
    final_name = bundle_path.name
    partial_name = f"{final_name}.part"
    roundtrip_path = bundle_path.with_name("roundtrip.tar")

    local_path = _retain_local(bundle_path, bundle_sha256, created_at)
    _LOGGER.info("Retained local complete bundle %s", local_path)

    _sftp(
        [
            f"put {bundle_path} {partial_name}",
            f"get {partial_name} {roundtrip_path}",
        ],
        timeout=3600,
    )
    if not roundtrip_path.is_file() or _sha256(roundtrip_path) != bundle_sha256:
        raise BackupError("Frank round-trip checksum mismatch; backup not published")

    _sftp([f"rename {partial_name} {final_name}"])
    if final_name not in _remote_names():
        raise BackupError("Frank did not list the published recovery set")
    return final_name


def backup() -> None:
    if os.geteuid() != 0:
        raise BackupError("This backup must run as root")
    if not _FILESTORE_DIR.is_dir():
        raise BackupError(f"Odoo filestore is missing: {_FILESTORE_DIR}")
    if not _SSH_KEY.is_file() or not _KNOWN_HOSTS.is_file():
        raise BackupError("Restricted SFTP identity or pinned host key is missing")

    os.umask(0o077)
    _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK_FILE.open("w", encoding="ascii") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BackupError("Another Odoo backup is already running") from exc

        created_at = datetime.now(UTC).replace(microsecond=0)
        with tempfile.TemporaryDirectory(
            prefix="filantropia-odoo-backup-", dir="/run"
        ) as temporary:
            work_dir = Path(temporary)
            bundle_path, bundle_sha256 = _create_recovery_set(work_dir, created_at)
            final_name = _publish(bundle_path, bundle_sha256, created_at)
            _LOGGER.info(
                "Published %s (bundle_sha256=%s, bundle_bytes=%s)",
                final_name,
                bundle_sha256,
                bundle_path.stat().st_size,
            )
            _prune_remote(created_at)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        backup()
    except BackupError as exc:
        _LOGGER.error("Odoo off-host backup failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
