import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_FS_VIEW_KEYS = (
    "filantropia_solar_public.page_inicio",
    "filantropia_solar_public.page_projetos",
    "filantropia_solar_public.page_instalacoes",
    "filantropia_solar_public.page_contacto",
    "filantropia_solar_public.page_candidatura",
    "filantropia_solar_public.snippet_leaflet_map",
    "filantropia_solar_public.snippet_steps",
)


def migrate(cr, _version):
    """Inventory COWs only. Never unlink published Website Builder content."""
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
                "filantropia_solar_public 19.0.2.25.0: preserving %s website "
                "COW view(s): %s",
                len(cows),
                detail,
            )
        else:
            _logger.info(
                "filantropia_solar_public 19.0.2.25.0: no FS website COW views"
            )
        # Ensure Projetos menu exists even if menus.xml noupdate blocked updates
        Menu = env["website.menu"].sudo()
        existing = Menu.search([("url", "=", "/projetos")], limit=1)
        if not existing:
            parent = env.ref("website.main_menu", raise_if_not_found=False)
            vals = {
                "name": "Projetos",
                "url": "/projetos",
                "sequence": 15,
            }
            if parent:
                vals["parent_id"] = parent.id
            menu = Menu.create(vals)
            # external id for future upgrades
            if not env.ref(
                "filantropia_solar_public.menu_projetos", raise_if_not_found=False
            ):
                env["ir.model.data"].sudo().create(
                    {
                        "name": "menu_projetos",
                        "module": "filantropia_solar_public",
                        "model": "website.menu",
                        "res_id": menu.id,
                        "noupdate": True,
                    }
                )
            _logger.info(
                "filantropia_solar_public 19.0.2.25.0: created website menu Projetos"
            )
    except Exception:
        _logger.exception("filantropia_solar_public 19.0.2.25.0 post-migrate failed")
