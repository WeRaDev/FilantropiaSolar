# Odoo website COW views (upgrade safety)

Website Builder creates **website-specific copies** (COW) of QWeb views.
On TRL5/prod those COWs **are** the published site (home page arch can be
200KB+ of builder markup). Module XML under
`filantropia_solar_public` is only the **baseline** for fresh installs.

## Policy (19.0.2.12.0+)

| Action | Behaviour |
|--------|-----------|
| `odoo -u filantropia_solar_public` | **Preserves** all website COWs for FS page/snippet keys |
| `post_init_hook` | Inventories COWs; does **not** unlink |
| Migration `19.0.2.11.0` | **No-op** (old delete withdrawn) |
| Migration `19.0.2.12.0` | Inventory only |

### Forced reset (opt-in, one-shot)

Only if a Website Builder override is known-broken and you intentionally
want module XML again:

```bash
# Odoo shell
env['ir.config_parameter'].sudo().set_param(
    'filantropia_solar_public.reset_website_cows', '1')
# then
odoo -d filantropia_public -u filantropia_solar_public --stop-after-init
# param is cleared to 0 automatically after one run
```

**Never** set this on TRL5/prod without a DB backup and a content restore plan.

## Keys watched

- `filantropia_solar_public.page_inicio`
- `filantropia_solar_public.page_instalacoes`
- `filantropia_solar_public.page_contacto`
- `filantropia_solar_public.page_candidatura`
- `filantropia_solar_public.snippet_leaflet_map`
- `filantropia_solar_public.snippet_steps`

Header/footer theme templates (`website.template_header_*`,
`website.footer_*`) are separate; enable via `theme.utils.enable_view`,
do not mass-delete.

## Before shipping to TRL5

1. **Backup** published website (or full DB):

```bash
bash nextcloud-app/scripts/backup-odoo-website.sh
# on TRL5 (recommended full DB):
TRL5_HOST=root@100.82.252.18 bash nextcloud-app/scripts/backup-odoo-website.sh --remote --full-db
```

2. Deploy addon code; run `-u filantropia_solar_public` (or compose recreate + update).

3. **Verify** COW still present and large:

```sql
SELECT key, website_id, active, length(arch_db::text)
FROM ir_ui_view
WHERE key = 'filantropia_solar_public.page_inicio'
ORDER BY website_id NULLS FIRST;
```

Expect a website-specific row with arch length much larger than the module
baseline (~15-20KB). TRL5 published home has historically been ~200KB+.

4. Smoke: `/inicio`, `/en/inicio`, header menus, map, candidatura, CRM login.

## Editing content

- **Visual / marketing pages** (home, branding): Website Builder is OK; COWs are preserved.
- **Station list/map data binding** (dynamic NC stations): prefer module XML + static JS
  (`stations_map.js`) so logic is not frozen in a stale COW. If a COW blocks a code fix,
  use the opt-in reset **after** backup, or surgically edit that COW only.

## History

- **19.0.2.11.0**: introduced automatic COW delete on upgrade (to fix broken map links).
  Unsafe for TRL5 published site.
- **19.0.2.12.0**: delete removed; preserve-by-default + opt-in flag.

## Map / station list fixes (PR #29)

Published COWs may:

1. Drop `fs-station-list-item` / `data-station-id|lat|lng` (list not clickable).
2. Embed a **serialized Leaflet DOM** inside `#fs-stations-map` (map init fails or
   focus/center broken).

Module baseline (`page_inicio` without `website_id`) and `stations_map.js?v=*` hold
the correct markup/logic. After deploy:

1. Confirm `/inicio` HTML contains `fs-station-list-item`, `stations_map.js?v=`, and
   an **empty** `#fs-stations-map` host (no `leaflet-container` in arch).
2. If COW is stale, either surgically replace the station list + map host from the
   module baseline, or opt-in `reset_website_cows` after backup.
3. Clear `web.assets_frontend` attachments if CSS badges/pins look missing.
4. Hard-refresh the browser (script is cache-busted via `?v=` query).

Expected UX: list click or marker click **centers** the station in the map box,
opens popup with Planeada/Em operação badge, markers are lifecycle-colored.

