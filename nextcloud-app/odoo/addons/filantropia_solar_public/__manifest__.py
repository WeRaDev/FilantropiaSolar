{
    "name": "FilantropiaSolar Public",
    "summary": "Public NGO website: donation platform for solar equipment and installation.",
    "version": "19.0.2.17.0",
    "author": "WeRa Global",
    "website": "https://wera.global",
    "category": "Website",
    "license": "LGPL-3",
    "depends": ["website", "website_blog", "crm", "queue_job"],
    "data": [
        "security/ir.model.access.csv",
        "data/menus.xml",
        "data/queue_job_channel_data.xml",
        "data/crm_stage_data.xml",
        "data/ir_cron_data.xml",
        "views/snippets.xml",
        "views/pages.xml",
        "views/crm_lead_views.xml",
        "views/fs_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "filantropia_solar_public/static/src/css/filantropia_solar_public.css",
        ],
    },
    "post_init_hook": "post_init_hook",
    "application": False,
    "installable": True,
}
