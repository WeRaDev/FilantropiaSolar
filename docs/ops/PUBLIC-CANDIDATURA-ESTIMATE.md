# Ops: Public candidatura estimate and form UX

**NC app:** 3.2.36+  
**Odoo module:** 19.0.2.34.0+  
**ML service:** self-consumption constants in `ml-service/main.py`

## Savings formula (on-grid)

```
annual_savings_eur = annual_production_kwh × grid_price_eur_kwh × self_consumption_factor
```

| Grid | Factor | Rationale |
|------|--------|-----------|
| on_grid (default) | **0.4** | Prosumers consume ~40% of generation on average; rest exported |
| off_grid | **1.0** | All generation offsets local load |

Applied in three places so UI / API / CRM stay aligned:

1. **ML** `POST /estimate` — `SELF_CONSUMPTION_FACTOR_ON_GRID = 0.4`
2. **NC** public estimate proxy — rewrites `annual_savings_eur` + exposes `self_consumption_factor` / `grid_connection_type`
3. **Odoo** `_normalize_estimate()` and homepage KPI fallback

UI copy on step 2: “Estimativa indicativa (on-grid: ~40% autoconsumo)”.

Default display price remains **0.15 EUR/kWh** unless the visitor supplies a bill-based price.

## Double-submit / latency

Candidatura final step can take ~0.7–2s (ML estimate + CRM create). Mitigations:

| Layer | Behaviour |
|-------|-----------|
| JS (`pages.xml`) | One-shot submit on step 1–3 + `/contacto/enviar`: disable buttons, label “A processar…”, ignore further submits |
| Odoo render | `light_public_data=True` on candidatura steps — skip full stations + dashboard fetch |
| Odoo enviar | Reuse estimate already computed on step 2 when present (no second ML round-trip) |

## CRM pipeline assignment

Website-created leads must appear in **My Pipeline**.

- Module ≥ **19.0.2.33.0**: `_crm_lead_pipeline_defaults()` sets `user_id` / `team_id` from the same defaults as NC station import (admin + sales team).
- Before that fix, leads landed on inactive user **public** (`user_id=3`) and were invisible in sales views.
- One-time repair on TRL5: reassign those leads to admin if any remain.

## Virtual station stats (NC)

Public dashboard KPIs (**Total stations**, **total kWp**, **total energy**, **total savings**) must **exclude** `lifecycle_state=virtual`.

- API: `findPublicStatsStations` (planned + running + archived only).
- Pinia header KPIs follow the same filter.
- Virtual stations remain CRM/ops tooling only until promoted.

## NC Admin URL (Odoo dashboard)

Default origin for the Filantropia **NC Admin** link:

```text
https://wera-ss-pt-tv-1.wera.global
```

Set via `FS_NC_ADMIN_URL` in `docker-compose.trl5.yml` / `trl5-ensure-stack.sh`.  
`nc_admin_url()` appends `/apps/filantropia_solar/`.

Do not use the Tailscale Magicsock hostname for the dashboard link (public Cloudflare host is preferred).

## Smoke

1. `/candidatura` step 2 savings ≈ 40% of (production × 0.15) for on-grid.  
2. Rapid double-click on Enviar → only one request; button shows “A processar…”.  
3. New lead visible under admin My Pipeline with `user_id` ≠ public.  
4. CRM **Sync Virtual to NC** with lat/lng `0.0` → HTTP 201 (not 500).  
5. Odoo Filantropia dashboard **NC Admin** opens `https://wera-ss-pt-tv-1.wera.global/apps/filantropia_solar/`.  
6. NC public `/dashboard` `station_count` excludes virtuals.

## Related

- `docs/ops/CRM-NC-LIFECYCLE-MIRROR.md`  
- `docs/ops/TRL5-NC-ACCESS.md`  
- `docs/ops/PUBLIC-ARCHIVED-LIFECYCLE.md`  
- `nextcloud-app/CHANGELOG.md` (3.2.36)
