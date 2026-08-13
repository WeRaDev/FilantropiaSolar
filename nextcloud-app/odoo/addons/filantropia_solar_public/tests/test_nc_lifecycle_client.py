"""Pure unit tests for NC lifecycle client + stage map (no Odoo runtime)."""

from __future__ import annotations

import json
import os
from pathlib import Path

# Allow importing services without loading odoo package
import sys
import unittest
from unittest.mock import MagicMock, patch

ADDON = Path(__file__).resolve().parents[1]
if str(ADDON) not in sys.path:
    sys.path.insert(0, str(ADDON))

from services.nc_lifecycle_client import (
    NcLifecycleClient,
    NcLifecycleError,
    lifecycle_base_url,
    redact_secrets,
)
from services.stage_map import (
    is_installed_stage,
    is_proposition_stage,
    is_qualified_stage,
    is_won_stage,
    lifecycle_action_for_stage_change,
    nc_state_for_stage,
    stage_xmlid_for_nc_state,
)


class StageMapTests(unittest.TestCase):
    def test_qualified_detects_name(self):
        self.assertTrue(is_qualified_stage("Qualified"))
        self.assertTrue(is_qualified_stage("Qualificação"))
        self.assertFalse(is_qualified_stage("New"))

    def test_proposition_and_installed(self):
        self.assertTrue(is_proposition_stage("Proposition"))
        self.assertTrue(is_proposition_stage("Proposta"))
        self.assertTrue(is_installed_stage(stage_name="Installed"))
        self.assertTrue(is_installed_stage(is_won=True))
        self.assertTrue(is_won_stage(stage_name="Won"))  # alias

    def test_nc_state_for_stage(self):
        self.assertIsNone(nc_state_for_stage("New"))
        self.assertEqual(nc_state_for_stage("Qualified"), "virtual")
        self.assertEqual(nc_state_for_stage("Proposition"), "planned")
        self.assertEqual(nc_state_for_stage("Installed", is_won=True), "running")

    def test_stage_change_matrix(self):
        self.assertEqual(
            lifecycle_action_for_stage_change("New", "Qualified"),
            "ensure_virtual",
        )
        self.assertEqual(
            lifecycle_action_for_stage_change("Qualified", "Proposition"),
            "promote_planned",
        )
        self.assertEqual(
            lifecycle_action_for_stage_change(
                "Proposition", "Installed", new_is_won=True
            ),
            "mark_installed",
        )
        # Won name still maps to installed action (rename transition)
        self.assertEqual(
            lifecycle_action_for_stage_change("Proposition", "Won", new_is_won=True),
            "mark_installed",
        )
        self.assertIsNone(lifecycle_action_for_stage_change("Qualified", "Qualified"))
        self.assertIsNone(lifecycle_action_for_stage_change("New", "New"))

    def test_inbound_stage_xmlids(self):
        self.assertEqual(stage_xmlid_for_nc_state("virtual"), "crm.stage_lead2")
        self.assertEqual(stage_xmlid_for_nc_state("planned"), "crm.stage_lead3")
        self.assertEqual(stage_xmlid_for_nc_state("running"), "crm.stage_lead4")
        self.assertIsNone(stage_xmlid_for_nc_state(None))


class RedactTests(unittest.TestCase):
    def test_redact_bearer_and_hex(self):
        token = "a" * 48
        text = f"Authorization: Bearer {token} body={token}"
        out = redact_secrets(text)
        self.assertNotIn(token, out)
        self.assertIn("[REDACTED]", out)


class LifecycleUrlTests(unittest.TestCase):
    def test_derives_from_public_url(self):
        with patch.dict(
            os.environ,
            {
                "FS_API_BASE_URL": "http://nc/apps/filantropia_solar/api/public/v1",
                "FS_LIFECYCLE_API_BASE_URL": "",
            },
            clear=False,
        ):
            os.environ.pop("FS_LIFECYCLE_API_BASE_URL", None)
            self.assertEqual(
                lifecycle_base_url(),
                "http://nc/apps/filantropia_solar/api/lifecycle/v1",
            )


class ClientHttpTests(unittest.TestCase):
    def test_create_virtual_posts_json(self):
        payload = {
            "odoo_lead_id": 42,
            "name": "ONG",
            "latitude": 38.7,
            "longitude": -9.1,
            "capacity_kwp": 5.0,
        }
        response_body = json.dumps(
            {
                "success": True,
                "station": {
                    "id": 9,
                    "installation_id": "crm_lead42",
                    "lifecycle_state": "virtual",
                },
            }
        ).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with patch(
            "services.nc_lifecycle_client.urllib.request.urlopen",
            return_value=mock_resp,
        ) as urlopen:
            client = NcLifecycleClient(
                base_url="http://nc/apps/filantropia_solar/api/lifecycle/v1",
                token="secret-token-value-not-for-logs",
            )
            result = client.create_virtual(payload)
            self.assertTrue(result["success"])
            self.assertEqual(result["station"]["lifecycle_state"], "virtual")
            req = urlopen.call_args[0][0]
            self.assertEqual(req.get_method(), "POST")
            self.assertTrue(req.full_url.endswith("/stations/virtual"))
            self.assertIn("Bearer ", req.headers.get("Authorization", ""))

    def test_mark_installed_posts(self):
        response_body = json.dumps(
            {
                "success": True,
                "station": {
                    "id": 9,
                    "installation_id": "x",
                    "lifecycle_state": "running",
                },
            }
        ).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        with patch(
            "services.nc_lifecycle_client.urllib.request.urlopen",
            return_value=mock_resp,
        ) as urlopen:
            client = NcLifecycleClient(
                base_url="http://nc/api/lifecycle/v1", token="tok"
            )
            result = client.mark_installed("abc", actor="odoo-lead-1")
            self.assertEqual(result["station"]["lifecycle_state"], "running")
            req = urlopen.call_args[0][0]
            self.assertEqual(req.get_method(), "POST")
            self.assertTrue(req.full_url.endswith("/stations/abc/mark-installed"))

    def test_list_stations_excludes_dataset_by_default(self):
        response_body = json.dumps(
            {"success": True, "stations": [], "count": 0}
        ).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        with patch(
            "services.nc_lifecycle_client.urllib.request.urlopen",
            return_value=mock_resp,
        ) as urlopen:
            client = NcLifecycleClient(
                base_url="http://nc/api/lifecycle/v1", token="tok"
            )
            client.list_stations()
            req = urlopen.call_args[0][0]
            self.assertIn("include_dataset=0", req.full_url)
            self.assertIn("include_soft_removed=0", req.full_url)

    def test_bind_lead_posts(self):
        response_body = json.dumps(
            {
                "success": True,
                "station": {
                    "installation_id": "fleet_x",
                    "odoo_lead_id": 54,
                },
            }
        ).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        with patch(
            "services.nc_lifecycle_client.urllib.request.urlopen",
            return_value=mock_resp,
        ) as urlopen:
            client = NcLifecycleClient(
                base_url="http://nc/api/lifecycle/v1", token="tok"
            )
            result = client.bind_lead("fleet_x", 54)
            self.assertEqual(result["station"]["odoo_lead_id"], 54)
            req = urlopen.call_args[0][0]
            self.assertEqual(req.get_method(), "POST")
            self.assertTrue(req.full_url.endswith("/stations/fleet_x/bind-lead"))

    def test_http_error_does_not_include_token_in_exception(self):
        import urllib.error

        token = "supersecrettokenvalue0123456789abcdef"
        err = urllib.error.HTTPError(
            url="http://nc/x",
            code=401,
            msg="nope",
            hdrs=None,
            fp=None,
        )
        err.read = MagicMock(return_value=f"Bearer {token}".encode())  # type: ignore[method-assign]

        with patch(
            "services.nc_lifecycle_client.urllib.request.urlopen",
            side_effect=err,
        ):
            client = NcLifecycleClient(
                base_url="http://nc/api/lifecycle/v1", token=token
            )
            with self.assertRaises(NcLifecycleError) as ctx:
                client.promote_planned("abc")
            self.assertNotIn(token, str(ctx.exception))
            self.assertNotIn(token, ctx.exception.body or "")


if __name__ == "__main__":
    unittest.main()
