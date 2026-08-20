"""Unit tests for public website coordinate obfuscation (no Odoo runtime)."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest


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


if __name__ == "__main__":
    unittest.main()
