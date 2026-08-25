# Cloudflare Tunnel — filantropiasolar.pt

Exposes the Filantropia Solar **Odoo public website** via Cloudflare Tunnel.

## Production host (current)

| Item | Value |
|------|--------|
| Public URL | https://filantropiasolar.pt |
| Origin host | TRL5 `wera-ss-pt-tv-1` (`root@100.82.252.18` Tailscale) |
| Code path | `/opt/FilantropiaSolar` |
| Module | `filantropia_solar_public` **19.0.2.7.0** (P2 SEO/FAQ/blog) |
| Tunnel | `filantropia-solar` (`6571cd54-a08d-46da-a4ca-9630c1a0d090`) |
| Ingress | Odoo `http://filantropia-odoo:8069`; Nextcloud AIO `http://nextcloud-aio-apache:11000` |
| Nextcloud public URL (working TLS) | https://wera-ss-pt-tv-1.wera.global |
| Nextcloud alt hostname | `wera-ss-pt-tv-1.cloud.wera.global` (DNS+tunnel ready; needs CF Advanced Cert for `*.cloud.wera.global`) |
| Tunnel runtime (TRL5) | `/home/wera-admin/cloudflared-nc` (writable); `/opt/.../infra/cloudflared` is root-owned mirror |

```
Internet -> Cloudflare edge -> filantropia-cloudflared (TRL5)
         -> http://filantropia-odoo:8069                    (filantropiasolar.pt)
         -> http://nextcloud-aio-apache:11000               (wera-ss-pt-tv-1.wera.global)
         -> http://nextcloud-aio-apache:11000               (wera-ss-pt-tv-1.cloud.wera.global)
```

### Nextcloud notes
- cloudflared must be on **both** `nextcloud-app_filantropia-net` and `nextcloud-aio`.
- NC trusted_domains include both public hostnames + Tailscale domain.
- AIO forces `OVERWRITEHOST` from `NC_DOMAIN` (Tailscale). Host-aware override:
  `/var/www/html/config/zzz-public-domain.config.php` inside `nextcloud-aio-nextcloud`.
- Universal SSL covers `*.wera.global` only (one label). Multi-level `*.cloud.wera.global` needs an Advanced Certificate in Cloudflare.

Mac and TRL4 are **not** the public origin. Keep only one active tunnel connector.

## Architecture notes

- Odoo binds `127.0.0.1:8069` on the host (see `docker-compose.trl5.yml`).
- cloudflared must share `nextcloud-app_filantropia-net` and target **container DNS**
  `filantropia-odoo:8069` (not `host.docker.internal`, which 502s when the publish is localhost-only).
- `credentials.json` must be mode `644` (image runs non-root).
- Nextcloud AIO already owns `:8080` on TRL5; Filantropia NC uses `127.0.0.1:18080`.

## TRL5 bring-up

```bash
# From a machine with repo + secrets (SSH as root on TRL5 Tailscale SSH today)
ssh root@100.82.252.18

cd /opt/FilantropiaSolar/nextcloud-app
bash scripts/setup-trl5.sh
# credentials: /opt/FilantropiaSolar/.secrets/filantropia_public_api_token
# tunnel creds: infra/cloudflared/credentials.json (gitignored)
```

Compose files:

- `docker-compose.yml` — base stack
- `docker-compose.trl5.yml` — port remap (NC 18080, Odoo/ML localhost)
- `infra/cloudflared/docker-compose.yml` — tunnel sidecar

## One-time Cloudflare (already done for wera.global)

```bash
bash nextcloud-app/scripts/deploy-public-tunnel.sh login
bash nextcloud-app/scripts/deploy-public-tunnel.sh create
```

Then copy `credentials.json` to the origin host and `docker compose up -d` in `infra/cloudflared/`.

## Day-2

```bash
# On TRL5
docker ps --filter name=filantropia
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8069/inicio
curl -sS -o /dev/null -w '%{http_code}\n' https://filantropiasolar.pt/inicio

docker compose -f /opt/FilantropiaSolar/nextcloud-app/infra/cloudflared/docker-compose.yml logs --tail 50
```

After Odoo recreate: re-run module update if addons changed, confirm tunnel container is `Up` (not Restarting).

## Clone local website DB -> TRL5

Local Odoo may have website COW views / data beyond module XML. To mirror:

```bash
# See scripts/export-odoo-website.sh and import notes in ops section of PR
bash nextcloud-app/scripts/export-odoo-website.sh
# scp dump to TRL5 and import (documented in script header)
```

## Secrets (never commit)

- `infra/cloudflared/credentials.json`
- `~/.cloudflared/cert.pem` (origin cert after login)
- `FS_PUBLIC_API_TOKEN` / `.secrets/filantropia_public_api_token`

## Odoo proxy

`proxy_mode = True` in `odoo/config/odoo.conf`.
`web.base.url` = `https://filantropiasolar.pt` (freeze recommended).
