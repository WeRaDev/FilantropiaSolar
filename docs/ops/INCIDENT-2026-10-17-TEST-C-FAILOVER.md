# Incident close-out — Test C TRL5 disconnect / auto-promote (2026-10-17 → 2026-10-19)

**Status:** CLOSED (production restored); auto-promote **not** yet declared production-ready  
**Last verified:** 2026-10-19T16:34Z (UTC)  
**Severity:** Production outage (public Odoo apex) during Test C and recovery  
**Primary writer at close:** `trl5`  
**Standby at close:** `frank` (streaming, lag 0)

## Summary

Test C injects a TRL5 dual-probe outage to exercise software-lease auto-promote to Frank.

| Run | Window (UTC) | Result |
|-----|--------------|--------|
| Test C #1 | 2026-10-17 ~19:40 | **FAILED** auto-promote: takeover OK, Frank stuck `blocked_unfenced` on draining proof; apex 503 until manual promote |
| Test C #2 | 2026-10-19 | **PARTIAL PASS** then operator-assisted durability: dual-probe + takeover worked; first blocked on frozen heartbeat/filestore ages; after mid-test policy waive, Embassy `promotion_executed` (frank epoch 24); post-promote lease expired because Frank lease-guard had been left stopped; re-acquire + re-enable guard restored apex; failback to TRL5 completed |

**Definition of done for a green Test C** (not yet met without operator touch):

1. Detect dual-probe outage  
2. Request takeover and wait until fencing proof is **acquirable**  
3. Authorize + execute promote (DB, filestore gates, lease acquire, start Odoo + Frank origin)  
4. Apex/www **200** via Worker → Frank  
5. Lease remains durable (Frank lease-guard renewing; expiry advancing) for ≥5 minutes with no manual re-acquire  
6. Disarm flags; documented failback restores TRL5 sole writer + Frank streaming standby  

## Timeline (UTC)

### Test C #1 and first recovery (2026-10-17 → 2026-10-18)

| Time | Event |
|------|--------|
| 2026-10-17 ~19:39 | Pre-inject: lease `active/trl5/epoch 16`, apex 200, Frank standby streaming, auto flags armed |
| 2026-10-17 19:40:04 | Frank Embassy: `primary_suspect` (TRL5 unreachable) |
| 2026-10-17 19:40:35 | Frank: `takeover_requested` then immediately `blocked_unfenced` |
| 2026-10-17 19:40:41 | Lease authority: takeover of trl5; proof `lease-takeover-16-…`; phase progressed to `acquirable`, owner null |
| 2026-10-17 19:41+ | Apex 503; Frank Odoo never started; journal stuck on `positive_independent_fencing_evidence_missing_or_invalid` |
| 2026-10-17 20:38–20:47 | Operator recovery on Frank: clear stale fences, `pg_promote`, start Odoo/origin, acquire lease (epochs 17–21), apex 200 via Frank |
| 2026-10-17 20:47 | Frank auto-promote flags **disarmed** |
| 2026-10-18 ~20:35 | Temporary renew-only guard stopped Odoo on expired self-lease (no reacquire) → apex 503 again |
| 2026-10-18 20:46–20:51 | Re-acquire + fixed renewer (self-expired reacquire); apex restored on Frank |
| 2026-10-18 22:48–23:01 | Durable Frank lease-guard enabled; failback: basebackup Frank→TRL5, promote TRL5, lease → `trl5` epoch 22–23 |
| 2026-10-18 23:02–23:17 | Frank rebuilt as standby from TRL5; TRL5 `:5432` Tailscale publish restored; streaming verified |
| 2026-10-18 23:21–23:25 | Health after first failback: apex/www/trl5 200; lag 0 |

### Test C #2 and second failback (2026-10-19)

| Time | Event |
|------|--------|
| Pre-window | Deployed Worker fencing-proof freshness (`bde010c0-8422-4b49-bc58-5f0aa2b64381`); Embassy proof-refresh + lease-guard self-reacquire on hosts; TRL5 readiness env restored; orphan sitemap att path cleaned so Frank `all_attachments_verified=true`; Frank fences/proof cleared; flags armed; **Frank lease-guard timer stopped** to avoid promote race |
| Inject | TRL5 offline ~10+ min; dual-probe confirmed; takeover requested |
| Mid-path | Frank stuck `blocked_standby` on stale primary heartbeat/filestore **ages** (~16 min) despite lag **0** (primary-originated timestamps freeze during outage) |
| Fix | Deployed `policy.py` waive of primary heartbeat/filestore *ages* after valid lease fence when lag=0 (lineage/attachments still enforced) |
| Promote | Embassy `promotion_executed` → **frank epoch 24**; apex 200 via Frank |
| Regression | Lease-guard still stopped → lease TTL expired → apex 503 while Frank origin still 200 |
| Repair | Manual re-acquire **epoch 25**; re-enable Frank lease-guard; stability PASS (expiry advancing) |
| Failback | TRL5 back; basebackup Frank→TRL5; promote TRL5; lease races while Frank still armed/renewing → eventually **trl5 epochs 26–28**; Frank fenced/disarmed; Frank re-seeded streaming lag 0 |
| 2026-10-19 16:34 | Final health PASS: `active/trl5/28`, apex/www/trl5 200, Frank Odoo stopped/fenced, auto flags false |

## Root causes

### Test C #1 — `blocked_unfenced`

1. Embassy requested lease takeover successfully.  
2. Takeover response wrote `fencing-proof.json` with `phase=draining`, `acquirable=false`.  
3. Policy requires `require_lease_acquirable=true` → fence invalid → `blocked_unfenced`.  
4. Observer did not refresh proof from `/lease/status` through drain→acquirable; stale proof on disk blocked further progress.  
5. Worker fencing-proof expiry was fixed to takeover time; proofs aged out while lease was still acquirable.

### Test C #2 — `blocked_standby` then post-promote 503

1. **Policy:** After a valid lease fence, primary heartbeat rows and filestore *pull* generation ages cannot advance while TRL5 is offline. Requiring those ages ≤ RPO always blocks promote once outage lasts longer than the budget, even with WAL lag 0 and verified attachments.  
2. **Ops/executor gap:** Prep stopped Frank `filantropia-lease-guard.timer` for a promote race. `execute_promotion` acquires the lease and starts Odoo/origin but **does not arm/unfence the lease-guard**. Without renewals, TTL (30s) expires → Worker 503 `no active writer epoch`.  
3. **Failback race:** Leaving Frank auto flags and renewals active while reclaiming TRL5 causes epoch thrash until Frank is fenced and disarmed.

**Not the cause (either run):** auto flags incorrectly left off at inject time when the window was armed.

## Fixes applied

| Area | Change | Status |
|------|--------|--------|
| `embassy/promote.py` | `refresh_fencing_proof_from_status`, `wait_for_acquirable_fencing_proof`; takeover waits for acquirable | Committed `a6c08ce`; on hosts |
| `embassy/service.py` | Refresh stale/draining proofs before evaluate; re-refresh when `blocked_unfenced` | Committed `a6c08ce`; on hosts |
| `embassy/policy.py` | Public `fencing_evidence_is_valid`; waive primary heartbeat/filestore *ages* after valid fence when lag=0 | Committed `bfd8a2e`; deployed Frank |
| `embassy/lease_guard.py` | Self-reacquire when own lease expires (`phase=acquirable`, owner=self); readiness ignores non-`fenced` markers | Committed `a6c08ce`; on hosts |
| `embassy/writer_control.py` | Fence identity accepts configured node (not TRL5-only) | Committed `a6c08ce` |
| `writer-gate.js` | Fencing proof freshness tied to observation time | Deployed Worker version `bde010c0-…` |
| Unit tests | Policy tests updated for waive + lag gates | Local (post-session) |

## Residual gaps before declaring Test C green

Production is healthy on TRL5. Remaining for a **recorded hands-free** Test C PASS:

1. **Deploy** post-promote `arm_lease_guard_as_writer` (repo implemented 2026-10-19) to Frank Embassy path and confirm unit tests on host Python.  
2. **Approved window retest** with preflight `scripts/test-c-preflight.sh`, flags armed only for the window, ≥5 min durable Frank lease, zero manual lease repair.  
3. **Failback** using `docs/ops/EMBASSY-FAILBACK-ANTI-RACE.md` (disarm/fence Frank before TRL5 acquire).  
4. **Push/PR** branch `feat/odoo-host-failover-software-lease` (includes proof-refresh, age-waive, arm-on-promote, docs).  
5. **Optional:** rotate replication password if historical debug exposure confirmed; orphan CRM attachment on lead 72 remains a customer item.

## Failback path used (both recoveries)

Frank had accepted writes (writes-occurred / uncertain branch):

1. Preserve TRL5 pre-failback PG under `/data/filantropia-embassy/failback-from-frank-trl5-pgdata-*`  
2. `pg_basebackup` from Frank → TRL5; promote TRL5 PG  
3. Filestore rsync Frank → TRL5 Odoo volume; `chown` for Odoo uid  
4. Fence Frank Odoo; disarm auto flags; lease → **trl5**  
5. Start TRL5 Odoo + cloudflared; enable TRL5 lease-guard  
6. Rebuild Frank PG as standby from TRL5 (`frank_odoo_slot`); Odoo stopped; Frank lease-guard left **fenced**

Prefer compose overlay `docker-compose.trl5-repl-publish.yml` **or** socat publish — not both. Always ensure `odoo-db` alias on `nextcloud-app_filantropia-net` after DB recreate.

## Final system state (2026-10-19T16:34Z)

### Lease / public

| Item | Value |
|------|--------|
| Lease phase | `active` |
| Owner | `trl5` |
| Epoch | `28` |
| Generation | `writer-epoch-20261012-trl5-primary` |
| Apex / www / odoo-trl5 | HTTP **200** |
| odoo-frank | HTTP **530** (Odoo stopped — expected) |
| Lease expiry | advancing under TRL5 lease-guard |

### TRL5 (`100.82.252.18`)

| Item | Value |
|------|--------|
| Role | Single writer |
| PG | primary (`pg_is_in_recovery=f`) |
| Attachments | 609 |
| Slot | `frank_odoo_slot` active / streaming |
| Lease-guard timer | **active**; not fenced |
| Odoo readiness env | required for dual-probe truth |

### Frank (`100.82.194.96`)

| Item | Value |
|------|--------|
| Role | Streaming standby |
| PG | `pg_is_in_recovery=t`; apply lag **0** |
| Attachments | 609 |
| Odoo | exited; restart=no |
| Lease-guard | enabled; state **fenced** (`failback_to_trl5`) |
| Auto-promote flags | **all false** |

### Safety invariants

- Single lease owner: trl5  
- Single Odoo writer: trl5  
- Frank Odoo stopped + fenced  
- Attachment counts equal  
- Replication lag effectively zero  
- Auto-promote disarmed outside approved windows  

## Lessons learned (session)

1. **Fence ≠ promote.** Takeover only excludes the old writer; promote still needs acquirable proof, standby integrity, and a live renew path after acquire.  
2. **Primary-sourced freshness freezes on outage.** After independent lease fence + lag 0, waive heartbeat/filestore *ages*; keep lineage, attachment verification, and standby-local status ages.  
3. **Lease TTL is the public availability clock.** Stopping lease-guard on the live writer (or the newly promoted writer) produces apex 503 even when Odoo is healthy.  
4. **Do not stop Frank lease-guard “for the promote race”** unless promote itself arms the guard before returning success.  
5. **Draining proofs must be refreshed** from the authority until `acquirable=true` or timeout; never treat the first takeover response as final.  
6. **Worker proof expiry must track observation time**, not only takeover start, or standbys permanently `blocked_unfenced`.  
7. **Failback is a dual-writer race** unless Frank is fenced and disarmed first.  
8. **Host access paths matter:** when TRL5 is offline, Frank root via TRL5 hop fails; use Frank `wera` + docker/nsenter.  
9. **Readiness 404 on TRL5** makes Embassy lie about primary health; compose must inject `/etc/filantropia-embassy/readiness.env`.  
10. **Orphan filestore rows** block `all_attachments_verified` on both nodes; fix blobs or null `store_fname` with explicit ops approval.  
11. **Cooperative fencing residual remains:** software lease cannot prove a wedged host stopped; automatic promotion stays conditional on rehearsed self-fence coverage.

## Open follow-ups

1. Implement post-promote lease-guard arming in Embassy executor (P0 for green Test C).  
2. Add unit/integration coverage for promote → guard active → renew advances expiry.  
3. Push branch / open PR; keep auto flags off until green retest.  
4. Re-run Test C only in an approved window with full preflight.  
5. Optional repl password rotation if leaked in historical debug logs.  

## Sign-off

| Field | Value |
|-------|--------|
| Incident | Test C disconnect + auto-promote failures/partial success + recovery + failback |
| Result | **Closed — production restored on TRL5** (2026-10-19) |
| Auto-promote | **Not** production-ready until post-promote lease-guard durability is automatic and Test C passes without operator lease repair |
| Documented by | Warp agent sessions 2026-10-17/18/19 |
| Related | `docs/ops/WRITER-GATE-PRODUCTION.md`, `docs/ops/TRL5-STRESS-TEST-RUNBOOK.md`, `docs/ops/TRL4-ODOO-FAILOVER.md`, plan `2b008856-5477-420e-924b-a207ed1995e4` |
