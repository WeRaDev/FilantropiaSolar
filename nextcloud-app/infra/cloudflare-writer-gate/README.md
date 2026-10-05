# Filantropia Odoo writer gate (Cloudflare Worker + Durable Object)

Repository-owned software fence and public origin proxy for the TRL5↔Frank
Odoo failover path.

## What it does

- Stores a single-writer lease (owner, epoch, generation, expiry, takeover) in
  a Durable Object with strongly consistent storage.
- Refuses lease renewals after takeover is requested.
- Grants the next epoch only after lease expiry, in-flight drain, and
  self-fence grace.
- Proxies public website requests only to the host that holds the active epoch.
- Fails closed when the authority is unavailable or ownership is unclear.

## What it does not do

- It does **not** power-off TRL5.
- It does **not** stop a wedged host by itself; each host must run
  `lease_guard` and stop Odoo/cron/queue workers on refused renewal or expiry.
- Same-tunnel Cloudflare replicas are still not an active/standby mechanism.
  Use separate authenticated origins and this Worker gate.

## Activation boundary

Checked-in source only. Do **not** deploy, attach the production hostname, or
set production secrets without separate explicit approval and a successful
isolated host-level rehearsal.
