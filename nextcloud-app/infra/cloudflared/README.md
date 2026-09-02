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
| Ingress (host net) | Odoo `http://127.0.0.1:8069`; Nextcloud AIO `http://127.0.0.1:11000` |
| Edge settings | `protocol: http2`, `edge-ip-version: 4`, `ha-connections: 2`, `network_mode: host` |
| Nextcloud public URL (working TLS) | https://wera-ss-pt-tv-1.wera.global |
| Nextcloud alt hostname | `wera-ss-pt-tv-1.cloud.wera.global` (DNS+tunnel ready; needs CF Advanced Cert for `*.cloud.wera.global`) |
| Tunnel runtime (TRL5) | `/home/wera-admin/cloudflared-nc` (writable); `/opt/.../infra/cloudflared` is root-owned mirror |

```
Internet -> Cloudflare edge -> filantropia-cloudflared (TRL5, host network)
         -> http://127.0.0.1:8069                    (filantropiasolar.pt)
         -> http://127.0.0.1:11000                   (wera-ss-pt-tv-1.wera.global)
         -> http://127.0.0.1:11000                   (wera-ss-pt-tv-1.cloud.wera.global)
```

### Nextcloud notes
- **Host-network mode (production):** cloudflared uses the host stack and localhost publish ports. Dual Docker-network attachment is **not** required.
- **Legacy bridge mode:** if compose is switched back to bridge, cloudflared must join **both** `nextcloud-app_filantropia-net` and `nextcloud-aio`, with ingress to container DNS names.
- NC trusted_domains include both public hostnames + Tailscale domain.
- AIO forces `OVERWRITEHOST` from `NC_DOMAIN` (Tailscale). Host-aware override:
  `/var/www/html/config/zzz-public-domain.config.php` inside `nextcloud-aio-nextcloud`.
- Universal SSL covers `*.wera.global` only (one label). Multi-level `*.cloud.wera.global` needs an Advanced Certificate in Cloudflare.

Mac and TRL4 are **not** the public origin. Keep only one active tunnel connector.

## Architecture notes

- Odoo binds `127.0.0.1:8069` on the host (see `docker-compose.trl5.yml`); AIO apache publishes `127.0.0.1:11000`.
- Production cloudflared uses **`network_mode: host`** so edge TCP does not traverse Docker bridge NAT (2026-09-01: dual-bridge mode flapped to public **502/530** on a lossy path to Cloudflare anycast while origins stayed **200**).
- Edge knobs: **HTTP/2**, **IPv4-only** (`edge-ip-version: 4`), **`ha-connections: 2`**.
- `credentials.json` must be mode `644` (image runs non-root).
- Nextcloud AIO already owns `:8080` on TRL5; Filantropia NC uses `127.0.0.1:18080`.
- Persistent edge ERR / reconnect noise while public stays **200** is documented in `docs/ops/CLOUDFLARED-TUNNEL-ERRORS.md`.

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
