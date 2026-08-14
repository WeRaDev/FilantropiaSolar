# TRL5 Nextcloud access (FilantropiaSolar app)

## Two Nextcloud instances on the host

| Instance | Ports | FilantropiaSolar app? |
|----------|-------|------------------------|
| **Nextcloud AIO** (general files) | host `:80`, `:8080`, `:8443` | **No** |
| **Filantropia NC** (`filantropia-nextcloud`) | `127.0.0.1:18080` and Tailscale `100.82.252.18:18080` | **Yes** (v3.2.26) |

If you open the usual AIO URL, the FilantropiaSolar app will not appear. That is expected.

## Open FilantropiaSolar

1. On Tailscale: **http://100.82.252.18:18080/**  
   or **http://wera-ss-pt-tv-1.tailfb390c.ts.net:18080/**
2. Log in (default stack user is often `admin` — use the password set for this instance).
3. Top app menu / navigation should list **FilantropiaSolar** (order 10), or open:  
   `http://100.82.252.18:18080/apps/filantropia_solar/`

## Verify on server

```bash
ssh root@100.82.252.18
docker exec -u 33 filantropia-nextcloud php occ app:list | grep filantropia
# expect: filantropia_solar: 3.2.26 (enabled)
```

Public website (Odoo map) remains **https://filantropiasolar.wera.global** (cloudflared → Odoo `:8069`), not Nextcloud.

## Compose

Ports and trusted domains: `nextcloud-app/docker-compose.trl5.yml`.
