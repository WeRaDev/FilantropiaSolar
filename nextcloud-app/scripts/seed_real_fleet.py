#!/usr/bin/env python3
"""Seed NC oc_fs_installations with the real Filantropia fleet (source=fleet).

Idempotent on serial_number = fleet-<slug>.
Capacity: inventory raw W / 1000 -> kWp (see data/real_fleet.json).

Usage (from host with docker):
  python3 nextcloud-app/scripts/seed_real_fleet.py
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FLEET_PATH = ROOT / "data" / "real_fleet.json"
DB_CONTAINER = "filantropia-db"
DB_USER = "nextcloud"
DB_PASS = "nextcloud_dev_password"
DB_NAME = "nextcloud"
# Stations dated on/after this calendar year stay planned until ops marks installed.
PLANNED_FROM_YEAR = 2026


def sql_escape(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s, flags=re.I)
    return s.strip("-")[:48]


def run_sql(sql: str) -> str:
    cmd = [
        "docker",
        "exec",
        "-i",
        DB_CONTAINER,
        "mariadb",
        f"-u{DB_USER}",
        f"-p{DB_PASS}",
        DB_NAME,
        "-N",
        "-e",
        sql,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "mariadb failed")
    return proc.stdout


def main() -> int:
    data = json.loads(FLEET_PATH.read_text(encoding="utf-8"))
    unit = data.get("capacity_unit", "W")
    stations = data["stations"]
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    created = 0
    updated = 0

    for st in stations:
        name = st["name"]
        serial = f"fleet-{slugify(name)}"
        raw = float(st["capacity_raw"])
        kwp = raw / 1000.0 if unit.upper() in {"W", "WP", "W_P"} else raw
        year = int(st["year"])
        notes_l = (st.get("notes") or "").lower()
        # Future-year or explicitly planned inventory stays planned until ops marks installed
        if year >= PLANNED_FROM_YEAR or "planned" in notes_l:
            lifecycle = "planned"
        else:
            lifecycle = "running"
        is_virtual = 1 if lifecycle == "virtual" else 0
        install_date = f"{year}-01-01"
        installed_at = f"{year}-01-01 00:00:00" if lifecycle == "running" else "NULL"
        org = (st.get("org") or "").strip()
        notes = (st.get("notes") or "").strip()
        desc_parts = []
        if org:
            desc_parts.append(org)
        if notes:
            desc_parts.append(notes)
        desc_parts.append(f"Fleet inventory year {year}.")
        short_description = " · ".join(desc_parts)
        lat = float(st["latitude"])
        lon = float(st["longitude"])
        location = st.get("location") or name

        existing = run_sql(
            f"SELECT id FROM oc_fs_installations WHERE serial_number={sql_escape(serial)} LIMIT 1;"
        ).strip()

        if existing:
            sql = f"""
UPDATE oc_fs_installations SET
  name={sql_escape(name)},
  location={sql_escape(location)},
  latitude={lat:.8f},
  longitude={lon:.8f},
  capacity_kwp={kwp:.2f},
  source='fleet',
  lifecycle_state={sql_escape(lifecycle)},
  is_virtual={is_virtual},
  soft_removed=0,
  installation_date={sql_escape(install_date)},
  installed_at={installed_at if installed_at == "NULL" else sql_escape(installed_at)},
  short_description={sql_escape(short_description)},
  nearest_location={sql_escape(location)},
  grid_price_kwh=0.1500,
  updated_at={sql_escape(now)}
WHERE id={int(existing)};
"""
            run_sql(sql)
            updated += 1
            print(f"updated id={existing} {name} {kwp} kWp {lifecycle}")
        else:
            sql = f"""
INSERT INTO oc_fs_installations (
  user_id, name, serial_number, location, latitude, longitude, capacity_kwp,
  grid_price_kwh, installation_date, created_at, updated_at, is_virtual, source,
  lifecycle_state, soft_removed, installed_at, short_description, nearest_location, error_flag
) VALUES (
  NULL,
  {sql_escape(name)},
  {sql_escape(serial)},
  {sql_escape(location)},
  {lat:.8f},
  {lon:.8f},
  {kwp:.2f},
  0.1500,
  {sql_escape(install_date)},
  {sql_escape(now)},
  {sql_escape(now)},
  {is_virtual},
  'fleet',
  {sql_escape(lifecycle)},
  0,
  {installed_at if installed_at == "NULL" else sql_escape(installed_at)},
  {sql_escape(short_description)},
  {sql_escape(location)},
  0
);
"""
            run_sql(sql)
            created += 1
            print(f"created {name} {kwp} kWp {lifecycle}")

    print(f"done created={created} updated={updated} total={len(stations)}")
    out = run_sql(
        "SELECT id,name,source,lifecycle_state,capacity_kwp FROM oc_fs_installations WHERE source='fleet' ORDER BY id;"
    )
    print(out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
