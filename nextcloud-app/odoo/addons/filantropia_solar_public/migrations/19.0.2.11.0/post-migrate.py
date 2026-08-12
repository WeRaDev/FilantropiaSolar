import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Historical note: 19.0.2.11.0 originally deleted website COW views for
# filantropia_solar_public page/snippet keys. That wiped published Website
# Builder content on upgrade (TRL5 home page). Withdrawn in 19.0.2.12.0 —
# this migration is now a no-op so late upgraders are safe too.
# Forced one-shot reset: ir.config_parameter
# filantropia_solar_public.reset_website_cows=1 (see hooks._maybe_reset_website_cows).


def migrate(cr, _version):
    _logger.info(
        "filantropia_solar_public 19.0.2.11.0 post-migrate: no-op "
        "(website COW delete withdrawn; preserving published views)"
    )
    # Touch env so Odoo migration runner stays happy if cr is expected used
    try:
        api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.exception(
            "filantropia_solar_public 19.0.2.11.0 post-migrate env probe failed"
        )
