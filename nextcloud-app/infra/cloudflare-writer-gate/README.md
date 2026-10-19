# Filantropia Odoo writer gate (Cloudflare Worker + Durable Object)

Repository-owned software fence and public origin proxy for the TRL5↔Frank
Odoo failover path.

## What it does

- Stores a single-writer lease (owner, epoch, generation, expiry, takeover) in
  a Durable Object with strongly consistent storage (SQLite-backed class).
- Refuses lease renewals after takeover is requested.
- Grants the next epoch only after lease expiry, in-flight drain, and
  self-fence grace.
- Proxies public website requests only to the host that holds the active epoch.
- Fails closed when the authority is unavailable or ownership is unclear.
- Uses constant-time bearer comparison for `/lease/*` auth.
- Bounds upstream origin fetches (`ORIGIN_FETCH_TIMEOUT_MS`, default 10s).

## What it does not do

- It does **not** power-off TRL5.
- It does **not** stop a wedged host by itself; each host must run
  `lease_guard` and stop Odoo/cron/queue workers on refused renewal or expiry.
- Same-tunnel Cloudflare replicas are still not an active/standby mechanism.
  Use separate authenticated origins and this Worker gate.
- It does **not** proxy WebSocket upgrades (returns 501). Odoo bus/live
  features that require `Upgrade: websocket` need a separate plan before
  production route cutover if those features are required on the public host.

## Residual race (documented)

Public proxy checks lease status, then permit, then fetches the origin. A lease
can expire in that window. Host `lease_guard` remains the hard writer stop; the
Worker only reduces the set of origins that may receive public traffic.

## Activation boundary

Checked-in source only. Do **not** deploy, attach the production hostname, or
set production secrets without separate explicit approval and a successful
isolated host-level rehearsal.

### Phase A (workers.dev lease authority only)

```bash
cd nextcloud-app/infra/cloudflare-writer-gate
npx wrangler deploy
openssl rand -base64 32 | npx wrangler secret put LEASE_API_TOKEN
openssl rand -base64 32 | npx wrangler secret put ORIGIN_SHARED_SECRET
# Bootstrap after secrets:
# POST /lease/bootstrap {"node_id":"trl5","generation":"writer-epoch-20261012-trl5-primary"}
```

Keep production `routes` commented until Phase B origins exist and Phase C is
explicitly approved.
