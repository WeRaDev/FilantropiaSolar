# Cloudflare Tunnel — filantropiasolar.wera.global

Exposes the Filantropia Solar **Odoo public website** on the internet via Cloudflare Tunnel.

## Architecture

```
Internet -> Cloudflare edge -> cloudflared (this host)
         -> http://127.0.0.1:8069 (filantropia-odoo)
```

Hostname: `filantropiasolar.wera.global`

## One-time setup (needs Cloudflare account access to wera.global)

```bash
# 1) Login (browser)
bash nextcloud-app/scripts/deploy-public-tunnel.sh login

# 2) Create tunnel + DNS CNAME
bash nextcloud-app/scripts/deploy-public-tunnel.sh create

# 3) Join TRL4 network + set Odoo public URL + start tunnel
bash nextcloud-app/scripts/deploy-public-tunnel.sh all
```

## Day-2

```bash
bash nextcloud-app/scripts/deploy-public-tunnel.sh status
bash nextcloud-app/scripts/deploy-public-tunnel.sh up      # docker sidecar
# or
bash nextcloud-app/scripts/deploy-public-tunnel.sh up-host # host process
```

## Secrets

- `credentials.json` is **gitignored**
- Origin cert lives in `~/.cloudflared/cert.pem` after login

## Odoo

`proxy_mode = True` in `odoo/config/odoo.conf` (mounted into the container).
`web.base.url` set to `https://filantropiasolar.wera.global` by the deploy script.
