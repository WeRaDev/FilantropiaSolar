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
    is_qualified_stage,
    is_won_stage,
    lifecycle_action_for_stage_change,
)


class StageMapTests(unittest.TestCase):
    def test_qualified_detects_name(self):
        self.assertTrue(is_qualified_stage("Qualified"))
        self.assertTrue(is_qualified_stage("Qualificação"))
        self.assertFalse(is_qualified_stage("New"))

    def test_won_never_qualified(self):
        self.assertFalse(is_qualified_stage("Qualified", is_won=True))
        self.assertTrue(is_won_stage(is_won=True))
        self.assertTrue(is_won_stage(stage_name="Won"))

    def test_stage_change_promote_only(self):
        self.assertEqual(
            lifecycle_action_for_stage_change("New", "Qualified"),
            "promote_planned",
        )
        self.assertIsNone(
            lifecycle_action_for_stage_change("New", "Won", new_is_won=True)
        )
        self.assertIsNone(
            lifecycle_action_for_stage_change("Qualified", "Won", new_is_won=True)
        )
        self.assertIsNone(lifecycle_action_for_stage_change("Qualified", "Qualified"))


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
