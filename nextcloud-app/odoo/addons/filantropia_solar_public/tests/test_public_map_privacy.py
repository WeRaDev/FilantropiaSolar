"""Unit tests for public website coordinate obfuscation (no Odoo runtime)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib.util
import math
import os
from pathlib import Path
import sys
import types
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


def _load_controller_module():
    """Load main.py with lightweight odoo stubs for offline tests."""
    root = Path(__file__).resolve().parents[1]
    main_path = root / "controllers" / "main.py"

    odoo = types.ModuleType("odoo")
    odoo_http = types.ModuleType("odoo.http")

    class _Controller:
        pass

    class _Http:
        Controller = _Controller

        @staticmethod
        def route(*_a, **_k):
            def deco(fn):
                return fn

            return deco

    odoo.http = _Http()
    odoo_http.Controller = _Controller
    odoo_http.request = None
    odoo_http.route = _Http.route

    sys.modules.setdefault("odoo", odoo)
    sys.modules.setdefault("odoo.http", odoo_http)
    sys.modules.setdefault("markupsafe", types.SimpleNamespace(Markup=str))

    spec = importlib.util.spec_from_file_location("fs_public_main", main_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class PublicMapPrivacyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_controller_module()
        cls.Ctrl = cls.mod.FilantropiaSolarPublicController

    def test_offset_within_5km_and_stable(self):
        lat0, lng0 = 38.7223, -9.1393
        seed = "fs-public-map:id:station-42"
        a = self.Ctrl._offset_public_coordinates(lat0, lng0, seed)
        b = self.Ctrl._offset_public_coordinates(lat0, lng0, seed)
        self.assertEqual(a, b)

        dlat_m = (a[0] - lat0) * self.mod._METERS_PER_DEG_LAT
        cos_lat = math.cos(math.radians(lat0))
        dlng_m = (a[1] - lng0) * self.mod._METERS_PER_DEG_LAT * cos_lat
        dist = math.hypot(dlat_m, dlng_m)
        self.assertGreater(dist, 50.0)
        self.assertLessEqual(dist, self.mod._PUBLIC_MAP_OFFSET_RADIUS_M + 1.0)

    def test_apply_privacy_replaces_coords(self):
        ctrl = self.Ctrl()
        # _as_float is instance method used by privacy helper
        out = ctrl._apply_public_location_privacy(
            {
                "id": "nc-7",
                "name": "Test Station",
                "latitude": 41.15,
                "longitude": -8.61,
                "exact_latitude": 41.15,
                "street": "Rua Secreta 1",
            }
        )
        self.assertTrue(out.get("location_is_approximate"))
        self.assertNotEqual(out["latitude"], 41.15)
        self.assertNotEqual(out["longitude"], -8.61)
        self.assertNotIn("exact_latitude", out)
        self.assertNotIn("street", out)

    def test_incomplete_or_invalid_coordinates_are_removed(self):
        ctrl = self.Ctrl()
        for station in (
            {
                "latitude": 41.15,
                "exact_longitude": -8.61,
                "street": "Rua Secreta 1",
            },
            {
                "latitude": 400.0,
                "longitude": -800.0,
                "coordinates": [400.0, -800.0],
            },
        ):
            with self.subTest(station=station):
                out = ctrl._apply_public_location_privacy(station)
                self.assertTrue(out["location_is_approximate"])
                self.assertNotIn("latitude", out)
                self.assertNotIn("longitude", out)
                self.assertNotIn("exact_longitude", out)
                self.assertNotIn("street", out)
                self.assertNotIn("coordinates", out)


class PublicSnapshotFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_controller_module()
        cls.Ctrl = cls.mod.FilantropiaSolarPublicController

    @staticmethod
    def _request_with_snapshot(snapshot):
        class SnapshotModel:
            def sudo(self):
                return self

            def _get_current(self):
                return snapshot

        return SimpleNamespace(
            env={"fs.public.snapshot": SnapshotModel()},
        )

    @staticmethod
    def _safe_snapshot():
        return SimpleNamespace(
            stations_data=[
                {
                    "id": "saved-station",
                    "latitude": 41.15001,
                    "longitude": -8.61001,
                    "location_is_approximate": True,
                }
            ],
            dashboard_data={"station_count": 1, "total_capacity_kwp": 5.5},
            refreshed_at=datetime.now(UTC) - timedelta(minutes=8),
        )

    def test_live_responses_are_returned_as_public_enriched_data(self):
        ctrl = self.Ctrl()

        def fetch(endpoint):
            if endpoint == "stations":
                return {
                    "success": True,
                    "stations": [
                        {
                            "id": "live-station",
                            "name": "Live station",
                            "latitude": 41.15,
                            "longitude": -8.61,
                            "exact_latitude": 41.15,
                        }
                    ],
                }
            return {
                "success": True,
                "station_count": 1,
                "total_capacity_kwp": 5.5,
                "locations": ["Porto"],
            }

        ctrl._fetch_json = fetch
        stations, dashboard, error = ctrl._get_public_data()

        self.assertIsNone(error)
        self.assertEqual(dashboard["station_count"], 1)
        self.assertEqual(len(stations), 1)
        self.assertTrue(stations[0]["location_is_approximate"])
        self.assertNotEqual(stations[0]["latitude"], 41.15)
        self.assertNotIn("exact_latitude", stations[0])

    def test_partial_live_failure_uses_entire_last_complete_snapshot(self):
        ctrl = self.Ctrl()
        snapshot = self._safe_snapshot()
        calls = []

        def fetch(endpoint):
            calls.append(endpoint)
            if endpoint == "stations":
                return {"success": True, "stations": [{"id": "partial-live"}]}
            raise TimeoutError("Nextcloud dashboard timed out")

        ctrl._fetch_json = fetch
        with patch.object(self.mod, "request", self._request_with_snapshot(snapshot)):
            stations, dashboard, error = ctrl._get_public_data()

        self.assertEqual(calls, ["stations", "dashboard"])
        self.assertEqual(stations, snapshot.stations_data)
        self.assertEqual(dashboard, snapshot.dashboard_data)
        self.assertIn("UTC", error)
        self.assertIn("desatualizados", error)
        self.assertIn("último conjunto completo", error)

    def test_live_failure_without_snapshot_keeps_error_state(self):
        ctrl = self.Ctrl()
        ctrl._fetch_json = lambda _endpoint: (_ for _ in ()).throw(
            TimeoutError("Nextcloud unavailable")
        )
        with patch.object(self.mod, "request", self._request_with_snapshot(None)):
            stations, dashboard, error = ctrl._get_public_data()

        self.assertEqual(stations, [])
        self.assertEqual(dashboard["station_count"], "—")
        self.assertIn("estações", error)
        self.assertIn("Sem cópia datada", error)

    def test_offline_snapshot_is_dated_and_never_calls_nextcloud(self):
        ctrl = self.Ctrl()
        snapshot = self._safe_snapshot()
        with (
            patch.dict(os.environ, {"FS_NC_OFFLINE": "1"}),
            patch.object(self.mod, "request", self._request_with_snapshot(snapshot)),
            patch("urllib.request.urlopen") as urlopen,
        ):
            stations, dashboard, error = ctrl._get_public_data()
            with self.assertRaises(ConnectionError):
                ctrl._fetch_json("estimate", {"capacity_kwp": 5})

        urlopen.assert_not_called()
        self.assertEqual(stations, snapshot.stations_data)
        self.assertEqual(dashboard, snapshot.dashboard_data)
        self.assertIn("contingência", error)
        self.assertIn("UTC", error)
        self.assertIn("desatualizados", error)

    def test_offline_without_dated_snapshot_does_not_claim_zero_stations(self):
        ctrl = self.Ctrl()
        undated = self._safe_snapshot()
        undated.refreshed_at = None
        with (
            patch.dict(os.environ, {"FS_NC_OFFLINE": "1"}),
            patch.object(self.mod, "request", self._request_with_snapshot(undated)),
        ):
            stations, dashboard, error = ctrl._get_public_data()

        self.assertEqual(stations, [])
        self.assertEqual(dashboard["station_count"], "—")
        self.assertIn("Sem cópia datada", error)

    def test_future_snapshot_is_not_presented_as_fresh(self):
        ctrl = self.Ctrl()
        snapshot = self._safe_snapshot()
        snapshot.refreshed_at = datetime.now(UTC) + timedelta(hours=1)
        with (
            patch.dict(os.environ, {"FS_NC_OFFLINE": "1"}),
            patch.object(self.mod, "request", self._request_with_snapshot(snapshot)),
        ):
            stations, dashboard, error = ctrl._get_public_data()

        self.assertEqual(stations, [])
        self.assertEqual(dashboard["station_count"], "—")
        self.assertIn("Sem cópia datada", error)

    def test_live_fetch_uses_bounded_timeout(self):
        ctrl = self.Ctrl()
        response = MagicMock()
        response.read.return_value = b'{"success": true}'
        response.__enter__.return_value = response
        with (
            patch.dict(
                os.environ,
                {"FS_NC_OFFLINE": "0", "FS_NC_HTTP_TIMEOUT": "3"},
            ),
            patch("urllib.request.urlopen", return_value=response) as urlopen,
        ):
            self.assertTrue(ctrl._fetch_json("stations")["success"])

        self.assertEqual(urlopen.call_args.kwargs["timeout"], 3.0)


if __name__ == "__main__":
    unittest.main()
