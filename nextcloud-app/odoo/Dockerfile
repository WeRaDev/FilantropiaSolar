# Filantropia Solar Odoo 19 image with queue_job Python deps baked in.
# Stock odoo:19.0 lacks openupgradelib (OCA queue_job external_dependencies).
FROM odoo:19.0

USER root
RUN pip3 install --no-cache-dir --break-system-packages \
        openupgradelib \
        requests \
    && python3 -c "import openupgradelib, requests; print('odoo deps ok')"

USER odoo
