# Odoo CRM + queue_job inventory (MVP)

**Date:** 2026-08-11  
**Addon:** `filantropia_solar_public` **19.0.2.7.0**  
**Depends (manifest):** `website`, `website_blog`, `crm` — **no `queue_job`**  
**Runtime:** Odoo 19 Community (`odoo:19.0`)

## What exists today

### CRM usage (`controllers/main.py`)

| Flow | Behavior |
|------|----------|
| Contact form `POST /contacto/enviar` | Creates `crm.lead` (description marks simple contact) |
| Candidatura SME path | Creates `crm.lead` (not eligible / WeRa referral) |
| Candidatura NGO `POST /candidatura/enviar` | Creates `crm.lead` with rich description + bill attachments |

Leads are created with **default CRM stage** (typically New).  
**No** `stage_id` write hooks, **no** automate actions in addon data XML for stage changes.  
**No** call to Nextcloud to create a Virtual station after lead create.  
**No** custom fields on `crm.lead` for `x_nc_installation_id` / ML id (not in manifest data files reviewed).

### FS / NC client from Odoo

Public site already calls NC for stations/dashboard/estimate (env `FS_API_BASE_URL`, `FS_PUBLIC_API_TOKEN`).  
That path is **read/estimate**, not lifecycle write.

### queue_job

- Not in addon `depends`.  
- Not referenced in addon Python.  
- Packaging choice still open: install OCA `queue_job` compatible with Odoo 19 Community in compose **or** temporary `ir.cron` poller documented as deviation from D7.

## Gaps vs MVP (D4, D7)

| Requirement | Gap |
|-------------|-----|
| Lead create → Virtual station on NC | Missing outbound write API client + post-create hook |
| Stage New→Qualified → Planned | Missing `crm.lead` write override or automation + job |
| Won does not install | Must **not** add Won→Running; document/test negative case |
| Installation id on lead | Missing lead fields + UI optional |
| Async non-blocking CRM | Missing queue_job (or interim cron) |
| Idempotency | Missing client key (e.g. `odoo_lead_id`) on NC create/promote |
| Failure visibility | No dead-letter; lead has no “NC sync error” field |

## Recommended MVP design (Odoo side)

1. **Fields on `crm.lead` (or thin `filantropia.lead.station` model):**  
   `nc_installation_id`, `nc_lifecycle_state`, `nc_sync_state`, `nc_sync_error`, `nc_last_sync_at`.
2. **On candidatura NGO lead create:** enqueue job `filantropia_create_virtual_station(lead_id)`.
3. **On stage change to Qualified:** enqueue `filantropia_promote_planned(lead_id)` (skip if already planned).
4. **On Won:** no NC lifecycle call (test asserts no mark-installed).
5. **HTTP client:** service methods using existing token pattern; timeouts; retry via queue_job.
6. **Depends:** add `queue_job` when OCA wheel/repo pinned; else `ir.cron` every 1–5 min processing a “pending sync” domain — ADR required if cron.

## queue_job packaging check (to run before coding)

```text
- Confirm OCA queue_job branch/tag for Odoo 19 Community
- Add to filantropia compose odoo addons_path
- Smoke: job appears in queue_job UI after lead create
- CI: optional; local/TRL5 must run job runner worker or channels
```

If OCA 19 support is blocked, document **D7 interim:** `ir.cron` + `nc_sync_state` machine, migrate to queue_job when available.

## Tests to add (MVP gates)

- Unit: stage transition helper maps Qualified→promote, Won→noop.  
- Integration (HTTP mock NC): lead create enqueues/calls virtual create once (idempotent second call).  
- Manual: Qualify lead → Planned on public map after job; Won alone does not change public Existing set.