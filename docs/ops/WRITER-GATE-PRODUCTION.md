# Writer-gate production ops (Phase C)

Status as of **2026-10-19T19:54Z** (post Test C #3 cutover to Frank). Public Odoo
traffic for FilantropiaSolar goes through the Cloudflare Worker lease gate.
Automatic promotion is **disabled**. **Frank** is sole writer (epoch **30**,
lease-guard renewing); TRL5 is offline pending return/failback. Visitor 503s
without an active lease show a branded failover HTML page (Worker). Incident:
`docs/ops/INCIDENT-2026-10-17-TEST-C-FAILOVER.md`. Failback order:
`docs/ops/EMBASSY-FAILBACK-ANTI-RACE.md`.

## Live topology

```
Browser
  -> Cloudflare edge
  -> Worker filantropia-odoo-writer-gate
       routes: filantropiasolar.pt/* , www.filantropiasolar.pt/*
       lease DO: WriterLeaseObject (id name filantropia-odoo-writer)
  -> ORIGIN_TRL5_URL https://odoo-trl5.wera.global
       -> tunnel filantropia-solar (6571cd54-a08d-46da-a4ca-9630c1a0d090)
       -> TRL5 cloudflared -> 127.0.0.1:8069

Standby Frank (wera-ss-pt-sn-1 / 100.82.194.96):
  Postgres streaming replica (slot frank_odoo_slot; primary publishes 100.82.252.18:5432)
  Filestore pull mirror (timer)
  Odoo stopped (restart=no); lease-guard timer enabled but state fenced (standby)
  ORIGIN_FRANK_URL https://odoo-frank.wera.global -> 502 while Odoo stopped
  Dedicated Frank origin tunnel exists (do not join TRL5 tunnel 6571cd54-…)
```

| Item | Value |
|------|--------|
| Worker | `filantropia-odoo-writer-gate` |
| workers.dev | `https://filantropia-odoo-writer-gate.filantropia.workers.dev` |
| Lease source name | `cloudflare-durable-object-lease` |
| Writer node | `trl5` (epoch **28** at 2026-10-19 verify) |
| Writer generation | `writer-epoch-20261012-trl5-primary` |
| Lease TTL / drain / grace | 30s / 5s / 15s |
| Lease guard timer (TRL5) | every 15s; **enabled/active** |
| Lease guard timer (Frank) | every 15s; **enabled**; standby left **fenced** |
| Worker fencing-proof freshness | deployed (`bde010c0-8422-4b49-bc58-5f0aa2b64381`) |
| Repl publish (TRL5) | prefer compose overlay `docker-compose.trl5-repl-publish.yml` **or** socat unit — not both |
| Auto-takeover | **false** on Frank (`automatic_actions_enabled`, `request_takeover_on_outage`, `execute_promotion`) |
| Test C readiness | proof-refresh + age-waive + **post-promote lease-guard arming** in repo; green production retest still required |
| Failback order | `docs/ops/EMBASSY-FAILBACK-ANTI-RACE.md` |
| Preflight | `nextcloud-app/infra/embassy/scripts/test-c-preflight.sh` |

Secrets live only in Wrangler secrets and host files under
`/etc/filantropia-embassy/` (and operator copy
`~/.config/filantropia-embassy/lease-phase-a.env`). Never commit tokens.

## Critical ops notes

### 1. Active lease is required for public HTTP

The Worker proxies apex/www **only** when lease `phase === active` and owner is
`trl5` or `frank`. If the lease expires (`acquirable` / `unowned`), public pages
return **503** even when Odoo and the tunnel are healthy.

Browser visitors no longer see a blank body with only the text
`no active writer epoch`. The Worker serves a branded HTML page (PT primary, EN
secondary) explaining that FilantropiaSolar will return within the designed
takeover window (~1–3 minutes), with auto-refresh every 20s, `Retry-After`, and
`Cache-Control: no-store`. Clients that `Accept: application/json` still get a
compact JSON body with the same reason codes.

Mitigation:

- Keep `filantropia-lease-guard.timer` **active on TRL5** while TRL5 holds the lease.
- Guard interval is 15s; TTL is 30s. Do not stop the timer on the live writer.
- After TRL5 reboot or Odoo recreate, confirm renew succeeds before walking away.

Quick repair if apex is 503 but origin is 200:

1. On TRL5 (preferred): `bash /tmp/trl5-unfence-lease-guard.sh`
   (repo: `nextcloud-app/infra/embassy/scripts/trl5-unfence-lease-guard.sh`).
   Do not `cd` into `/opt/FilantropiaSolar/nextcloud-app` as `wera-admin`
   (directory mode `0700` root-only); the script drives systemd instead.
2. Or authenticated lease status / acquire / renew against workers.dev
   (`/lease/status`, `/lease/acquire`, `/lease/renew`) with the TRL5 token from
   `/etc/filantropia-embassy/lease.env`.

After an aborted takeover, Worker acquire allows previous owner reclaim once
`readyToAcquire` is true (drain/grace already enforced).

### 2. Fail-closed is intentional

| Condition | Public result |
|-----------|----------------|
| No active lease | 503 |
| Unknown owner | 503 |
| Origin down / tunnel down | 503 / 530 |
| WebSocket upgrade | 501 |
| `/lease/*` without Bearer | 401 |

### 3. Lease client User-Agent

Host lease calls must send a browser-compatible User-Agent. Bare Python urllib
can be challenged on `workers.dev` and return non-JSON bodies that the client
treats as invalid. Production `lease_client.py` sets:

`FilantropiaEmbassyLeaseClient/1.0 (+https://filantropiasolar.pt; Mozilla/5.0 compatible)`

### 4. Dual origins

| URL | Purpose |
|-----|---------|
| `https://odoo-trl5.wera.global` | TRL5 Odoo origin for the Worker |
| `https://odoo-frank.wera.global` | Reserved Frank origin (503 placeholder on TRL5 tunnel today) |
| `https://filantropiasolar.pt` | Public apex (Worker route) |

Apex and origin hostnames are separate on purpose. Do not point
`ORIGIN_TRL5_URL` at the apex (loop risk once routes are on the Worker).

Frank still needs its own cloudflared connector claiming `odoo-frank.wera.global`
before a real promote can serve public traffic from Frank through the gate.

### 5. Postgres replication publish

TRL5 primary must publish Postgres on the Tailnet for Frank:

- Preferred durable path after 2026-10-18: systemd
  `filantropia-pg-repl-publish.service` (socat bind `100.82.252.18:5432` → DB
  container on `nextcloud-app_filantropia-net`). Avoid running this **and**
  compose host-port publish at the same time (bind conflicts can leave the DB
  container networkless).
- Alternate compose overlay: `docker-compose.trl5-repl-publish.yml`
  (`100.82.252.18:5432:5432`). If used alone, include it in `COMPOSE_FILE`.
- After any `odoo-db` recreate, attach alias `odoo-db` on
  `nextcloud-app_filantropia-net` or Odoo cannot resolve `HOST=odoo-db`.
- `listen_addresses = '*'`
- `pg_hba` allows `replicator` from Frank Tailnet IP and Docker NAT ranges
  (`100.82.194.96/32`, `172.16.0.0/12` as needed)
- Slot: `frank_odoo_slot`

After TRL5 reboot, confirm `pg_stat_replication` shows Frank streaming and lag
bytes ≈ 0.

### 6. Readiness endpoint

Odoo must load `/etc/filantropia-embassy/readiness.env` via
`docker-compose.trl5-embassy.yml`:

- `FS_EMBASSY_READINESS_TOKEN`
- `FS_EMBASSY_NODE_ID=trl5`
- `FS_WRITER_GENERATION=writer-epoch-20261012-trl5-primary`

Without these, `/filantropia/embassy/readiness` returns 404/503 and Embassy on
Frank reports degraded even if the public site is fine.

### 7. Rollback Phase C (remove Worker from apex)

```bash
cd nextcloud-app/infra/cloudflare-writer-gate
# Comment routes in wrangler.toml, then:
npx wrangler deploy
```

Tunnel DNS for `filantropiasolar.pt` remains; traffic returns to tunnel-only
ingress once Worker routes are removed.

### 8. Designed RTO (when auto-promote is eventually enabled)

Lease math: TTL 30s + drain 5s + grace 15s, then promote/start Odoo.

- Designed automatic RTO: about **1–3 minutes** with warm standby
- Observed Test C #2: promote reachable after policy fix, but public durability
  failed when renewals stopped — treat renew path as part of RTO, not optional
- Manual RTO today: about **5–15 minutes**
- Auto-promote is still **off**; do not claim hands-free failover yet

### 9. Policy note after lease fence

Once the independent lease fence is valid and standby WAL apply lag is **0**,
Embassy waives primary heartbeat and filestore *generation age* freshness
(those clocks freeze while TRL5 is offline). Lineage, attachment verification,
and standby-local status age remain mandatory.

## Day-2 health checklist

```bash
# Public
curl -sS -o /dev/null -w '%{http_code}\n' -A 'Mozilla/5.0' -L https://filantropiasolar.pt/inicio
curl -sS -o /dev/null -w '%{http_code}\n' -A 'Mozilla/5.0' -L https://filantropiasolar.pt/en/blog
curl -sS -o /dev/null -w '%{http_code}\n' -A 'Mozilla/5.0' -L https://odoo-trl5.wera.global/inicio

# Lease (token required)
curl -sS -A 'Mozilla/5.0' -H "Authorization: Bearer $TOKEN" \
  https://filantropia-odoo-writer-gate.filantropia.workers.dev/lease/status

# TRL5
ssh root@100.82.252.18 'docker ps --filter name=filantropia-odoo --filter name=cloudflared; systemctl is-active filantropia-lease-guard.timer; test ! -f /etc/filantropia-embassy/odoo-fenced.json && echo not_fenced'

# Frank
ssh root@100.82.194.96 'docker exec filantropia-odoo-db psql -U odoo -d postgres -tAc "SELECT pg_is_in_recovery()"; systemctl is-active filantropia-odoo-filestore-sync.timer; docker inspect -f "{{.State.Status}}" filantropia-odoo'
```

Expect:

- apex/www/blog/login **200**
- origin TRL5 **200**; origin Frank **502/503** while Odoo stopped
- lease **active** owner **trl5**
- unauthenticated `/lease/status` **401**
- TRL5 Odoo healthy, not fenced, lease-guard timer active
- Frank `pg_is_in_recovery=t`, Odoo exited, lease-guard may report fenced (standby)
- `frank_odoo_slot` active; replay lag bytes **0**
- Frank embassy auto flags all **false**

## Related paths

- Worker source: `nextcloud-app/infra/cloudflare-writer-gate/`
- Tunnel config: `nextcloud-app/infra/cloudflared/config.yml` (live on TRL5 under `/home/wera-admin/cloudflared-nc/`)
- Embassy ADR: `docs/adr/0007-odoo-availability-first-embassy.md`
- Failover runbook: `docs/ops/TRL4-ODOO-FAILOVER.md`
- Test C incident close-out: `docs/ops/INCIDENT-2026-10-17-TEST-C-FAILOVER.md`
