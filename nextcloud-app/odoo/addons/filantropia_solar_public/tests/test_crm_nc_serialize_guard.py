"""Unit tests for CRM/NC serialize guard and webhook echo dampening."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class SerializationHelperTests(unittest.TestCase):
    def test_detects_serialize_message(self):
        from odoo.addons.filantropia_solar_public.models import crm_lead as m

        CrmLead = m.CrmLead
        self.assertTrue(
            CrmLead._fs_is_serialization_error(
                Exception("ERROR: could not serialize access due to concurrent update")
            )
        )
        self.assertTrue(
            CrmLead._fs_is_serialization_error(Exception("serialization failure"))
        )
        self.assertFalse(CrmLead._fs_is_serialization_error(Exception("HTTP 404")))

    def test_detects_nested_cause(self):
        from odoo.addons.filantropia_solar_public.models import crm_lead as m

        root = Exception("could not serialize access due to concurrent update")
        wrap = Exception("cursor error")
        wrap.__cause__ = root
        self.assertTrue(m.CrmLead._fs_is_serialization_error(wrap))


class FakeLeadEcho:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.fs_nc_sync_state = kwargs.get("fs_nc_sync_state", "ok")
        self.fs_nc_sync_origin = kwargs.get("fs_nc_sync_origin", "crm")
        self.fs_nc_last_sync_at = kwargs.get("fs_nc_last_sync_at")
        self.fs_nc_installation_id = kwargs.get("fs_nc_installation_id", "iid-1")
        self.fs_nc_db_id = kwargs.get("fs_nc_db_id", 15)

    def exists(self):
        return True


class EchoDampenTests(unittest.TestCase):
    def _sync(self):
        from odoo.addons.filantropia_solar_public.models.fs_station_sync import (
            FsStationSync,
        )

        return FsStationSync

    def test_pending_crm_is_echo(self):
        Sync = self._sync()
        lead = FakeLeadEcho(fs_nc_sync_state="pending", fs_nc_sync_origin="crm")
        self.assertTrue(
            Sync._is_crm_echo(Sync, lead, {"installation_id": "iid-1", "id": 15})
        )

    def test_recent_crm_origin_is_echo(self):
        Sync = self._sync()
        now = datetime(2026, 9, 1, 12, 0, 0)
        lead = FakeLeadEcho(
            fs_nc_sync_state="ok",
            fs_nc_sync_origin="crm",
            fs_nc_last_sync_at=now - timedelta(seconds=5),
        )
        with patch(
            "odoo.addons.filantropia_solar_public.models.fs_station_sync.fields.Datetime.now",
            return_value=now,
        ):
            self.assertTrue(
                Sync._is_crm_echo(Sync, lead, {"installation_id": "iid-1", "id": 15})
            )

    def test_old_crm_origin_not_echo(self):
        Sync = self._sync()
        now = datetime(2026, 9, 1, 12, 0, 0)
        lead = FakeLeadEcho(
            fs_nc_sync_state="ok",
            fs_nc_sync_origin="crm",
            fs_nc_last_sync_at=now - timedelta(seconds=60),
        )
        with patch(
            "odoo.addons.filantropia_solar_public.models.fs_station_sync.fields.Datetime.now",
            return_value=now,
        ):
            self.assertFalse(
                Sync._is_crm_echo(Sync, lead, {"installation_id": "iid-1", "id": 15})
            )

    def test_nc_origin_not_echo(self):
        Sync = self._sync()
        lead = FakeLeadEcho(
            fs_nc_sync_state="ok",
            fs_nc_sync_origin="nc",
            fs_nc_last_sync_at=datetime(2026, 9, 1, 12, 0, 0),
        )
        self.assertFalse(
            Sync._is_crm_echo(Sync, lead, {"installation_id": "iid-1", "id": 15})
        )


class SafeWriteTests(unittest.TestCase):
    def _fake_lead(self, crm_lead_module, write):
        lead = SimpleNamespace(
            ids=[1],
            _writes=0,
            env=SimpleNamespace(cr=SimpleNamespace(rollback=lambda: None)),
            _fs_is_serialization_error=(
                crm_lead_module.CrmLead._fs_is_serialization_error
            ),
        )
        lead.invalidate_recordset = lambda: None
        lead.with_context = lambda **_kwargs: lead
        lead.write = write
        return lead

    def test_safe_write_retries_then_soft_fails(self):
        from odoo.addons.filantropia_solar_public.models import crm_lead as m

        lead = self._fake_lead(m, lambda _vals: None)
        lead.ids = [46]

        def fail_write(_vals):
            lead._writes += 1
            raise Exception(
                "ERROR: could not serialize access due to concurrent update"
            )

        lead.write = fail_write
        with patch.object(m.time, "sleep", return_value=None):
            ok = m.CrmLead._fs_safe_write(lead, {"fs_nc_sync_state": "ok"}, attempts=3)
        self.assertFalse(ok)
        self.assertEqual(lead._writes, 3)

    def test_safe_write_succeeds(self):
        from odoo.addons.filantropia_solar_public.models import crm_lead as m

        lead = self._fake_lead(m, lambda _vals: True)
        self.assertTrue(m.CrmLead._fs_safe_write(lead, {"fs_nc_sync_state": "ok"}))


class WebhookRouteTests(unittest.TestCase):
    def test_json_lifecycle_route_uses_jsonrpc(self):
        from odoo.addons.filantropia_solar_public.controllers.nc_webhook import (
            FsNcWebhookController,
        )

        routing = FsNcWebhookController.lifecycle_event.routing
        self.assertEqual(routing["type"], "jsonrpc")

    def test_raw_lifecycle_http_route_is_preserved(self):
        from odoo.addons.filantropia_solar_public.controllers.nc_webhook import (
            FsNcWebhookController,
        )

        routing = FsNcWebhookController.lifecycle_event_http.routing
        self.assertEqual(routing["type"], "http")


if __name__ == "__main__":
    unittest.main()
