# Public domain cutover: filantropiasolar.pt

**Primary public website:** https://filantropiasolar.pt  
**Also:** https://www.filantropiasolar.pt  
**Legacy (tunnel still accepts):** https://filantropiasolar.wera.global  

## Already applied (TRL5)

- Odoo `web.base.url` = `https://filantropiasolar.pt` (frozen)
- Odoo `website.domain` = `https://filantropiasolar.pt`
- cloudflared ingress includes `filantropiasolar.pt`, `www.filantropiasolar.pt`, and legacy `filantropiasolar.wera.global` → `http://filantropia-odoo:8069`
- Repo defaults: `PUBLIC_HOSTNAME` / tunnel scripts / compose trusted domains

## Required in Cloudflare dashboard (filantropiasolar.pt zone)

The zone NS are already on Cloudflare (`ivy` / `syeef`). Traffic must hit the **named tunnel**, not a generic proxied A record.

For **@** and **www** (and optionally bare redirect):

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `@` | `6571cd54-a08d-46da-a4ca-9630c1a0d090.cfargotunnel.com` | Proxied (orange) |
| CNAME | `www` | `6571cd54-a08d-46da-a4ca-9630c1a0d090.cfargotunnel.com` | Proxied |

Cloudflare flattens apex CNAMEs. Remove conflicting A/AAAA records for `@` / `www` first.

**SSL/TLS:** Full (strict not required for HTTP origin to Odoo).

Optional: Zero Trust → Networks → Tunnels → `filantropia-solar` → Public hostnames should list the same hostnames (connector config already publishes them).

### Do not use

`cloudflared tunnel route dns filantropia-solar filantropiasolar.pt` from a cert authorized only for `wera.global` — it creates `filantropiasolar.pt.wera.global` under the wrong zone.

## Verify

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://filantropiasolar.pt/inicio
curl -sS -o /dev/null -w '%{http_code}\n' https://www.filantropiasolar.pt/inicio
curl -sS -o /dev/null -w '%{http_code}\n' -H 'Host: filantropiasolar.pt' http://127.0.0.1:8069/inicio  # on TRL5 → 200
```

Expect **200** on public URLs after DNS. **521/525** means DNS/proxy is not bound to this tunnel yet.

## Rollback

1. Set Odoo `web.base.url` / website domain back to `https://filantropiasolar.wera.global`
2. Revert cloudflared ingress primary hostname (legacy rule can remain)
