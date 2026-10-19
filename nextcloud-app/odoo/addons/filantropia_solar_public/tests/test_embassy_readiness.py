"""Isolated tests for the protected Odoo readiness route (no Odoo runtime)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ADDON_ROOT = Path(__file__).resolve().parents[1]
READINESS_PATH = ADDON_ROOT / "controllers" / "readiness.py"


class _Cursor:
    def __init__(self, *, database_primary=True, addon_version="19.0.2.35.0"):
        self.database_primary = database_primary
        self.addon_version = addon_version
        self.dbname = "filantropia_public"
        self.row = None
        self.fail = False
        self.query_count = 0

    def execute(self, query, _params=None):
        if self.fail:
            raise RuntimeError("database unavailable")
        self.query_count += 1
        if "pg_is_in_recovery" in query:
            self.row = (self.database_primary, "0/16B6C50")
        elif "fs_ops.replication_heartbeat" in query:
            self.row = (
                "generation-7",
                datetime.now(UTC) - timedelta(seconds=5),
                "0/16B6C40",
            )
        else:
            self.row = (self.addon_version,)

    def fetchone(self):
        return self.row


class _FakeRequest:
    def __init__(self, cursor, *, authorization):
        self.env = types.SimpleNamespace(cr=cursor)
        self.httprequest = types.SimpleNamespace(
            headers={"Authorization": authorization},
        )

    @staticmethod
    def make_response(body, *, headers, status):
        return types.SimpleNamespace(body=body, headers=headers, status=status)


def _load_controller():
    odoo = types.ModuleType("odoo")
    http_module = types.ModuleType("odoo.http")
    tools_module = types.ModuleType("odoo.tools")

    class _Controller:
        pass

    def route(*_args, **_kwargs):
        return lambda function: function

    http_module.Controller = _Controller
    http_module.route = route
    http_module.request = None
    tools_module.config = types.SimpleNamespace(filestore=lambda _database: "/tmp")
    odoo.http = http_module
    odoo.tools = tools_module
    sys.modules["odoo"] = odoo
    sys.modules["odoo.http"] = http_module
    sys.modules["odoo.tools"] = tools_module

    spec = importlib.util.spec_from_file_location(
        "fs_embassy_readiness_test",
        READINESS_PATH,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load controller from {READINESS_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EmbassyReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_controller()

    def _controller(self, cursor=None, *, authorization="Bearer test-token"):
        self.module.request = _FakeRequest(
            cursor or _Cursor(),
            authorization=authorization,
        )
        return self.module.EmbassyReadinessController()

    @staticmethod
    def _env():
        return {
            "FS_EMBASSY_READINESS_TOKEN": "test-token",
            "FS_EMBASSY_NODE_ID": "trl5",
            "FS_WRITER_GENERATION": "generation-7",
            "FS_EMBASSY_MAINTENANCE_FILE": "",
        }

    def test_valid_request_returns_origin_database_and_freshness_metadata(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(os.environ, self._env(), clear=False),
            patch.object(
                self.module.config,
                "filestore",
                return_value=temporary,
            ),
        ):
            response = self._controller().embassy_readiness()

        payload = json.loads(response.body)
        self.assertEqual(response.status, 200)
        self.assertTrue(payload["ready"])
        self.assertTrue(payload["database_is_primary"])
        self.assertEqual(payload["node_id"], "trl5")
        self.assertEqual(payload["writer_generation"], "generation-7")
        self.assertEqual(payload["addon_version"], "19.0.2.35.0")
        self.assertEqual(payload["current_wal_lsn"], "0/16B6C50")
        self.assertEqual(
            payload["replication_heartbeat_generation"],
            "generation-7",
        )
        self.assertLessEqual(payload["replication_heartbeat_age_seconds"], 60)
        self.assertIn(
            ("Cache-Control", "no-store, no-cache, max-age=0, must-revalidate"),
            response.headers,
        )

    def test_unauthorized_request_does_not_query_database(self):
        cursor = _Cursor()
        with patch.dict(os.environ, self._env(), clear=False):
            response = self._controller(
                cursor,
                authorization="Bearer wrong",
            ).embassy_readiness()

        self.assertEqual(response.status, 404)
        self.assertEqual(json.loads(response.body), {"ready": False})
        self.assertEqual(cursor.query_count, 0)

    def test_missing_identity_configuration_fails_readiness_closed(self):
        with patch.dict(os.environ, {"FS_EMBASSY_READINESS_TOKEN": "test-token"}):
            response = self._controller().embassy_readiness()

        self.assertEqual(response.status, 503)
        self.assertEqual(
            json.loads(response.body)["reason"],
            "readiness_identity_unconfigured",
        )

    def test_standby_database_and_unavailable_filestore_are_not_ready(self):
        with (
            patch.dict(os.environ, self._env(), clear=False),
            patch.object(
                self.module.config,
                "filestore",
                return_value="/path/that/does/not/exist",
            ),
        ):
            response = self._controller(
                _Cursor(database_primary=False),
            ).embassy_readiness()

        payload = json.loads(response.body)
        self.assertEqual(response.status, 503)
        self.assertFalse(payload["ready"])
        self.assertFalse(payload["database_is_primary"])
        self.assertFalse(payload["filestore_available"])

    def test_database_errors_return_generic_non_cacheable_failure(self):
        cursor = _Cursor()
        cursor.fail = True
        with patch.dict(os.environ, self._env(), clear=False):
            response = self._controller(cursor).embassy_readiness()

        self.assertEqual(response.status, 503)
        self.assertEqual(
            json.loads(response.body)["reason"],
            "readiness_probe_failed",
        )
        self.assertIn(("Pragma", "no-cache"), response.headers)

    def test_active_maintenance_marker_suppresses_normal_readiness(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "maintenance.json"
            marker.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "expires_at_utc": (
                            datetime.now(UTC) + timedelta(minutes=5)
                        ).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            environment = {
                **self._env(),
                "FS_EMBASSY_MAINTENANCE_FILE": str(marker),
            }
            with (
                patch.dict(os.environ, environment, clear=False),
                patch.object(
                    self.module.config,
                    "filestore",
                    return_value=temporary,
                ),
            ):
                response = self._controller().embassy_readiness()

        payload = json.loads(response.body)
        self.assertEqual(response.status, 503)
        self.assertTrue(payload["maintenance_active"])
        self.assertFalse(payload["ready"])

    def test_expired_maintenance_marker_no_longer_suppresses_readiness(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "maintenance.json"
            marker.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "expires_at_utc": (
                            datetime.now(UTC) - timedelta(seconds=1)
                        ).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            environment = {
                **self._env(),
                "FS_EMBASSY_MAINTENANCE_FILE": str(marker),
            }
            with (
                patch.dict(os.environ, environment, clear=False),
                patch.object(
                    self.module.config,
                    "filestore",
                    return_value=temporary,
                ),
            ):
                response = self._controller().embassy_readiness()

        payload = json.loads(response.body)
        self.assertEqual(response.status, 200)
        self.assertFalse(payload["maintenance_active"])
        self.assertTrue(payload["ready"])

    def test_boolean_schema_version_is_treated_as_malformed_maintenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "maintenance.json"
            marker.write_text(
                json.dumps(
                    {
                        "schema_version": True,
                        "expires_at_utc": (
                            datetime.now(UTC) + timedelta(minutes=5)
                        ).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            environment = {
                **self._env(),
                "FS_EMBASSY_MAINTENANCE_FILE": str(marker),
            }
            with (
                patch.dict(os.environ, environment, clear=False),
                patch.object(
                    self.module.config,
                    "filestore",
                    return_value=temporary,
                ),
            ):
                response = self._controller().embassy_readiness()

        payload = json.loads(response.body)
        self.assertEqual(response.status, 503)
        self.assertTrue(payload["maintenance_active"])
        self.assertFalse(payload["ready"])

    def test_symlinked_maintenance_marker_fails_readiness_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            marker = root / "maintenance.json"
            marker.symlink_to(target)
            environment = {
                **self._env(),
                "FS_EMBASSY_MAINTENANCE_FILE": str(marker),
            }
            with (
                patch.dict(os.environ, environment, clear=False),
                patch.object(
                    self.module.config,
                    "filestore",
                    return_value=temporary,
                ),
            ):
                response = self._controller().embassy_readiness()

        payload = json.loads(response.body)
        self.assertEqual(response.status, 503)
        self.assertTrue(payload["maintenance_active"])
        self.assertFalse(payload["ready"])


if __name__ == "__main__":
    unittest.main()
