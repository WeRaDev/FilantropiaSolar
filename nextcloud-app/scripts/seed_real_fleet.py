#!/usr/bin/env python3
"""Seed NC oc_fs_installations with the real Filantropia fleet (source=fleet).

Idempotent on serial_number = fleet-<slug>.
Capacity: inventory raw W / 1000 -> kWp (see data/real_fleet.json).
install_date: ISO YYYY-MM-DD in real_fleet.json (ops truth DD/MM/YYYY).

Usage (from host with docker):
  # MariaDB compose (filantropia-db):
  python3 nextcloud-app/scripts/seed_real_fleet.py
  # Nextcloud AIO Postgres:
  FS_DB_ENGINE=postgres FS_DB_CONTAINER=nextcloud-aio-database \
    FS_DB_USER=nextcloud FS_DB_NAME=nextcloud_database \
    FS_DB_PASS=... python3 nextcloud-app/scripts/seed_real_fleet.py
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
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


def parse_install_date(st: dict) -> tuple[str, int]:
    """Return (YYYY-MM-DD, year) from install_date or legacy year field."""
    raw = (st.get("install_date") or st.get("installation_date") or "").strip()
    if raw:
        # Accept YYYY-MM-DD or DD/MM/YYYY
        if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
            year = int(raw[:4])
            return raw, year
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return f"{y:04d}-{mo:02d}-{d:02d}", y
        # ISO datetime prefix
        if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
            return raw[:10], int(raw[:4])
    if "year" in st and st["year"] is not None:
        year = int(st["year"])
        return f"{year:04d}-01-01", year
    raise ValueError(f"station {st.get('name')!r} missing install_date/year")


def db_engine() -> str:
    return (os.environ.get("FS_DB_ENGINE") or "mysql").strip().lower()


def sql_bool(value: bool) -> str:
    """Boolean literal for MySQL/MariaDB (0/1) or Postgres (FALSE/TRUE)."""
    if db_engine() in {"postgres", "postgresql", "pg"}:
        return "TRUE" if value else "FALSE"
    return "1" if value else "0"


def run_sql(sql: str) -> str:
    # Prefer env override for TRL5 / non-dev passwords (never log the value).
    db_pass = (
        os.environ.get("FS_DB_PASS")
        or os.environ.get("MYSQL_PASSWORD")
        or os.environ.get("POSTGRES_PASSWORD")
        or DB_PASS
    )
    db_container = os.environ.get("FS_DB_CONTAINER", DB_CONTAINER)
    db_user = os.environ.get("FS_DB_USER", DB_USER)
    db_name = os.environ.get("FS_DB_NAME", DB_NAME)
    engine = db_engine()

    if engine in {"postgres", "postgresql", "pg"}:
        cmd = [
            "docker",
            "exec",
            "-i",
            db_container,
            "psql",
            "-U",
            db_user,
            "-d",
            db_name,
            "-v",
            "ON_ERROR_STOP=1",
            "-t",
            "-A",
            "-c",
            sql,
        ]
        env = os.environ.copy()
        if db_pass:
            env["PGPASSWORD"] = db_pass
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or "psql failed")
        return proc.stdout

    last_err = ""
    for client in ("mariadb", "mysql"):
        cmd = [
            "docker",
            "exec",
            "-i",
            db_container,
            client,
            f"-u{db_user}",
            f"-p{db_pass}",
            db_name,
            "-N",
            "-e",
            sql,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            return proc.stdout
        last_err = proc.stderr or proc.stdout or f"{client} failed"
        if (
            "not found" not in last_err.lower()
            and "executable file not found" not in last_err.lower()
        ):
            break
    raise RuntimeError(last_err or "sql client failed")


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
        install_date, year = parse_install_date(st)
        notes_l = (st.get("notes") or "").lower()
        # Future-year or explicitly planned inventory stays planned until ops marks installed
        if year >= PLANNED_FROM_YEAR or "planned" in notes_l:
            lifecycle = "planned"
        else:
            lifecycle = "running"
        grid_connection = (
            "off_grid" if "off-grid" in notes_l or "off_grid" in notes_l else "on_grid"
        )
        is_virtual_sql = sql_bool(lifecycle == "virtual")
        soft_removed_sql = sql_bool(False)
        error_flag_sql = sql_bool(False)
        installed_at = f"{install_date} 00:00:00" if lifecycle == "running" else "NULL"
        org = (st.get("org") or "").strip()
        notes = (st.get("notes") or "").strip()
        desc_parts = []
        if org:
            desc_parts.append(org)
        if notes:
            desc_parts.append(notes)
        desc_parts.append(f"Fleet install_date {install_date}.")
        short_description = " · ".join(desc_parts)
        lat = float(st["latitude"])
        lon = float(st["longitude"])
        location = st.get("location") or name

        existing = run_sql(
            f"SELECT id FROM oc_fs_installations WHERE serial_number={sql_escape(serial)} LIMIT 1;"
        ).strip()
        # Fallback: same fleet name (handles renames like Mount-Inn Horses -> Rita)
        if not existing:
            existing = run_sql(
                f"SELECT id FROM oc_fs_installations WHERE source='fleet' AND name={sql_escape(name)} LIMIT 1;"
            ).strip()
        # Capacity fallback for known renames (Rita was Mount-Inn Horses @ 1.38 kWp)
        rita_kwp = 1.38
        kwp_eps = 0.01
        if not existing and name == "Rita" and abs(kwp - rita_kwp) < kwp_eps:
            existing = run_sql(
                "SELECT id FROM oc_fs_installations WHERE source='fleet' "
                f"AND capacity_kwp BETWEEN {rita_kwp - kwp_eps:.2f} "
                f"AND {rita_kwp + kwp_eps:.2f} LIMIT 1;"
            ).strip()

        if existing:
            # existing may be "12" or "12\n"; take first token
            existing_id = int(str(existing).split()[0])
            sql = f"""
UPDATE oc_fs_installations SET
  name={sql_escape(name)},
  serial_number={sql_escape(serial)},
  location={sql_escape(location)},
  latitude={lat:.8f},
  longitude={lon:.8f},
  capacity_kwp={kwp:.2f},
  source='fleet',
  lifecycle_state={sql_escape(lifecycle)},
  is_virtual={is_virtual_sql},
  soft_removed={soft_removed_sql},
  installation_date={sql_escape(install_date)},
  installed_at={installed_at if installed_at == "NULL" else sql_escape(installed_at)},
  short_description={sql_escape(short_description)},
  nearest_location={sql_escape(location)},
  grid_price_kwh=0.1500,
  grid_connection_type={sql_escape(grid_connection)},
  updated_at={sql_escape(now)}
WHERE id={existing_id};
"""
            run_sql(sql)
            updated += 1
            print(
                f"updated id={existing_id} {name} {kwp} kWp {lifecycle} install={install_date} grid={grid_connection}"
            )
        else:
            sql = f"""
INSERT INTO oc_fs_installations (
  user_id, name, serial_number, location, latitude, longitude, capacity_kwp,
  grid_price_kwh, grid_connection_type, installation_date, created_at, updated_at, is_virtual, source,
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
  {sql_escape(grid_connection)},
  {sql_escape(install_date)},
  {sql_escape(now)},
  {sql_escape(now)},
  {is_virtual_sql},
  'fleet',
  {sql_escape(lifecycle)},
  {soft_removed_sql},
  {installed_at if installed_at == "NULL" else sql_escape(installed_at)},
  {sql_escape(short_description)},
  {sql_escape(location)},
  {error_flag_sql}
);
"""
            run_sql(sql)
            created += 1
            print(
                f"created {name} {kwp} kWp {lifecycle} install={install_date} grid={grid_connection}"
            )

    print(f"done created={created} updated={updated} total={len(stations)}")
    out = run_sql(
        "SELECT id, name, source, lifecycle_state, capacity_kwp, installation_date, grid_connection_type "
        "FROM oc_fs_installations WHERE source='fleet' ORDER BY id;"
    )
    print(out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
