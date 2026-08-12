import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)
_KEYS = (
    "filantropia_solar_public.page_inicio",
    "filantropia_solar_public.page_instalacoes",
    "filantropia_solar_public.page_contacto",
    "filantropia_solar_public.page_candidatura",
    "filantropia_solar_public.snippet_leaflet_map",
    "filantropia_solar_public.snippet_steps",
)


def migrate(cr, _version):
    try:
        env = api.Environment(cr, SUPERUSER_ID, {})
        View = env["ir.ui.view"].sudo()
        cows = View.search([("website_id", "!=", False), ("key", "in", list(_KEYS))])
        n = len(cows)
        if cows:
            cows.unlink()
        _logger.info(
            "filantropia_solar_public post-migrate: removed %s website COW views", n
        )
    except Exception:
        _logger.exception("filantropia_solar_public post-migrate COW reset failed")
