# Cloudflared tunnel errors (TRL5)

**Tunnel:** `filantropia-solar` (`6571cd54-a08d-46da-a4ca-9630c1a0d090`)  
**Runtime:** container `filantropia-cloudflared` (`cloudflare/cloudflared:2025.8.1`)  
**Config dir:** `/home/wera-admin/cloudflared-nc` (live); repo mirror `nextcloud-app/infra/cloudflared/`  
**Reviewed:** 2026-09-01 (HTTP/2 + IPv4 edge pin; prior QUIC window 2026-08-30)

## Executive summary

| Question | Answer |
|----------|--------|
| Is the website origin broken? | **No.** Odoo and NC AIO answer **200** on Docker networks and host ports. |
| What do the persistent ERRs mean? | Historically **edge QUIC path flakiness**; after `protocol: http2`, residual flaps were often **IPv6 edge dials** (`network is unreachable`) on a host with **no global IPv6 WAN route**. |
| Do they always take the site down? | **No** when some edge sessions stay up. When **all** connectors drop: public **502**, **530**, or Cloudflare **error 1033** (tunnel down / no connector). |
| Required network layout | **Host network (production):** `network_mode: host`, ingress `127.0.0.1:8069` / `:11000`. **Legacy bridge:** dual nets + container DNS. |
| Required edge protocol / IP | **`protocol: http2`**, **`edge-ip-version: "4"`**, **`ha-connections: 2`**. |

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

Protocol in production (2026-09-01): **`protocol=http2`** with **`edge-ip-version=4`** (TCP 7844 to Cloudflare edge over IPv4).

### Incident 2026-09-01 (public 530 / 502, origins healthy)

| Observation | Detail |
|-------------|--------|
| Public | `https://filantropiasolar.pt` → **530** (`error code: 1033`) then **502** |
| Local Odoo / AIO | `127.0.0.1:8069/inicio` and AIO status → **200** |
| Dual Docker nets | Present on `filantropia-cloudflared` |
| cloudflared logs | `dial tcp 198.41.192.x:7844: connect: network is unreachable`; edge lost/reconnect loops |
| Host IPv6 | Only Tailscale/`fe80` routes — **no global IPv6 default** via `wlan0` |
| WAN path | Ping to Cloudflare anycast (`198.41.192.27`) showed ~**30%** loss while `1.1.1.1` was clean; Wi‑Fi link OK |
| Fix applied | (1) `edge-ip-version: 4` + HTTP/2 (2) prefer IPv4 in `/etc/gai.conf` (3) switch cloudflared to **`network_mode: host`** + localhost origins + **`ha-connections: 2`** |
| Result | External poll **12/12** **200** on `filantropiasolar.pt/inicio` after host-net switch |

**Note:** `wera-ss-pt-tv-1.cloud.wera.global` may still fail TLS at Cloudflare (multi-level name needs Advanced Certificate for `*.cloud.wera.global`). Prefer `wera-ss-pt-tv-1.wera.global` for NC. On TRL5 itself, `/etc/hosts` maps `wera-ss-pt-tv-1.wera.global` → `127.0.1.1` (AIO/local), so host curls to that name are not a public-path probe.

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

### 1. Host network (production, 2026-09-01+)

```yaml
# docker-compose.yml
network_mode: host
# config.yml ingress
service: http://127.0.0.1:8069   # Odoo
service: http://127.0.0.1:11000  # AIO apache
```

Requires Odoo/AIO publish ports on localhost (TRL5 compose already does).  
`trl5-ensure-stack.sh` skips Docker-network heal for cloudflared when compose has `network_mode: host`.

### 2. Legacy dual Docker networks (bridge mode only)

If not using host net, cloudflared **must** remain attached to:

| Network | Why |
|---------|-----|
| `nextcloud-app_filantropia-net` | Resolve/reach `filantropia-odoo` |
| `nextcloud-aio` | Resolve/reach `nextcloud-aio-apache` |

```bash
docker inspect filantropia-cloudflared \
  --format '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}'
# bridge mode expect: nextcloud-app_filantropia-net + nextcloud-aio
```

Bridge ingress should use container DNS (`http://filantropia-odoo:8069`), not `host.docker.internal`.

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
edge-ip-version: "4"
```

Or compose:

```yaml
command: tunnel --config /etc/cloudflared/config.yml --protocol http2 --edge-ip-version 4 run
```

Then:

```bash
cd /home/wera-admin/cloudflared-nc
docker compose up -d --force-recreate
docker logs -f filantropia-cloudflared   # expect protocol=http2 on register
```

Trade-off: slightly higher latency possible vs QUIC; avoids UDP-lossy path noise and IPv6 dials on IPv4-only WAN.

### A2. Prefer IPv4 for host processes (gai.conf)

TRL5 resolves many Cloudflare names with AAAA first. Without a global IPv6 route, local clients can fail or mis-attribute outages. Keep:

```text
# /etc/gai.conf
precedence ::ffff:0:0/96  100
```

This does not replace `edge-ip-version: "4"` inside cloudflared.

### B. Keep ensure-stack / health timer enabled

```bash
systemctl is-enabled filantropia-stack.service filantropia-stack-health.timer
# both enabled
```

These heal **origin network membership** (the failure mode that causes real public 502s), which is separate from QUIC spam.

### C. Optional: pin fewer edge connections / upgrade image

- Image `2025.8.1` is behind current cloudflared releases; plan a controlled bump (test HTTP/2 + QUIC).  
- Avoid running extra experimental flags unless documented by Cloudflare for your version.

### D. Host networking is intentional on TRL5

Host networking **is** the production mode when paired with localhost ingress and published ports. Do not mix host net with container DNS names (`filantropia-odoo`) — those only resolve on Docker networks.

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
| Public **200** but logs full of QUIC ERR | Edge UDP flapping | Keep `protocol: http2`; monitor ISP/UDP |
| Public **502/530/1033**, local Odoo **200**, logs `network is unreachable` to `198.41.*:7844` | IPv6 edge dial / WAN path | Confirm `edge-ip-version: 4` + HTTP/2; recreate cloudflared |
| Origin refused in tunnel logs | Wrong ingress service name/port | Fix config.yml; ensure Odoo healthy |
| TLS handshake failure on `*.cloud.wera.global` | CF cert coverage for multi-level name | Use `wera-ss-pt-tv-1.wera.global` or Advanced Certificate |

## Related

- `nextcloud-app/infra/cloudflared/README.md`  
- `docs/ops/PUBLIC-DOMAIN-FILANTROPIASOLAR-PT.md`  
- `docs/ops/TRL5-ODOO-BOOT.md`  
- `scripts/trl5-ensure-stack.sh`  
