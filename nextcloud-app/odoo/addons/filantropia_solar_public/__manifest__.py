{
    "name": "FilantropiaSolar Public",
    "summary": "Public NGO website: donation platform for solar equipment and installation.",
    "version": "19.0.2.1.0",
    "author": "WeRa Global",
    "website": "https://wera.global",
    "category": "Website",
    "license": "LGPL-3",
    "depends": ["website", "crm"],
    "data": [
        "views/snippets.xml",
        "views/pages.xml",
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
