import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_FS_VIEW_KEYS = (
    "filantropia_solar_public.page_inicio",
    "filantropia_solar_public.page_instalacoes",
    "filantropia_solar_public.page_contacto",
    "filantropia_solar_public.page_candidatura",
    "filantropia_solar_public.snippet_leaflet_map",
    "filantropia_solar_public.snippet_steps",
)


def migrate(cr, _version):
    """Preserve website COWs; inventory only. Never unlink on upgrade."""
    try:
        env = api.Environment(cr, SUPERUSER_ID, {})
        View = env["ir.ui.view"].sudo()
        cows = View.search(
            [("website_id", "!=", False), ("key", "in", list(_FS_VIEW_KEYS))]
        )
        if cows:
            detail = ", ".join(
                sorted(
                    {
                        f"{c.key}(ws={c.website_id.id},len={len(c.arch_db or '')})"
                        for c in cows
                    }
                )
            )
            _logger.info(
                "filantropia_solar_public 19.0.2.12.0: preserving %s website "
                "COW view(s): %s",
                len(cows),
                detail,
            )
        else:
            _logger.info(
                "filantropia_solar_public 19.0.2.12.0: no FS website COW views"
            )
    except Exception:
        _logger.exception(
            "filantropia_solar_public 19.0.2.12.0 post-migrate inventory failed"
        )
