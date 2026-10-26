"""Settings for FilantropiaSolar CRM notification recipients."""

from __future__ import annotations

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    fs_qualified_lead_user_id = fields.Many2one(
        "res.users",
        string="Qualified lead notification recipient",
        domain=[("active", "=", True), ("share", "=", False)],
        config_parameter="filantropia_solar_public.fs_qualified_lead_user_id",
        help="Internal user notified when a public website lead first enters Qualified.",
    )
