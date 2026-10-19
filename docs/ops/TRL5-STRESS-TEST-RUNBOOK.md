# TRL5 stress-test runbook (writer-gate + software lease)

Status: **2026-10-19**. TRL5-side tests (A/B) remain the safe default. Test C
ran twice in production windows: #1 failed on draining fencing proofs; #2
reached `promotion_executed` after a policy waive but lost the lease when Frank
lease-guard was left stopped. Production is restored on TRL5 with auto flags
**off**. Hands-free Test C is **not** green until post-promote lease-guard
arming is automatic. Full record:
`docs/ops/INCIDENT-2026-10-17-TEST-C-FAILOVER.md`.

## Goals

| Test | Intent | What we prove |
|------|--------|----------------|
| A. Network disconnect | TRL5 loses public path / Tailnet briefly | Lease expires fail-closed (apex 503); after restore, lease-guard reclaims; site 200 without dual-writer |
| B. Host reboot | TRL5 full reboot | Stack + lease-guard + tunnel + DB publish return; site 200; replication slot reconnects |
| C. Auto-promote | TRL5 dual-probe outage with Frank armed | Takeover → promote → apex via `frank` within RTO; single writer |

Tests A/B do **not** start Frank Odoo. Test C does, only after P2/P3 gates.

## Pre-flight checklist (must all pass)

Run from an operator workstation with lease token
(`~/.config/filantropia-embassy/lease-phase-a.env` or TRL5
`/etc/filantropia-embassy/lease.env`).

```bash
# 1) Public + origin
curl -sS -o /dev/null -w 'apex=%{http_code}\n' -A 'Mozilla/5.0' -L https://filantropiasolar.pt/inicio
curl -sS -o /dev/null -w 'www=%{http_code}\n' -A 'Mozilla/5.0' -L https://www.filantropiasolar.pt/inicio
curl -sS -o /dev/null -w 'origin=%{http_code}\n' -A 'Mozilla/5.0' -L https://odoo-trl5.wera.global/web/login

# 2) Lease active on trl5
set -a && source ~/.config/filantropia-embassy/lease-phase-a.env && set +a
curl -sS -A 'filantropia-lease-client/1.0' -H "Authorization: Bearer $FS_LEASE_AUTHORITY_TOKEN" \
  "$FS_LEASE_AUTHORITY_URL/lease/status" | python3 -m json.tool
# Expect: phase=active, owner_node_id=trl5, takeover_pending=false

# 3) TRL5 services
ssh wera-admin@100.82.252.18 '
  systemctl is-active filantropia-lease-guard.timer
  systemctl show filantropia-lease-guard.service -p Result -p ExecMainStatus
  docker ps --filter name=filantropia-odoo --filter name=filantropia-cloudflared --format "{{.Names}} {{.Status}} {{.Ports}}"
  curl -sS -o /dev/null -w "local=%{http_code}\n" http://127.0.0.1:8069/web/login
  docker exec filantropia-odoo-db psql -U odoo -d postgres -c \
    "SELECT slot_name, active FROM pg_replication_slots; SELECT application_name, client_addr, state FROM pg_stat_replication;"
'
```

Expect:

- apex/www/origin **200**
- lease **active / trl5**
- lease-guard timer **active**, last service **Result=success ExecMainStatus=0**
- Odoo healthy, cloudflared up, local 8069 **200**
- `frank_odoo_slot` **active=t**, `pg_stat_replication` row **streaming**
- DB published: `100.82.252.18:5432->5432/tcp`
- no Mac keep-alive / no `/tmp/filantropia-origin-keepup.sh`

### Known durable host notes

- Lease TTL / drain / grace: **30s / 5s / 15s**; guard timer **~15s**
- Unfence helper: `infra/embassy/scripts/trl5-unfence-lease-guard.sh`
  (on host also `/tmp/trl5-unfence-lease-guard.sh`). Uses **systemd one-shot**,
  not `cd` into root-only `/opt/.../nextcloud-app`.
- After any `odoo-db` recreate, ensure network alias **`odoo-db`** exists
  (`docker network connect --alias odoo-db ...`) or Odoo cannot resolve `HOST=odoo-db`.
- Compose overlay for publish: `docker-compose.trl5-repl-publish.yml`
- Frank SSH from this Tailnet identity is currently **policy-denied**; do not
  block the TRL5 tests on Frank shell access.
- Auto-takeover must stay **off** for these tests.

## Timers (design)

| Event | Bound |
|-------|--------|
| Lease stop renewing | guard interval ≤15s then TTL 30s → phase leaves `active` |
| Public fail-closed | Worker returns **503** `no active writer epoch` once not `active` |
| Drain + grace (if takeover requested) | 5s + 15s before acquire |
| Reclaim after outage (no takeover) | guard acquires/renews once Odoo readiness + authority reachable |
| Designed RTO (manual recover TRL5 only) | about **1–3 min** after network/host returns |

## Test A — Network disconnect

### Preferred controlled fault (no physical unplug)

Stops public origin path without rebooting the host. Choose **one**:

**A1. Stop cloudflared only** (origin 530/502; lease may stay active if guard still renews):

```bash
ssh wera-admin@100.82.252.18 'docker stop filantropia-cloudflared'
```

**A2. Stop lease-guard renewals** (lease expires; apex 503 even if Odoo up):

```bash
ssh wera-admin@100.82.252.18 'sudo systemctl stop filantropia-lease-guard.timer filantropia-lease-guard.service'
```

**A3. Combined** (closest to “path + writer authority lost” without reboot):

```bash
ssh wera-admin@100.82.252.18 '
  sudo systemctl stop filantropia-lease-guard.timer filantropia-lease-guard.service
  docker stop filantropia-cloudflared
'
```

**A4. True NIC/Tailnet down** (optional, physical or `ip link set … down` on WAN/Tailscale):
only with console access; expect SSH loss until link returns.

### Observe during outage (t0 → t0+90s)

```bash
# repeat every 10s
curl -sS -o /dev/null -w '%{http_code}\n' -A 'Mozilla/5.0' https://filantropiasolar.pt/inicio
curl -sS -A 'filantropia-lease-client/1.0' -H "Authorization: Bearer $FS_LEASE_AUTHORITY_TOKEN" \
  "$FS_LEASE_AUTHORITY_URL/lease/status" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("phase"), (d.get("state") or {}).get("owner_node_id"), (d.get("state") or {}).get("epoch"))'
```

### Pass criteria (outage)

| Fault | Pass |
|-------|------|
| A1 cloudflared stop | origin/apex become **5xx/530**; lease may remain `active` |
| A2/A3 guard stop | within ~45s lease not `active` **or** renew stops advancing `lease_expires_at`; apex **503** once lease not active |
| No Frank promotion | lease owner never becomes `frank`; Frank Odoo stays stopped |

### Restore

```bash
ssh wera-admin@100.82.252.18 '
  docker start filantropia-odoo-db filantropia-odoo filantropia-cloudflared
  docker network connect --alias odoo-db --alias filantropia-odoo-db \
    nextcloud-app_filantropia-net filantropia-odoo-db 2>/dev/null || true
  sudo systemctl start filantropia-lease-guard.timer
  # if still fenced:
  # bash /tmp/trl5-unfence-lease-guard.sh
'
```

### Pass criteria (recovery)

Within **3 minutes** of restore:

- lease `phase=active` owner `trl5`
- apex/www/origin **200**
- lease-guard `Result=success`
- `frank_odoo_slot` active/streaming again (may take a short reconnect)

### Rollback if stuck

1. Run `bash /tmp/trl5-unfence-lease-guard.sh` on TRL5 (sudo).
2. Manual acquire/renew against workers.dev `/lease/*` with TRL5 token.
3. Phase C emergency: comment Worker `routes` in `wrangler.toml` and
   `npx wrangler deploy` so tunnel-only apex works without lease (last resort).

## Test B — Host reboot

### Pre-reboot snapshot

Record lease epoch, `docker ps`, `pg_replication_slots`, public 200s.

### Execute

```bash
ssh wera-admin@100.82.252.18 'sudo reboot'
```

### Observe

- During boot: apex may **503** or **530** (lease/origin down).
- From t_reboot, poll public + lease every 15s for 10 minutes.

### Pass criteria

Within **5 minutes** of host SSH returning (target **≤3 minutes** if stack auto-starts):

- SSH to TRL5 works
- `filantropia-odoo` healthy, `filantropia-cloudflared` up
- `100.82.252.18:5432` published (if using repl-publish container)
- lease-guard timer active and renewing (`Result=success`)
- lease `active/trl5`
- apex **200**
- replication slot streaming (Frank side)

### Fail / follow-up

| Symptom | Action |
|---------|--------|
| Odoo up, apex 503 | lease-guard fenced or not renewing → unfence script |
| Odoo cannot start DB | `odoo-db` alias missing → `docker network connect --alias odoo-db …` |
| Slot inactive | confirm `:5432` publish + Frank receiver; do not recreate primary slot casually |
| Guard failed exit 2 | sticky `fenced:true` in lease-guard-state.json → unfence script |

## Test C — Auto-promote (requires P2/P3)

### Prerequisites beyond A/B

- Tailscale SSH to Frank works for operators (when TRL5 is offline, use Frank
  `wera` + docker/nsenter; do not depend on TRL5→Frank root hop)
- Dedicated Frank tunnel serves `odoo-frank.wera.global` (never TRL5 tunnel `6571cd54-…`)
- Frank `/etc/filantropia-embassy/embassy.toml` with real readiness URLs, generation, addon hash
- TRL5 Odoo loads `/etc/filantropia-embassy/readiness.env` (otherwise readiness 404 lies)
- Frank timers: embassy observe, filestore sync; standby status fresh; **lag 0**
- Code on Frank includes proof refresh, policy age-waive after fence, and
  executor (`service._maybe_execute_promotion`); Worker fencing-proof freshness deployed
- Flags **only** for the approved window:
  - `request_takeover_on_outage = true`
  - `automatic_actions_enabled = true`
  - `execute_promotion = true`
  - `standby_writer_generation` set and matching Frank `FS_WRITER_GENERATION`
- Frank standby `all_attachments_verified=true` (or an approved exception)
- **Do not stop** `filantropia-lease-guard.timer` on Frank for the window.
  Leave standby guard **fenced** in state file with timer enabled. As of
  2026-10-19, `execute_promotion` calls `arm_lease_guard_as_writer` after lease
  acquire (clear fence marker, unfence guard state, renew once, enable timer).
- Run `nextcloud-app/infra/embassy/scripts/test-c-preflight.sh` before arming.
- Failback order: `docs/ops/EMBASSY-FAILBACK-ANTI-RACE.md`.
- Pre-clear stale `fencing-proof.json` / old fence markers on Frank so drain
  refresh is not fighting a corrupt local proof

Residual (2026-10-15, leave for re-upload — do **not** clear the DB row):

- Orphan `ir.attachment` **836** `EDP.pdf` on **crm.lead 72**
  (Teresa Nolasco Pereira / Associação Dobermann em Risco - Dobie Hope)
- Created 2026-10-13 10:35:42Z via public candidatura (`public` user); checksum
  `7883bb561ea90d1d5f51092721c5777d048bf998`, path `78/7883bb…`
- Blob missing on TRL5 live filestore and Frank mirror; not in 2026-10-12
  filestore archives (upload is after those bundles)
- After contact re-uploads on lead 72, confirm primary file exists, Frank
  filestore sync picks it up, then `all_attachments_verified=true`

### Inject outage

Prefer controlled A3/A4 on TRL5 (stop lease-guard + cloudflared, or NIC down) so
Embassy dual-probe fails. Do **not** leave flags armed after the window.

### Pass criteria (hands-free)

Within designed RTO (~1–3 min warm) **and** hold for ≥5 minutes:

1. Lease owner becomes `frank`, `phase=active`
2. Apex/www **200** via Worker → `odoo-frank`
3. TRL5 path excluded (lease takeover / self-fence); no dual writer
4. Embassy journal shows `takeover_requested` then `promotion_executed` (no stuck
   `blocked_unfenced` / `blocked_standby` after acquirable + lag 0)
5. Frank lease-guard **active** and `lease_expires_at` advancing without manual
   acquire/renew
6. Failback afterward restores `active/trl5`, Frank streaming lag 0, flags off

### Production inject results

- **2026-10-17 Test C #1 — FAILED:** draining proof → `blocked_unfenced`; manual promote.
- **2026-10-19 Test C #2 — PARTIAL:** promote after mid-test policy waive; post-promote
  503 when lease-guard left stopped; manual re-acquire; failback OK.

Details: `docs/ops/INCIDENT-2026-10-17-TEST-C-FAILOVER.md`.

Do **not** re-arm auto-promote until post-promote lease-guard arming is shipped
and a full hands-free pass is recorded.

### Rollback

1. Disarm Frank flags (`execute_promotion=false`, takeover false, actions false)
2. Fence Frank Odoo; restore TRL5 lease (`trl5-unfence` + acquire) per failback runbook
3. Phase C route rollback only as last resort

## Explicit non-goals until Test C prerequisites pass

- Do **not** enable `request_takeover_on_outage` or `execute_promotion` on production Frank
- Do **not** start Frank Odoo outside an approved promote window
- Do **not** attach Frank to tunnel `filantropia-solar` (`6571cd54-…`)
- Do **not** point Worker `ORIGIN_TRL5_URL` at apex

## Post-test sign-off

Record:

1. Test ID (A1/A2/A3/A4/B/C), start/end UTC
2. Max public downtime seconds
3. Lease epochs before/after
4. Whether unfence script was required
5. Replication streaming yes/no after recovery
6. Any Phase C rollback

## Related docs

- `docs/ops/WRITER-GATE-PRODUCTION.md`
- `docs/ops/TRL4-ODOO-FAILOVER.md`
- `docs/ops/INCIDENT-2026-10-17-TEST-C-FAILOVER.md`
- `infra/embassy/scripts/trl5-unfence-lease-guard.sh`
- `docker-compose.trl5-repl-publish.yml`
