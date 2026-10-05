"""Atomic, permission-restricted Embassy state and action journal."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import TYPE_CHECKING

_SCHEMA_VERSION = 1
_SENSITIVE_KEY_PARTS = (
    "authorization",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
if TYPE_CHECKING:
    from collections.abc import Iterator


class JournalError(RuntimeError):
    """Raised when Embassy state cannot be trusted or safely persisted."""


def _check_private_file(path: Path) -> None:
    if path.is_symlink():
        raise JournalError(f"Embassy state file must not be a symlink: {path.name}")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise JournalError(f"Embassy state file has unsafe permissions: {path.name}")


def _check_event_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if any(part in str(key).lower() for part in _SENSITIVE_KEY_PARTS):
                raise JournalError(f"Refusing to journal sensitive field: {key}")
            _check_event_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_event_keys(child)


class StateStore:
    """Persist a versioned JSON state document using same-directory replacement."""

    def __init__(self, path: Path):
        self.path = path

    def read(self) -> dict[str, object]:
        if self.path.is_symlink():
            raise JournalError("Embassy state must not be a symlink")
        if not self.path.exists():
            return {
                "schema_version": _SCHEMA_VERSION,
                "consecutive_primary_failures": 0,
            }
        _check_private_file(self.path)
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise JournalError(
                "Embassy state is unreadable; refusing to reset it"
            ) from exc
        if (
            not isinstance(state, dict)
            or type(state.get("schema_version")) is not int
            or state.get("schema_version") != _SCHEMA_VERSION
        ):
            raise JournalError("Embassy state schema is invalid; refusing to reset it")
        failures = state.get("consecutive_primary_failures")
        if isinstance(failures, bool) or not isinstance(failures, int) or failures < 0:
            raise JournalError("Embassy failure counter is invalid")
        return state

    def write(self, state: dict[str, object]) -> None:
        _check_event_keys(state)
        payload = dict(state)
        payload["schema_version"] = _SCHEMA_VERSION
        failures = payload.get("consecutive_primary_failures")
        if isinstance(failures, bool) or not isinstance(failures, int) or failures < 0:
            raise JournalError("Embassy failure counter is invalid")
        parent = self.path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if stat.S_IMODE(parent.stat().st_mode) & 0o077:
            raise JournalError(
                f"Embassy state directory has unsafe permissions: {parent}"
            )
        encoded = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "wb") as output:
                os.fchmod(output.fileno(), 0o600)
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(self.path)
            directory_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise JournalError("Could not atomically persist Embassy state") from exc


class EventJournal:
    """Append minimal, non-secret JSONL state transitions."""

    def __init__(self, path: Path):
        self.path = path

    def append(self, event: dict[str, object]) -> None:
        _check_event_keys(event)
        if self.path.is_symlink():
            raise JournalError("Embassy action journal must not be a symlink")
        parent = self.path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if stat.S_IMODE(parent.stat().st_mode) & 0o077:
            raise JournalError(
                f"Embassy journal directory has unsafe permissions: {parent}"
            )
        payload = (
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
        descriptor = os.open(self.path, flags, 0o600)
        try:
            if stat.S_IMODE(os.fstat(descriptor).st_mode) & 0o077:
                raise JournalError("Embassy action journal has unsafe permissions")
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


@contextmanager
def operation_lock(path: Path) -> Iterator[None]:
    """Serialize Embassy runs; overlapping timers fail rather than race."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
        raise JournalError(
            f"Embassy lock directory has unsafe permissions: {path.parent}"
        )
    if path.is_symlink():
        raise JournalError("Embassy operation lock must not be a symlink")
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if stat.S_IMODE(os.fstat(descriptor).st_mode) & 0o077:
            raise JournalError("Embassy operation lock has unsafe permissions")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise JournalError("Another Embassy run is already active") from exc
        yield
    finally:
        os.close(descriptor)
