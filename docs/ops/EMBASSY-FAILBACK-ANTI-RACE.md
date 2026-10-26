# Embassy failback anti-race (Frank → TRL5)

Use this **ordered** procedure after Frank held the software lease (Test C or
real promote). Skipping the disarm/fence steps causes lease epoch thrash and
apex 503s.

Related: `docs/ops/INCIDENT-2026-10-17-TEST-C-FAILOVER.md`,
`docs/ops/TRL4-ODOO-FAILOVER.md`, `docs/ops/WRITER-GATE-PRODUCTION.md`.

## Invariants

- Only one Odoo writer and one lease owner at a time.
- Public apex requires `phase=active` with renewals (lease-guard timer).
- Frank standby posture: Odoo stopped, lease-guard **state fenced**, auto flags
  **false**, PG in recovery.

## Ordered failback (writes occurred or uncertain)

1. **Disarm Frank auto-promote** in `/etc/filantropia-embassy/embassy.toml`:
   - `request_takeover_on_outage = false`
   - `execute_promotion = false`
   - `automatic_actions_enabled = false`
2. **Fence Frank writers**
   - Stop/restart-policy-no `filantropia-odoo` (and any queue workers).
   - Set lease-guard state `fenced=true` with reason `failback_to_trl5`.
   - Leave `filantropia-lease-guard.timer` enabled (it must stay no-op while
     fenced) **or** stop renewals explicitly if state cannot be fenced yet.
3. **Preserve rollback**
   - Snapshot TRL5 PG/filestore under `/data/filantropia-embassy/failback-from-frank-trl5-pgdata-*`
     before destructive reseed when Frank accepted writes.
4. **Reseed TRL5 from Frank authority**
   - `pg_basebackup` / restore Frank-originated pair; promote TRL5 PG.
   - Filestore rsync Frank → TRL5; fix ownership for Odoo uid.
5. **Acquire lease as trl5** only after Frank cannot renew
   - Takeover/acquire path → owner `trl5`.
   - Enable TRL5 lease-guard; confirm `lease_expires_at` advances.
6. **Start TRL5 Odoo + cloudflared**; apex/www/odoo-trl5 **200**.
7. **Rebuild Frank streaming standby** from TRL5
   - Prefer compose overlay `docker-compose.trl5-repl-publish.yml` **or** socat
     publish — not both.
   - Ensure `odoo-db` alias on `nextcloud-app_filantropia-net`.
   - Slot `frank_odoo_slot` streaming; lag 0; Odoo stopped; guard fenced.
8. **Verify**
   - Lease `active/trl5`; Frank flags still false; attachment counts match.

## Ordered failback (no Frank writes proved)

If Frank never accepted application writes: fence Frank, restore TRL5 lease and
services without reseed if TRL5 data is intact; still disarm Frank flags first.

## Anti-patterns (do not)

- Acquire TRL5 lease while Frank still renews or auto flags remain true.
- Stop TRL5 lease-guard after TRL5 becomes writer.
- Stop Frank lease-guard during Test C prep “to avoid races” unless promote
  arms it (Embassy `execute_promotion` now arms by default).
- Join Frank to TRL5 tunnel `6571cd54-…`.

## Promote path note (2026-10-19+)

`embassy.promote.execute_promotion` calls `arm_lease_guard_as_writer` after
lease acquire: clears local Odoo fence marker, writes unfenced guard state,
optionally renews once, enables `filantropia-lease-guard.timer`. Promote fails
closed if arming cannot prove `phase=active` for the new owner.

## After Test C #3 failback (2026-10-20 ~14:38Z)

- Public writer: **TRL5** (`active` lease epoch 32, guard renewing).
- Frank: streaming standby, Odoo stopped, lease-guard **fenced**, auto flags **false**.
- Attachment counts matched at 610 after Frank-originated reseed.
- Frank origin container name remains `filantropia-cloudflared-frank` for next promote.
