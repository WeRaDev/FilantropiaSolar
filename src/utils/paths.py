#!/usr/bin/env python3
r"""Cross-platform resource and user-data path helpers.

- get_resource_path: locate bundled resources (PyInstaller sys._MEIPASS) or repo-relative during dev
- get_app_cache_dir: user-writable cache/models directory (Windows: %LOCALAPPDATA%\FilantropiaSolar)
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


def get_project_root() -> Path:
    # src/utils/paths.py -> src -> project
    return Path(__file__).resolve().parents[2]


def get_resource_base() -> Path:
    # PyInstaller one-file exposes _MEIPASS; one-folder sets sys.frozen with executable path
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    if getattr(sys, "frozen", False):
        try:
            return Path(sys.executable).parent
        except Exception:
            pass
    # Pynsist: sys.prefix points to <AppDir>\\Python; resources live in <AppDir>
    try:
        app_python = Path(sys.prefix)
        app_dir = app_python.parent
        # Heuristic: nsist layout contains a 'pkgs' dir next to 'Python'
        if (app_dir / "pkgs").exists() and (app_dir / "Python").exists():
            return app_dir
    except Exception:
        pass
    # Dev fallback: project root
    return get_project_root()


def get_resource_path(rel: str | Path) -> Path:
    base = get_resource_base()
    return base / Path(rel)


def get_app_base_dir(app_name: str = "FilantropiaSolar") -> Path:
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / app_name
    # macOS/Linux default
    return Path.home() / f".{app_name.lower()}"


def get_app_cache_dir(subdir: str = "") -> Path:
    base = get_app_base_dir()
    cache = base / "cache"
    if subdir:
        cache = cache / subdir
    cache.mkdir(parents=True, exist_ok=True)
    return cache
