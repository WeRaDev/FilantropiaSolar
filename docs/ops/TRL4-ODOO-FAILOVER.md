# Frank TRL4 — Filantropia Odoo-only failover
## Current state and boundary (read-only, 2026-09-29)
Frank's Odoo PostgreSQL is healthy, but `filantropia-odoo` exited cleanly on
September 27 (`restart: no`) and `filantropia-cloudflared.service` is inactive.
The public website returns HTTP 200, but its origin has not been proven to be
Frank. Docker root is `/data-bulk/docker` on `/dev/sda7` ext4; encrypted
`/data` is a separate mount and does not protect the Docker data at rest.
**Do not start Odoo, switch a route, stop the DB, or mount over this store yet.**
On 2026-09-29 a read-only aggregate check found 27 CRM leads on Frank (latest
lead write August 18) versus 22 on TRL5 (latest lead write September 29).
This does not prove Frank accepted outage writes, but it blocks any destructive
Frank restore until record, attachment, and queued-job provenance is assessed.
A further read-only, in-memory comparison (no customer fields or lead IDs
printed) found 17 matching ID/creation-time pairs, ten Frank-only leads and
five TRL5-only leads. The Frank-only set has **four direct attachments across
four leads and 18 linked messages**; eight were last written by a different
user ID from their creator. No Frank job had `model_name = 'crm.lead'`, but
this does not rule out indirect jobs or show whether a lead is historical
test data. User IDs and timestamps cannot prove which host served public
writes. Preserve and privately review the records and matching filestore
before any overwrite; the original destructive-restore stop remains in force.
On September 30, another read-only comparison found the same 27/22 split,
ten Frank-only leads, four direct attachments and 18 linked messages.
TRL5's latest lead write is now September 30. Frank remains stopped while
TRL5 Odoo is healthy; neither the historical lead dates nor the current
container states prove public writer ownership or permit an overwrite.

Frank needs only the Filantropia website/CRM and its Odoo PostgreSQL during a
TRL5 outage. The legacy `filantropia-nextcloud`, MariaDB, Redis and ML
containers are not dependencies of this failover. City Nextcloud AIO/Talk is
a separate City service and must not be substituted for either API source.

## Preparation (no live service changes)
1. Prove which origin currently serves the public site and document the
   single-writer owner for CRM submissions. Record Odoo database, named
   volumes, addon/source versions and connector settings without reading
   secrets into command output. The Compose project must stay `nextcloud-app`
   to preserve existing Odoo volume identities.
2. Verify the selected TRL5-originated database/filestore recovery bundle on
   Frank (outer and component hashes, manifest, `pg_restore --list`, and
   filestore archive contents). Restore it into an isolated environment and
   test website rendering and a locally stored CRM lead. This bundle is a
   TRL5 promotion snapshot; it does not contain writes accepted by Frank after
   promotion. Before replacing Frank's current volume, rule out any prior
   unreconciled Frank-originated writes; if that cannot be proved, stop and
   capture/reconcile that state first. Preserve a coherent pre-restore Frank
   database/filestore pair for rollback before any destructive promotion;
   this is not a routine off-host backup of an unwritten standby. Handle City
   data separately.
3. On a development workstation, validate the additive overlay from the
   FilantropiaSolar repository root using
   `docker compose -f nextcloud-app/docker-compose.yml -f nextcloud-app/docker-compose.trl4-failover.yml --profile odoo config --quiet`. Confirm the
   existing Odoo volumes, `127.0.0.1:8069` bind and `restart: no`.
   Both services and their Odoo addon must be tested without Nextcloud before
   any production activation. The overlay is staged only; it has **not**
   changed Frank's Compose configuration.

## Outage rehearsal and controlled activation (separate approvals)
1. Select an approved window and a proved alternative public origin or a
   tested site rollback. Do not activate Frank's Cloudflare connector while
   another origin receives public writes. Confirm the selected TRL5 recovery
   pair, an independent City backup, the reversible root-backed runtime
   cutover, and storage startup guards first; the retired SolarSeed bootstrap
   scripts are **not** a shortcut around these gates.
2. Run only the `odoo-db` and `odoo` Compose services with the `odoo` profile
   and the overlay; never run a plain `up` of the legacy Nextcloud stack.
   Compose profiles do **not** stop already-running legacy containers or
   update their restart policies. Their eventual shutdown needs its own
   approved window and **must retain all named volumes**.
   After restoring and before opening ingress, record the selected TRL5 bundle
   name/hash and promotion UTC time, plus a baseline of CRM/profile changes,
   attachments, and queued-job state. Use this baseline to classify Frank-side
   writes during failback.
3. With `FS_NC_OFFLINE=1` and the bounded `FS_NC_HTTP_TIMEOUT=3`, Odoo must
   not fetch or mutate Nextcloud data. The `fs.public.snapshot` model retains
   the last **complete**, privacy-filtered public stations/dashboard payload,
   with a UTC refresh timestamp. The website explicitly labels it stale; if
   no valid dated snapshot exists, it shows unavailable metrics rather than
   invented zeroes. A future timestamp more than five minutes ahead is
   rejected. CRM application leads still persist in Odoo's database.
4. In an **isolated rehearsal**, verify page load time, snapshot label or
   unavailable marker, a submitted lead's Odoo ID, and absent Nextcloud HTTP
   traffic. Exercise lifecycle stage edits and inbound webhooks: offline
   synchronization must fail explicitly and not claim success. Record queued
   job failures and preserve the leads for reconciliation. Verify outbound
   mail and privacy controls separately rather than assuming them healthy.
5. Only after rehearsal, prove the intended public route and activate Frank's
   connector in a separately approved step; capture request tracing and a
   rollback route. The current HTTP 200 alone is not that proof.

### Local controller-level outage simulation (2026-10-02)
Three isolated tests passed:

- With `FS_NC_OFFLINE=1`, the controller served the dated last-known-good
  snapshot with a stale-data notice; the patched HTTP client was not called.
- When the stations request succeeded but the dashboard request timed out,
  the controller returned the entire previous complete snapshot rather than
  mixing live and stale data.
- A successful refresh persisted the complete enriched, privacy-filtered
  public snapshot.

Reproduction from the repository root:

```bash
python3 nextcloud-app/odoo/addons/filantropia_solar_public/tests/test_public_map_privacy.py PublicSnapshotFallbackTests.test_offline_snapshot_is_dated_and_never_calls_nextcloud
python3 nextcloud-app/odoo/addons/filantropia_solar_public/tests/test_public_map_privacy.py PublicSnapshotFallbackTests.test_partial_live_failure_uses_entire_last_complete_snapshot
python3 nextcloud-app/odoo/addons/filantropia_solar_public/tests/test_public_model_hooks.py PublicSnapshotCronTests.test_refresh_persists_complete_public_enriched_snapshot
```

This verifies only the Odoo controller's Nextcloud-dependency fallback using
mocks. No Docker services, TRL5, or Frank were contacted or changed. It does
**not** verify Embassy host promotion, PostgreSQL replication, independent
fencing, public ingress cutover, or failback; the isolated host-level rehearsal
and the gates in ADR 0007 remain outstanding.

## Software lease fence (repository implementation, 2026-10-05)

Repository code now includes a cooperative software fence rather than TRL5 power
control:

- Lease protocol: `nextcloud-app/infra/embassy/lease.py`
- Host self-fence guard: `nextcloud-app/infra/embassy/lease_guard.py`
- Cloudflare Worker + Durable Object gate: `nextcloud-app/infra/cloudflare-writer-gate/`
- Isolated lab authority: `nextcloud-app/infra/embassy/lab/`
- Postgres bootstrap helpers: `nextcloud-app/infra/embassy/replication_bootstrap.py`
- Staged filestore promotion: `nextcloud-app/infra/embassy/filestore_promote.py`

Dual-probe failure (origin readiness down **and** public routes down across
confirmation cycles) is the Embassy takeover trigger. It is **not** proof that
TRL5 has stopped writing. The Durable Object must refuse TRL5 renewals, the
TRL5 lease guard must stop local writers, and Frank may acquire the next epoch
only after lease expiry, drain, self-fence grace, standby validation, and
filestore checks.

Production defaults remain fail-closed (`automatic_actions_enabled = false`,
`request_takeover_on_outage = false`). As of 2026-10-14 the Worker routes for
`filantropiasolar.pt` / `www` are attached (Phase C); see
`docs/ops/WRITER-GATE-PRODUCTION.md`. The 2026-10-17 Test C inject **failed**
auto-promote (draining fencing proof); production was restored and failed back
to TRL5 on 2026-10-18 — see
`docs/ops/INCIDENT-2026-10-17-TEST-C-FAILOVER.md`. Do **not** enable automatic
takeover without a successful retest after Worker/Embassy proof-refresh deploys.
Residual risk: software fencing cannot stop a wedged host or a write path that
bypasses the lease guard. Public HTTP requires an **active** lease; an expired
lease yields 503 even when Odoo is healthy.

## Failback (manual single-writer gate)
TRL5 remains the source of truth while online. When TRL5 returns, fence Frank
before making TRL5 authoritative. Determine whether Frank accepted any
application writes during the outage, including CRM/profile changes and
queued-job effects; checking only for new leads is insufficient. Compare
against the recorded promotion baseline. If absence of writes cannot be
proved, use the writes-occurred path.

### No Frank-side writes
Leave TRL5's pre-outage database and filestore in place; do not restore a
TRL5-originated bundle held on Frank back onto TRL5. After Frank's Odoo and
public connector are fenced, start/verify TRL5 and return ingress to it in the
approved window. Validate the serving origin and accepted lead path.

### Frank accepted writes, or write status is uncertain
1. Keep Frank the sole writer until the approved cutover. Fence its public
   ingress, stop Frank Odoo, and verify it is exited while PostgreSQL remains
   available for a consistent database dump.
2. Create a fresh Frank-originated recovery set containing both the Odoo
   database and filestore. Record a manifest and checksums; validate the
   database archive, filestore archive, and round-trip copy before restore.
   The older TRL5-to-Frank recovery bundle is not a substitute for this set.
3. Preserve TRL5's pre-failback database/filestore as a rollback point before
   the destructive restore. Restore the fresh Frank-originated pair to TRL5
   while its Odoo writer remains stopped. With Frank fenced, start TRL5 Odoo
   behind closed public ingress and validate database/filestore consistency,
   the website, accepted leads, attachments, and queued jobs.
4. Only after validation, route ingress back to TRL5. Keep Frank fenced;
   never allow both Odoo instances to accept writes.

Reconcile pending/error jobs only under operator supervision after the
authoritative writer is chosen. **Automated safe failback is not demonstrated;
do not bulk-retry queued jobs or claim zero lost writes.**

For each host backup, service, mount or route operation, propose its exact
commands, one-sentence impact and rollback, then wait for explicit approval.
Neither this procedure nor the overall recovery plan authorizes live changes.
