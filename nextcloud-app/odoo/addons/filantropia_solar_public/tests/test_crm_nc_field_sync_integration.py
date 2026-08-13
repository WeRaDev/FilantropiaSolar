"""Live integration tests: CRM <-> NC station snapshot field matrix.

Requires local Docker stack (filantropia-nextcloud :8080, filantropia-odoo :8069)
and FS public/lifecycle token at SolarSeed-v3/.secrets/filantropia_public_api_token
(or env FS_PUBLIC_API_TOKEN / FS_LIFECYCLE_API_TOKEN).

Run:
  python3 -m unittest tests.test_crm_nc_field_sync_integration -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
import unittest
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[5]
TOKEN_FILE = (
    REPO_ROOT.parent / "SolarSeed-v3" / ".secrets" / "filantropia_public_api_token"
)
NC_BASE = os.environ.get(
    "FS_LIFECYCLE_API_BASE_URL",
    "http://127.0.0.1:8080/apps/filantropia_solar/api/lifecycle/v1",
).rstrip("/")
ODOO_WEBHOOK = os.environ.get(
    "FS_ODOO_LIFECYCLE_WEBHOOK_URL",
    "http://127.0.0.1:8069/filantropia/nc/lifecycle/http",
)

# Canonical snapshot fields that must round-trip (ADR 0006 / ops matrix).
SNAPSHOT_KEYS = (
    "name",
    "location",
    "latitude",
    "longitude",
    "capacity_kwp",
    "grid_price_kwh",
    "website",
    "short_description",
    "lifecycle_state",
    "installation_id",
    "id",
    "odoo_lead_id",
)


def _load_token() -> str:
    tok = (
        os.environ.get("FS_LIFECYCLE_API_TOKEN")
        or os.environ.get("FS_PUBLIC_API_TOKEN")
        or ""
    ).strip()
    if tok:
        return tok
    if TOKEN_FILE.is_file():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    return ""


def _stack_up() -> bool:
    try:
        urllib.request.urlopen("http://127.0.0.1:8080/status.php", timeout=3)
        urllib.request.urlopen("http://127.0.0.1:8069/web/login", timeout=3)
        return True
    except Exception:
        return False


def _http_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
    timeout: float = 30.0,
) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _psql(sql: str) -> str:
    return subprocess.check_output(
        [
            "docker",
            "exec",
            "filantropia-odoo-db",
            "psql",
            "-U",
            "odoo",
            "-d",
            "filantropia_public",
            "-Atc",
            sql,
        ],
        text=True,
    ).strip()


def _odoo_shell(script: str) -> str:
    return subprocess.check_output(
        [
            "docker",
            "exec",
            "-i",
            "filantropia-odoo",
            "odoo",
            "shell",
            "-d",
            "filantropia_public",
            "--no-http",
        ],
        input=script,
        text=True,
        stderr=subprocess.STDOUT,
    )


@unittest.skipUnless(
    _stack_up() and bool(_load_token()), "local NC+Odoo stack/token required"
)
class CrmNcFieldSyncIntegrationTests(unittest.TestCase):
    """End-to-end checks for the station snapshot field matrix."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.token = _load_token()
        cls.station_db_id = 16  # ARIA Alcabadeche in local fleet
        cls.lead_id = None
        # Resolve lead via NC station
        st = _http_json(
            "GET",
            f"{NC_BASE}/stations/{cls.station_db_id}",
            token=cls.token,
        )["station"]
        cls.lead_id = int(st["odoo_lead_id"])
        cls.installation_id = st["installation_id"]
        cls._baseline = {
            "name": st.get("name") or "ARIA Alcabadeche",
            "location": st.get("location") or "Alcabadeche",
            "latitude": float(st.get("latitude") or 38.7336),
            "longitude": float(st.get("longitude") or -9.3014),
            "capacity_kwp": float(st.get("capacity_kwp") or 4.5),
            "grid_price_kwh": float(st.get("grid_price_kwh") or 0.15),
            "website": st.get("website") or "https://example.org/aria",
            "short_description": st.get("short_description")
            or "NGO · Fleet inventory year 2024.",
            "lifecycle_state": st.get("lifecycle_state") or "running",
        }

    def tearDown(self) -> None:
        # Best-effort restore baseline snapshot after each test.
        try:
            body = {
                **{
                    k: self._baseline[k]
                    for k in (
                        "name",
                        "location",
                        "latitude",
                        "longitude",
                        "capacity_kwp",
                        "grid_price_kwh",
                        "website",
                        "short_description",
                    )
                },
                "location_label": self._baseline["location"],
                "actor": "integration-teardown",
            }
            _http_json(
                "POST",
                f"{NC_BASE}/stations/{self.station_db_id}/profile",
                token=self.token,
                payload=body,
            )
            if self._baseline["lifecycle_state"] in ("virtual", "planned", "running"):
                _http_json(
                    "POST",
                    f"{NC_BASE}/stations/{self.station_db_id}/set-lifecycle",
                    token=self.token,
                    payload={
                        "lifecycle_state": self._baseline["lifecycle_state"],
                        "actor": "integration-teardown",
                    },
                )
            time.sleep(0.4)
        except Exception:
            pass

    def _crm_row(self) -> dict:
        sql = (
            "select id, name, partner_name, city, website, "
            "fs_nc_installation_id, fs_nc_db_id, fs_nc_lifecycle_state, "
            "fs_station_location_label, fs_station_latitude, fs_station_longitude, "
            "fs_station_capacity_kwp, fs_station_grid_price_kwh, fs_station_website, "
            "fs_station_short_description "
            f"from crm_lead where id={int(self.lead_id)}"
        )
        line = _psql(sql)
        parts = line.split("|")
        keys = [
            "id",
            "name",
            "partner_name",
            "city",
            "website",
            "fs_nc_installation_id",
            "fs_nc_db_id",
            "fs_nc_lifecycle_state",
            "fs_station_location_label",
            "fs_station_latitude",
            "fs_station_longitude",
            "fs_station_capacity_kwp",
            "fs_station_grid_price_kwh",
            "fs_station_website",
            "fs_station_short_description",
        ]
        return dict(zip(keys, parts, strict=False))

    def _nc_station(self) -> dict:
        return _http_json(
            "GET",
            f"{NC_BASE}/stations/{self.station_db_id}",
            token=self.token,
        )["station"]

    def test_01_nc_payload_exposes_all_snapshot_keys(self) -> None:
        st = self._nc_station()
        missing = [k for k in SNAPSHOT_KEYS if k not in st]
        self.assertEqual(missing, [], f"NC lifecycle payload missing keys: {missing}")
        self.assertIsNotNone(st.get("grid_price_kwh"))

    def test_02_nc_profile_updates_all_crm_snapshot_fields(self) -> None:
        marker = f"integ-{int(time.time())}"
        payload = {
            "name": f"ARIA {marker}",
            "location_label": f"Loc{marker[:6]}",
            "latitude": 38.8011,
            "longitude": -9.3901,
            "capacity_kwp": 4.75,
            "grid_price_kwh": 0.217,
            "website": f"https://example.org/{marker}",
            "short_description": f"desc {marker}",
            "actor": "integration-nc-profile",
        }
        resp = _http_json(
            "POST",
            f"{NC_BASE}/stations/{self.station_db_id}/profile",
            token=self.token,
            payload=payload,
        )
        self.assertTrue(resp.get("success"))
        time.sleep(1.0)
        crm = self._crm_row()
        self.assertEqual(crm["name"], payload["name"])
        self.assertEqual(crm["partner_name"], payload["name"])
        self.assertEqual(crm["fs_station_location_label"], payload["location_label"])
        self.assertEqual(crm["city"], payload["location_label"])
        self.assertAlmostEqual(
            float(crm["fs_station_latitude"]), payload["latitude"], places=4
        )
        self.assertAlmostEqual(
            float(crm["fs_station_longitude"]), payload["longitude"], places=4
        )
        self.assertAlmostEqual(
            float(crm["fs_station_capacity_kwp"]), payload["capacity_kwp"], places=3
        )
        self.assertAlmostEqual(
            float(crm["fs_station_grid_price_kwh"]), payload["grid_price_kwh"], places=3
        )
        self.assertEqual(crm["fs_station_website"], payload["website"])
        self.assertEqual(crm["website"], payload["website"])
        self.assertEqual(
            crm["fs_station_short_description"], payload["short_description"]
        )
        self.assertEqual(str(crm["fs_nc_db_id"]), str(self.station_db_id))

    def test_03_crm_push_updates_all_nc_snapshot_fields(self) -> None:
        marker = f"crm-{int(time.time())}"
        script = f"""
lead=env['crm.lead'].sudo().browse({int(self.lead_id)})
vals={{
    'name': 'CRM {marker}',
    'partner_name': 'CRM {marker}',
    'city': 'City{marker[:5]}',
    'website': 'https://example.org/crm-{marker}',
    'fs_station_location_label': 'City{marker[:5]}',
    'fs_station_latitude': 39.1111,
    'fs_station_longitude': -8.2222,
    'fs_station_capacity_kwp': 5.25,
    'fs_station_grid_price_kwh': 0.183,
    'fs_station_website': 'https://example.org/crm-{marker}',
    'fs_station_short_description': 'crm desc {marker}',
}}
lead.with_context(fs_skip_nc_enqueue=True).write(vals)
ok=lead.fs_push_station_profile()
print('PUSH_OK', ok)
print('SYNC', lead.fs_nc_sync_state)
try:
    env.cr.commit()
    print('COMMIT_OK')
except Exception as e:
    print('COMMIT_ERR', type(e).__name__)
    env.cr.rollback()
"""
        out = _odoo_shell(script)
        self.assertIn("PUSH_OK True", out)
        time.sleep(0.8)
        st = self._nc_station()
        self.assertEqual(st["name"], f"CRM {marker}")
        self.assertEqual(st["location"], f"City{marker[:5]}")
        self.assertAlmostEqual(float(st["latitude"]), 39.1111, places=4)
        self.assertAlmostEqual(float(st["longitude"]), -8.2222, places=4)
        self.assertAlmostEqual(float(st["capacity_kwp"]), 5.25, places=3)
        self.assertAlmostEqual(float(st["grid_price_kwh"]), 0.183, places=3)
        self.assertEqual(st["website"], f"https://example.org/crm-{marker}")
        self.assertEqual(st["short_description"], f"crm desc {marker}")

    def test_04_lifecycle_demotion_and_promotion_sync_stage(self) -> None:
        # running -> planned -> running
        for state, crm_stage_en in (
            ("planned", "Proposition"),
            ("running", "Installed"),
        ):
            resp = _http_json(
                "POST",
                f"{NC_BASE}/stations/{self.station_db_id}/set-lifecycle",
                token=self.token,
                payload={"lifecycle_state": state, "actor": "integration-lifecycle"},
            )
            self.assertTrue(resp.get("success"), resp)
            time.sleep(1.0)
            crm = self._crm_row()
            self.assertEqual(crm["fs_nc_lifecycle_state"], state)
            # stage name is translated JSON or plain
            stage = _psql(
                f"select s.name::text from crm_lead l join crm_stage s on s.id=l.stage_id where l.id={int(self.lead_id)}"
            )
            self.assertIn(crm_stage_en, stage)

    def test_05_installation_id_rewrite_keeps_same_lead(self) -> None:
        """Location-driven installation_id change must update same CRM lead via db id."""
        st = self._nc_station()
        fake_iid = f"RewriteLoc_fleet-aria-{int(time.time()) % 10000}"
        payload = {
            "success": True,
            "station": {
                "id": int(self.station_db_id),
                "installation_id": fake_iid,
                "lifecycle_state": st.get("lifecycle_state") or "running",
                "location": "RewriteLoc",
                "latitude": 38.5,
                "longitude": -9.5,
                "capacity_kwp": float(st.get("capacity_kwp") or 4.5),
                "grid_price_kwh": float(st.get("grid_price_kwh") or 0.15),
                "name": st.get("name") or "ARIA Alcabadeche",
                "odoo_lead_id": int(self.lead_id),
                "website": st.get("website"),
                "short_description": "rewrite iid smoke",
                "source": "fleet",
                "soft_removed": False,
                "public_category": "existing",
                "is_public": True,
            },
        }
        resp = _http_json(
            "POST",
            ODOO_WEBHOOK,
            token=self.token,
            payload=payload,
        )
        self.assertTrue(resp.get("success"), resp)
        self.assertEqual(int(resp.get("lead_id")), int(self.lead_id))
        crm = self._crm_row()
        self.assertEqual(crm["fs_nc_installation_id"], fake_iid)
        self.assertEqual(crm["fs_station_location_label"], "RewriteLoc")
        self.assertEqual(str(crm["fs_nc_db_id"]), str(self.station_db_id))

    def test_06_import_reconcile_fills_grid_price(self) -> None:
        out = _odoo_shell(
            "r=env['fs.station.sync'].import_all_from_nc(); print('IMPORT', r); env.cr.commit()\n"
        )
        self.assertIn("IMPORT", out)
        self.assertIn("'ok': True", out.replace("True", "True"))
        # After import, linked active leads should generally have grid from NC
        with_grid = int(
            _psql(
                "select count(*) from crm_lead where active and fs_nc_installation_id is not null "
                "and fs_station_grid_price_kwh is not null"
            )
        )
        linked = int(
            _psql(
                "select count(*) from crm_lead where active and fs_nc_installation_id is not null"
            )
        )
        self.assertGreater(linked, 0)
        self.assertGreaterEqual(with_grid, max(1, linked // 2))


if __name__ == "__main__":
    unittest.main()
