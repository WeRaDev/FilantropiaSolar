# Epic MVP — Admin/CRM integrity

**Goal:** Ops manage lifecycle without dual systems fighting; CRM and NC stay bidirectional (stages + station profile); public site frozen and stable.

**Decisions:** D1–D4, D7, D9, D10  
**Do not start feature coding until** `docs/architecture/TRS-ADDENDUM-D1-D10.md` is merged (this branch).

## Success (from plan)

Ops run lifecycle on **Nextcloud admin**; CRM stages mirror NC (**Qualified→Virtual**, **Proposition→Planned**, **Installed→Running**); ADR 0006; public TRL5 stable; no second Odoo station admin.

## Stories

### MVP-0 — Documentation baseline (this delivery)

- [x] TRS addendum D1–D10  
- [x] NC gap inventory  
- [x] Odoo CRM / queue_job inventory  
- [x] Lifecycle OpenAPI sketch  
- [x] ADRs 0001–0005  

**Gate:** docs merged; eng onboards from addendum not raw TRS.

---

### MVP-1 — NC lifecycle data model ✅  
**Maps:** D3, D4  

- Migration: `lifecycle_state` (`virtual|planned|running`), `soft_removed`, `odoo_lead_id` (unique nullable), optional `installed_at`.  
- Derive `running_mode` active|offline from measured data presence (rule documented).  
- Mapper + entity + admin JSON include new fields.  

**AC:** Existing dataset stations default to `running` + not soft_removed; virtuals explicit; unique lead id enforced.

---

### MVP-2 — NC lifecycle write API ✅  
**Maps:** D1, D4, D7  

- Implement OpenAPI paths in `docs/architecture/nc-odoo-lifecycle-api.openapi.yaml`.  
- Bearer auth (reuse or dedicated token).  
- Idempotent virtual create by `odoo_lead_id`.  

**AC:** Contract tests/mocks; double POST virtual → one row; illegal transitions → 409.

---

### MVP-3 — Public API filter Existing+Planned ✅  
**Maps:** D3, D9  

- Change `GET /api/public/v1/stations` (and dashboard aggregates) to lifecycle public rules.  
- Never return virtual or soft_removed.  

**AC:** Odoo map smoke still 200; fixture with virtual not listed; planned listed with category.

---

### MVP-4 — NC admin UI lifecycle actions ✅  
**Maps:** D2, D4  

- Actions: promote planned, mark installed, soft-remove (hard-delete policy stub OK if soft-remove ships).  
- List filters by state.  

**AC:** Manual checklist in plan exit gates.  
**App version:** 3.2.3 — session-auth admin lifecycle endpoints + admin UI.

---

### MVP-5 — Odoo lead fields + NC client ✅  
**Maps:** D1, D4  

- Lead fields for NC ids/sync state.  
- Service calling lifecycle API with token from config (no log of token).  
- Extended by PR #29: demotions, profile sync, NC→CRM webhook, ops-only fleet import, public map list focus.  

**AC:** Unit tests with http mock; token redaction in logs; ADR 0006 stage matrix.

---

### MVP-6 — queue_job (or ADR interim cron) ✅  
**Maps:** D7  

- Package queue_job on Odoo 19 Community **or** ADR + cron interim.  
- Jobs: ensure Virtual on Qualified; promote on Proposition; mark-installed on Installed;
  set-lifecycle on demotion; profile push on station field edits.  
- New has no NC station until Qualified (ADR 0006).  
- Hourly `import_all_from_nc` reconcile + dashboard import button.  

**AC:** CRM UI returns without waiting on NC; failed job visible; retry safe.

---

### MVP-7 — Automated + manual gates  
**Maps:** D10  
**Status:** Automated gates green; local CRM script signed; **TRL5 deployed** NC **3.2.26** + Odoo **19.0.2.22.0** (2026-08-14). Optional: browser analytics smoke; ops fleet seed for public map.  

- Tests: promote/remove; Won noop; public filter.  
- Manual script: form → New (no NC) → Qualify → Virtual → Proposition → Planned on map → Installed → Running/Existing.  
- Deploy note TRL5: NC + Odoo; no secret echo.  

**AC:** CI green; manual checklist signed by operator (CRM + TRL5 tables).  
**Checklist:** `docs/mvp/MVP-7-GATES-TRL5.md`.  
**Also on main:** series epic + analytics PR #31 — provenance, grid_connection_type, FilantropiaSolarAdmin, chunked SeriesBackfillJob + **hourly** SeriesRollForwardJob (3600s), NC Historical SoT / Predicted ops sim / Lisbon TZ / dual I/O.

---

## Non-goals (MVP)

- Effective dating, piecewise savings, PDF/XLSX (V1)  
- Live feed (V2 spike)  
- Public website features  
- Global ML model  

## Dependency order

```text
MVP-0 → MVP-1 → MVP-2 → MVP-3
                ↘ MVP-4
MVP-2 → MVP-5 → MVP-6 → MVP-7
MVP-3 → MVP-7
```

## Tracking

Create Gitea issues from MVP-1…MVP-7 with labels `mvp`, `decision/D*`. Link PRs to story ids.