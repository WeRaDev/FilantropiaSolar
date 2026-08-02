"""Post-init hooks for the Filantropia Solar public module."""

import logging

_logger = logging.getLogger(__name__)

# Old single-page URL redirects to the new home page (kept working forever).
LEGACY_URL = "/filantropia-solar"
HOME_URL = "/inicio"


def post_init_hook(env):
    """Register the legacy redirect, ensure PT is available.

    Does NOT set homepage_url — the website root renders /inicio via the
    controller route (which injects live stations/dashboard data).
    """

    # Legacy 301: /filantropia-solar -> /inicio (no deletion, just a redirect)
    rewrite = env["website.rewrite"].search(
        [("url_from", "=", LEGACY_URL)],
        limit=1,
    )
    if not rewrite:
        env["website.rewrite"].create(
            {
                "name": "filantropia-solar legacy home",
                "redirect_type": "301",
                "url_from": LEGACY_URL,
                "url_to": HOME_URL,
            }
        )
        _logger.info(
            "filantropia_solar_public: 301 %s -> %s registered",
            LEGACY_URL,
            HOME_URL,
        )

    # Ensure Portuguese is available on the frontend
    lang = env["res.lang"].search([("code", "=", "pt_PT")], limit=1)
    if lang and not lang.active:
        lang.active = True
        _logger.info("filantropia_solar_public: pt_PT activated")
