# TRL5 Nextcloud — single instance (AIO)

**As of 2026-08-14:** FilantropiaSolar runs on **Nextcloud AIO only**.  
The separate `filantropia-nextcloud` container is **stopped** (`restart=no`).

## Where to open the app

| Surface | URL |
|---------|-----|
| AIO (users / primary) | Host **:80** / **:8080** / **:8443** (your existing AIO entry) |
| App path | **Apps → FilantropiaSolar** or `/apps/filantropia_solar/` |
| Public website (Odoo) | https://filantropiasolar.wera.global |
| Public/lifecycle API (internal) | `http://nextcloud-aio-apache:11000/index.php/apps/filantropia_solar/api/...` |

Verify:

```bash
ssh root@100.82.252.18
docker exec -u 33 nextcloud-aio-nextcloud php occ app:list | grep filantropia
# filantropia_solar: 3.2.26
docker exec nextcloud-aio-database psql -U nextcloud -d nextcloud_database -tAc \
  "SELECT count(*) FROM oc_fs_installations WHERE source='fleet';"
# 11
```

## Architecture after cutover

| Component | Status |
|-----------|--------|
| nextcloud-aio-nextcloud | **SoT** for FilantropiaSolar app + `oc_fs_*` |
| nextcloud-aio-apache | Front door (port 11000 internal, host 80/8080/8443 via master) |
| filantropia-ml | Running; AIO joined `nextcloud-app_filantropia-net`; `ml_service_url=http://filantropia-ml:8501` |
| filantropia-odoo | Running; `FS_*` → AIO apache:11000; CRM import OK |
| filantropia-nextcloud | **Stopped** (rollback: start container + point Odoo back) |
| filantropia-db | Kept for rollback (MariaDB old instance) |

## Install notes (already done)

1. App `max-version` raised to **33** for AIO NC 33.0.7.  
2. Clean app tree copied into AIO `custom_apps/filantropia_solar` (**no** macOS `._*` files — those break route loading).  
3. `occ app:enable filantropia_solar` + migrations → `oc_fs_*` tables.  
4. Fleet seed (11 stations) into AIO Postgres.  
5. Odoo env: token + API base URLs on `nextcloud-aio-apache:11000`.  
6. Dual-job risk removed by stopping Filantropia NC.

## Rollback

```bash
# Start old NC again
docker update --restart=unless-stopped filantropia-nextcloud
docker start filantropia-nextcloud
# Point Odoo FS_API_BASE_URL back to http://filantropia-nextcloud/...
# Optionally occ app:disable filantropia_solar on AIO
```

## Outbound email (TRL5, verified 2026-08-16)

NC and Odoo send mail through **host Proton Mail Bridge**, not a container MTA.

**Verified working:** NC Admin email test, Odoo Test Connection, and Odoo user invitation delivery.

| Piece | Value |
|-------|--------|
| Bridge SMTP | `127.0.0.1:1025` STARTTLS + AUTH |
| Bridge mailbox | `cloud@wera.global` (account `Tomás Crespim` index `0`) |
| Docker reachability | `protonmail-smtp-docker-proxy.service` → `172.18.0.1:1025` / `172.19.0.1:1025` |
| NC SMTP | `172.18.0.1:1025`, `mail_smtpsecure=tls` + self-signed `mail_smtpstreamoptions`, from `cloud@wera.global` |
| Odoo outgoing server | `Proton Bridge (host via docker gw)` — same host/port, `starttls` / `login`, `from_filter=wera.global` |
| Odoo identity | company / OdooBot / admin = `cloud@wera.global`; alias domain bounce/catchall/default_from all `cloud` |

### If mail stops after Bridge restart
Bridge may show `signed out` / `locked`. Re-login:
```bash
ssh -t wera-admin@wera-ss-pt-tv-1.tailfb390c.ts.net
sudo systemctl restart protonmail.service   # only if tmux session missing
sudo -u protonmail tmux attach -t protonmail
# Bridge CLI:
list
login 0
# Proton password + 2FA
list   # expect connected
info 0 # refresh SMTP password into NC/Odoo if rotated
# Ctrl-b then d to detach
sudo systemctl restart protonmail-smtp-docker-proxy.service
```

Full procedure and failure matrix: SolarSeed-v3 `ops/RUNBOOK.md` → **TRL5 outbound email**.

## AIO upgrades

After AIO updates Nextcloud container, re-check:

```bash
docker exec nextcloud-aio-nextcloud ls /var/www/html/custom_apps/filantropia_solar/appinfo/info.xml
docker exec -u 33 nextcloud-aio-nextcloud php occ app:list | grep filantropia
docker network connect nextcloud-app_filantropia-net nextcloud-aio-nextcloud || true
```

Re-copy app from `/opt/FilantropiaSolar/nextcloud-app` if `custom_apps` was wiped.
