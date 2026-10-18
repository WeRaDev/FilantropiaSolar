# Incident close-out — Test C TRL5 disconnect / auto-promote (2026-10-17 → 2026-10-18)

**Status:** CLOSED  
**Closed at:** 2026-10-18T23:25Z (UTC)  
**Severity:** Production outage (public Odoo apex) during Test C and subsequent recovery  
**Primary writer at close:** `trl5`  
**Standby at close:** `frank` (streaming)

## Summary

Test C injected a TRL5 network disconnect to exercise software-lease auto-promote to Frank. **Automatic promote failed.** Lease takeover ran, but Frank Embassy remained `blocked_unfenced` because a draining/non-acquirable fencing proof was persisted and never refreshed. Public apex stayed **503** (`no active writer epoch`).

Operators restored service on Frank (manual promote + lease acquire), then performed failback to TRL5 after TRL5 returned. Production was verified healthy with zero replication lag before close.

## Timeline (UTC)

| Time | Event |
|------|--------|
| 2026-10-17 ~19:39 | Pre-inject: lease `active/trl5/epoch 16`, apex 200, Frank standby streaming, auto flags armed |
| 2026-10-17 19:40:04 | Frank Embassy: `primary_suspect` (TRL5 unreachable) |
| 2026-10-17 19:40:35 | Frank: `takeover_requested` then immediately `blocked_unfenced` |
| 2026-10-17 19:40:41 | Lease authority: takeover of trl5; proof `lease-takeover-16-…`; phase progressed to `acquirable`, owner null |
| 2026-10-17 19:41+ | Apex 503; Frank Odoo never started; journal stuck on `positive_independent_fencing_evidence_missing_or_invalid` |
| 2026-10-17 20:38–20:47 | Operator recovery on Frank: clear stale fences, `pg_promote`, start Odoo/origin, acquire lease (epochs 17–21 over recovery), apex 200 via Frank |
| 2026-10-17 20:47 | Frank auto-promote flags **disarmed** |
| 2026-10-18 ~20:35 | Temporary renew-only guard stopped Odoo on expired self-lease (no reacquire) → apex 503 again |
| 2026-10-18 20:46–20:51 | Re-acquire + fixed renewer (self-expired reacquire); apex restored on Frank |
| 2026-10-18 22:48–23:01 | Durable Frank lease-guard enabled; failback: basebackup Frank→TRL5, promote TRL5, lease → `trl5` epoch 22–23 |
| 2026-10-18 23:02–23:17 | Frank rebuilt as standby from TRL5; TRL5 `:5432` Tailscale publish restored; streaming verified |
| 2026-10-18 23:21–23:25 | Final health: apex/www/trl5 200; lag 0; incident closed |

## Root cause (Test C auto-promote fail)

1. Embassy requested lease takeover successfully.
2. Takeover response wrote `fencing-proof.json` with `phase=draining`, `acquirable=false`.
3. Policy requires `require_lease_acquirable=true` → fence invalid → `blocked_unfenced`.
4. Observer did not refresh proof from `/lease/status` through drain→acquirable; stale proof on disk blocked further `request_lease_takeover` proposals.
5. Proof expiry window was short relative to wall-clock; even live status proofs aged out under old Worker fencing-proof expiry semantics.

**Not the cause:** auto flags were correctly armed (`request_takeover_on_outage`, `execute_promotion`, `automatic_actions_enabled`).

## Fixes applied

| Area | Change |
|------|--------|
| `embassy/promote.py` | `refresh_fencing_proof_from_status`, `wait_for_acquirable_fencing_proof`; takeover waits for acquirable |
| `embassy/service.py` | Refresh stale/draining proofs before evaluate; re-refresh when blocked_unfenced |
| `embassy/policy.py` | Public `fencing_evidence_is_valid` helper |
| `embassy/lease_guard.py` | Self-reacquire when own lease expires (`phase=acquirable`, owner=self); readiness ignores non-`fenced` markers |
| `embassy/writer_control.py` | Fence identity accepts configured node (not TRL5-only) |
| `writer-gate.js` (repo) | Fencing proof freshness tied to observation time (deploy to Cloudflare still pending) |
| Hosts | Code deployed to Frank/TRL5 embassy paths; unit tests 29 OK locally |

## Failback path used

Frank had accepted writes (uncertain/writes-occurred branch):

1. Preserve TRL5 pre-failback PG: `/data/filantropia-embassy/failback-from-frank-trl5-pgdata-20261018T225232Z`
2. `pg_basebackup` from Frank → TRL5; promote TRL5 PG
3. Filestore rsync Frank → TRL5 Odoo volume; `chown` for Odoo uid
4. Fence Frank Odoo; lease takeover/acquire → **trl5**
5. Start TRL5 Odoo + cloudflared; enable TRL5 lease-guard
6. Rebuild Frank PG as standby from TRL5 (`frank_odoo_slot`); Odoo stopped; Frank lease-guard left **fenced**

## Final system state (close snapshot ~2026-10-18T23:25Z)

### Lease / public

| Item | Value |
|------|--------|
| Lease phase | `active` |
| Owner | `trl5` |
| Epoch | `23` |
| Generation | `writer-epoch-20261012-trl5-primary` |
| Apex / www / odoo-trl5 | HTTP **200** |
| odoo-frank | HTTP **502** (Odoo stopped — expected) |

### TRL5 (`100.82.252.18`)

| Item | Value |
|------|--------|
| Role | Single writer |
| PG | primary (`pg_is_in_recovery=f`) |
| Odoo / cloudflared | up |
| Lease-guard timer | enabled + active; result `active`; not fenced |
| Repl publish | `filantropia-pg-repl-publish.service` active (`100.82.252.18:5432` via socat) |
| Slot | `frank_odoo_slot` active |
| Replication lag to Frank | **0 bytes** (streaming async) |
| Attachments | 609 |

### Frank (`100.82.194.96`)

| Item | Value |
|------|--------|
| Role | Streaming standby |
| PG | `pg_is_in_recovery=t`; apply lag **0** |
| Odoo | exited; restart=no |
| Origin connector | up or idle; public origin 502 without Odoo |
| Lease-guard timer | enabled + active; state **fenced** (`failback_to_trl5`) — intentional for standby |
| Auto-promote flags | **all false** |
| Temp nohup renewer | **removed** |
| Attachments | 609 (matches primary) |

### Safety invariants at close

- Single lease owner: trl5  
- Single Odoo writer: trl5  
- Frank Odoo stopped + fenced  
- Attachment counts equal  
- Replication lag effectively zero  

## Lessons for next Test C

1. Deploy Worker fencing-proof freshness + Embassy proof-refresh code **before** arming auto-promote.
2. Lease-guard must self-reacquire expired **own** lease (deployed); do not use renew-only loops that stop the writer on TTL miss.
3. After any `docker compose` recreate of `odoo-db` on TRL5: ensure `odoo-db` alias on `nextcloud-app_filantropia-net` and that host `:5432` publish does not leave the DB container networkless.
4. Prefer compose overlay `docker-compose.trl5-repl-publish.yml` **or** socat unit — not both fighting the same bind.
5. Keep auto flags disarmed outside an approved window; disarm immediately after the test.
6. Do not leave long-lived Mac/nohup lease renewers as the sole writer heartbeat.

## Open follow-ups (non-blocking)

1. Deploy `writer-gate.js` fencing-proof change to Cloudflare (wrangler deploy).
2. Commit embassy/lease-guard/writer-gate source fixes on branch `feat/odoo-host-failover-software-lease`.
3. Optional: rotate replication password if it appeared in any host debug logs during basebackup.
4. Orphan attachment 836 / lead 72 still tracked for customer re-upload (pre-existing).
5. Re-run Test C only after (1) and a clean dry-run of drain→acquirable→promote on Frank.

## Sign-off

| Field | Value |
|-------|--------|
| Incident | Test C disconnect + auto-promote failure + recovery + failback |
| Result | **Closed — production restored on TRL5** |
| Auto-promote | Still **not** production-ready until Worker deploy + successful retest |
| Documented by | Warp agent session 2026-10-17/18 |
| Related | `docs/ops/WRITER-GATE-PRODUCTION.md`, `docs/ops/TRL5-STRESS-TEST-RUNBOOK.md`, `docs/ops/TRL4-ODOO-FAILOVER.md` |
