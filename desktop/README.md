# FilantropiaSolar Desktop Edition

Desktop client for the FilantropiaSolar platform. The **Nextcloud app is the
server-side application** (stations, admin panel, public website, ML
estimates); this desktop edition is the client-side companion for analysts
who prefer a native window over the browser.

## Current version: 1.3.0 (API-client mode)

Since 1.3.0 the desktop edition consumes the **Nextcloud API** instead of
running a local ML pipeline. Set the server connection and start:

```bash
export FS_SERVER_URL="http://localhost:8080"          # your Nextcloud server
export FS_SERVER_TOKEN="<app password or public token>"
python main.py
```

What it does:

- Lists installations from the server (merged dataset + user stations)
- Requests period analysis (hourly/daily production + weather) from the
  server's prediction endpoints
- Renders the charts and rankings locally (Tkinter + Matplotlib)

What it no longer does: local model training/inference and local dataset
loading (the server owns data and ML; legacy local-ML modules in `src/` are
retained for reference and tests).

## Roadmap

- **1.2.4 (planned)** — branded client on the `nextcloud/desktop` base:
  server login, FilantropiaSolar panel as default landing, other Nextcloud
  apps as secondary, optional file sync.

## Development

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e .
pytest -q            # tests (HTTP is mocked; no server needed)
ruff format . && ruff check . && mypy
```

Shared datasets (`data/`, `weather_files/`) are symlinked from the repository
root for the legacy local-mode code paths and the smoke scripts.

See `docs/` for usage and development guides.
