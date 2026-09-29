# Frank TRL4 — Filantropia Odoo-only failover
## Current state and boundary (read-only, 2026-09-29)
Frank's Odoo PostgreSQL is healthy, but `filantropia-odoo` exited cleanly on
September 27 (`restart: no`) and `filantropia-cloudflared.service` is inactive.
The public website returns HTTP 200, but its origin has not been proven to be
Frank. Docker root is `/data-bulk/docker` on `/dev/sda7` ext4; encrypted
`/data` is a separate mount and does not protect the Docker data at rest.
**Do not start Odoo, switch a route, stop the DB, or mount over this store yet.**

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
   capture/reconcile that state first. Handle City data separately.
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
   another origin receives public writes. Confirm verified backups and the
   storage migration/startup guards first; the retired SolarSeed bootstrap
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
   while its Odoo writer remains stopped. Validate database/filestore
   consistency, accepted leads, attachments, and queued jobs.
4. Only after validation, activate TRL5 and route ingress back to it. Keep
   Frank fenced; never allow both Odoo instances to accept writes.

Reconcile pending/error jobs only under operator supervision after the
authoritative writer is chosen. **Automated safe failback is not demonstrated;
do not bulk-retry queued jobs or claim zero lost writes.**

For each host backup, service, mount or route operation, propose its exact
commands, one-sentence impact and rollback, then wait for explicit approval.
Neither this procedure nor the overall recovery plan authorizes live changes.
