import logging
from odoo import SUPERUSER_ID, api
_logger = logging.getLogger(__name__)

def migrate(cr, _version):
    """Inventory only; never delete website COWs."""
    try:
        env = api.Environment(cr, SUPERUSER_ID, {})
        View = env["ir.ui.view"].sudo()
        cows = View.search([
            ("website_id", "!=", False),
            ("key", "like", "filantropia_solar_public.%"),
        ])
        _logger.info(
            "filantropia_solar_public 19.0.2.26.0: preserving %s website COW view(s)",
            len(cows),
        )
    except Exception:
        _logger.exception("19.0.2.26.0 post-migrate failed")
