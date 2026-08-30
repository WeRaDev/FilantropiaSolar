# Cloudflared tunnel errors (TRL5)

**Tunnel:** `filantropia-solar` (`6571cd54-a08d-46da-a4ca-9630c1a0d090`)  
**Runtime:** container `filantropia-cloudflared` (`cloudflare/cloudflared:2025.8.1`)  
**Config dir:** `/home/wera-admin/cloudflared-nc` (live); repo mirror `nextcloud-app/infra/cloudflared/`  
**Reviewed:** 2026-08-30 (last ~5k log lines, ~5h window)

## Executive summary

| Question | Answer |
|----------|--------|
| Is the website origin broken? | **No.** Odoo and NC AIO answer **200** on Docker networks and host ports. |
| What do the persistent ERRs mean? | **Edge QUIC path flakiness** between TRL5 and Cloudflare PoPs (`ams*`, `lis04`), not origin DNS/network inside Docker. |
| Do they always take the site down? | **No.** Connector keeps re-registering connections; public URLs often stay **200**. Brief **502** windows can appear when all edge sessions drop. |
| Required network layout | cloudflared on **both** `nextcloud-app_filantropia-net` and `nextcloud-aio`; ingress to **container DNS** (`filantropia-odoo:8069`, `nextcloud-aio-apache:11000`). |

## Log volume (sample)

From `docker logs filantropia-cloudflared` tail **5000** lines (~14:44–19:56 UTC):

| Pattern | Count | Meaning |
|---------|------:|---------|
| `ERR` lines | 2148 | High noise |
| `timeout: no recent network activity` | 1339 | QUIC idle/path loss to edge |
| `failed to accept QUIC stream` | 580 | Edge stream accept failed after timeout |
| `datagram handler` failures | 585 | Same QUIC session death |
| `Connection terminated` | 317 | Edge conn closed |
| `Failed to dial` / `failed to dial to edge` | 209 | Reconnect attempt failed |
| `Registered tunnel connection` | 581 | Successful (re)connects — tunnel self-heals |
| Origin unreachable / connection refused / no such host | **4** | Rare; not the dominant failure mode |
| Missing `cert.pem` / origincert | **0** in this window | N/A for named-tunnel token mode |

### Representative messages

```text
ERR failed to accept incoming stream requests error="failed to accept QUIC stream: timeout: no recent network activity"
ERR failed to run the datagram handler error="timeout: no recent network activity"
ERR Connection terminated error="accept stream listener encountered a failure while serving" connIndex=…
ERR Failed to dial a quic connection error="failed to dial to edge with quic: timeout: no recent network activity"
INF Registered tunnel connection connIndex=0 … location=ams19 protocol=quic
INF Registered tunnel connection connIndex=1 … location=lis04 protocol=quic
```

Protocol in use today: **`protocol=quic` only** (UDP 7844 to Cloudflare edge).

## What is *not* wrong

1. **Docker service discovery for origins**  
   - From `nextcloud-app_filantropia-net`: `http://filantropia-odoo:8069/inicio` → **200**  
   - From `nextcloud-aio`: `http://nextcloud-aio-apache:11000/status.php` → **200**

2. **Ingress hostnames** (config is correct for current product):

   | Hostname | Origin |
   |----------|--------|
   | `filantropiasolar.pt` | `http://filantropia-odoo:8069` |
   | `www.filantropiasolar.pt` | `http://filantropia-odoo:8069` |
   | `filantropiasolar.wera.global` (legacy) | `http://filantropia-odoo:8069` (Host header → `.pt`) |
   | `wera-ss-pt-tv-1.wera.global` | `http://nextcloud-aio-apache:11000` |
   | `wera-ss-pt-tv-1.cloud.wera.global` | `http://nextcloud-aio-apache:11000` |

3. **Restart policy** — `unless-stopped`; restarts often **0** while ERRs continue (process stays up and reconnects).

4. **Host DOCKER-USER firewall** — empty/default; not dropping tunnel traffic in the observed config.

## Network configuration requirements (must stay true)

### 1. Dual Docker networks

cloudflared **must** remain attached to:

| Network | Why |
|---------|-----|
| `nextcloud-app_filantropia-net` | Resolve/reach `filantropia-odoo` |
| `nextcloud-aio` | Resolve/reach `nextcloud-aio-apache` |

Compose (`infra/cloudflared/docker-compose.yml`) declares both as **external**.  
After Odoo recreate or host reboot, membership can be lost — `scripts/trl5-ensure-stack.sh` and `filantropia-stack-health.timer` re-attach.

```bash
docker inspect filantropia-cloudflared \
  --format '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}'
# expect:
# nextcloud-app_filantropia-net
# nextcloud-aio
```

### 2. Prefer container DNS over host ports

Do **not** point ingress at `http://host.docker.internal:8069` or host LAN IP for production. TRL5 publishes Odoo on `127.0.0.1:8069` (and Tailscale IP); from another container, host-gateway is fragile and previously caused **502**.

Correct:

```yaml
service: http://filantropia-odoo:8069
```

### 3. Cloudflare DNS for `.pt`

Zone must CNAME apex/www to the **named tunnel**, not a random proxied A record:

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `@` | `6571cd54-a08d-46da-a4ca-9630c1a0d090.cfargotunnel.com` | orange |
| CNAME | `www` | same | orange |

SSL/TLS mode: **Full** (origin is HTTP).  
See `docs/ops/PUBLIC-DOMAIN-FILANTROPIASOLAR-PT.md`.

### 4. Single connector

Only **one** active connector for this tunnel (TRL5). Do not also run Mac/TRL4 `cloudflared` against the same tunnel ID (split-brain / flapping).

### 5. Outbound UDP to Cloudflare edge

QUIC needs **UDP/7844** (and general HTTPS/UDP to Cloudflare anycast) from TRL5 WAN. If the LAN/router/ISP filters UDP, expect exactly this log pattern and consider HTTP/2 protocol fallback (below).

## Recommended configuration adjustments

### A. Prefer HTTP/2 to the edge (reduce QUIC noise)

If UDP is lossy on the site uplink, force TCP HTTP/2:

```yaml
# in config.yml (top-level)
tunnel: 6571cd54-a08d-46da-a4ca-9630c1a0d090
credentials-file: /etc/cloudflared/credentials.json
protocol: http2
```

Or compose:

```yaml
command: tunnel --config /etc/cloudflared/config.yml --protocol http2 run
```

Then:

```bash
cd /home/wera-admin/cloudflared-nc
docker compose up -d --force-recreate
docker logs -f filantropia-cloudflared   # expect protocol=http2 on register
```

Trade-off: slightly higher latency possible; much fewer `timeout: no recent network activity` ERRs on bad UDP paths.

### B. Keep ensure-stack / health timer enabled

```bash
systemctl is-enabled filantropia-stack.service filantropia-stack-health.timer
# both enabled
```

These heal **origin network membership** (the failure mode that causes real public 502s), which is separate from QUIC spam.

### C. Optional: pin fewer edge connections / upgrade image

- Image `2025.8.1` is behind current cloudflared releases; plan a controlled bump (test HTTP/2 + QUIC).  
- Avoid running extra experimental flags unless documented by Cloudflare for your version.

### D. Do **not** “fix” by adding host `network_mode: host` casually

Host networking would break current dual-network DNS names unless ingress is rewritten to `127.0.0.1` and NC AIO publish ports are guaranteed. Prefer bridge + dual external networks.

## How to triage next time

```bash
# 1) Public
curl -sS -o /dev/null -w '%{http_code}\n' https://filantropiasolar.pt/inicio

# 2) Origin on host
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8069/inicio

# 3) Origin from tunnel networks
docker run --rm --network nextcloud-app_filantropia-net curlimages/curl:8.5.0 \
  -sS -o /dev/null -w 'odoo %{http_code}\n' -m 8 http://filantropia-odoo:8069/inicio
docker run --rm --network nextcloud-aio curlimages/curl:8.5.0 \
  -sS -o /dev/null -w 'aio %{http_code}\n' -m 8 http://nextcloud-aio-apache:11000/status.php

# 4) Tunnel nets + errors
docker inspect filantropia-cloudflared \
  --format '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}'
docker logs filantropia-cloudflared 2>&1 | tail -100 | grep -E 'ERR|Registered tunnel|protocol='

# 5) Heal
sudo systemctl start filantropia-stack.service
```

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Public **502**, local Odoo **000**/bad nets | Odoo off `filantropia-net` | `filantropia-stack.service` / recreate Odoo |
| Public **502**, local Odoo **200**, tunnel missing dual nets | cloudflared cannot reach origin DNS | connect both networks; restart tunnel |
| Public **521/525** | DNS/SSL not on named tunnel | Fix CF DNS CNAME to `….cfargotunnel.com` |
| Public **200** but logs full of QUIC ERR | Edge UDP flapping | Optional `protocol: http2`; monitor ISP/UDP |
| Origin refused in tunnel logs | Wrong ingress service name/port | Fix config.yml; ensure Odoo healthy |

## Related

- `nextcloud-app/infra/cloudflared/README.md`  
- `docs/ops/PUBLIC-DOMAIN-FILANTROPIASOLAR-PT.md`  
- `docs/ops/TRL5-ODOO-BOOT.md`  
- `scripts/trl5-ensure-stack.sh`  
