"""Unit tests for async enqueue helpers (no Odoo runtime)."""

from __future__ import annotations

import unittest


class FakeLead:
    """Minimal stand-in for crm.lead enqueue methods."""

    def __init__(self, lead_id=1, donation=True):
        self.id = lead_id
        self.fs_is_donation_application = donation
        self.writes = []
        self.created_sync = False
        self.promoted_sync = False
        self.delay_calls = []
        self._has_delay = True

    def write(self, vals):
        self.writes.append(vals)
        return True

    def with_delay(self, **kwargs):
        self.delay_calls.append(kwargs)
        parent = self

        class DelayProxy:
            def fs_create_virtual_station(self_inner):
                parent.created_sync = "delayed"

            def fs_promote_planned(self_inner):
                parent.promoted_sync = "delayed"

        return DelayProxy()

    def fs_create_virtual_station(self):
        self.created_sync = True
        return True

    def fs_promote_planned(self):
        self.promoted_sync = True
        return True

    # Copy of production enqueue logic (kept in sync with crm_lead.py)
    def fs_enqueue_create_virtual(self):
        for lead in [self]:
            if not lead.fs_is_donation_application:
                continue
            lead.write({"fs_nc_sync_state": "pending", "fs_nc_sync_error": False})
            if hasattr(lead, "with_delay") and lead._has_delay:
                lead.with_delay(
                    priority=10,
                    description=f"NC Virtual create for lead {lead.id}",
                    channel="root.filantropia",
                    identity_key=f"fs-virtual-{lead.id}",
                ).fs_create_virtual_station()
            else:
                lead.fs_create_virtual_station()
        return True

    def fs_enqueue_promote_planned(self):
        for lead in [self]:
            if not lead.fs_is_donation_application:
                continue
            if hasattr(lead, "with_delay") and lead._has_delay:
                lead.with_delay(
                    priority=10,
                    description=f"NC promote Planned for lead {lead.id}",
                    channel="root.filantropia",
                    identity_key=f"fs-promote-{lead.id}",
                ).fs_promote_planned()
            else:
                lead.fs_promote_planned()
        return True


class EnqueueTests(unittest.TestCase):
    def test_enqueue_create_uses_with_delay(self):
        lead = FakeLead(7)
        lead.fs_enqueue_create_virtual()
        self.assertEqual(lead.created_sync, "delayed")
        self.assertEqual(lead.writes[0]["fs_nc_sync_state"], "pending")
        self.assertEqual(lead.delay_calls[0]["identity_key"], "fs-virtual-7")
        self.assertEqual(lead.delay_calls[0]["channel"], "root.filantropia")

    def test_enqueue_promote_uses_with_delay(self):
        lead = FakeLead(3)
        lead.fs_enqueue_promote_planned()
        self.assertEqual(lead.promoted_sync, "delayed")
        self.assertEqual(lead.delay_calls[0]["identity_key"], "fs-promote-3")

    def test_enqueue_skips_non_donation(self):
        lead = FakeLead(1, donation=False)
        lead.fs_enqueue_create_virtual()
        self.assertFalse(lead.created_sync)
        self.assertEqual(lead.delay_calls, [])

    def test_fallback_sync_without_delay(self):
        lead = FakeLead(2)
        lead._has_delay = False
        lead.fs_enqueue_create_virtual()
        self.assertIs(lead.created_sync, True)
        self.assertEqual(lead.delay_calls, [])


if __name__ == "__main__":
    unittest.main()
