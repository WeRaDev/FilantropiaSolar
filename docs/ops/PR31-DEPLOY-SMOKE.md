# PR #31 — local deploy smoke (analytics + ML)

**App version:** 3.2.26  
**Branch:** `feat/analytics-nc-historical-hourly-status` → **merged to `main`** (`ad444b7`, 2026-08-14)  
**Status:** Closed with MVP-7 automated re-run; remaining work is operator CRM + TRL5 sign-off in `docs/mvp/MVP-7-GATES-TRL5.md`.

## Automated / CLI

```bash
# Stack
docker ps --format '{{.Names}} {{.Status}}' | grep filantropia

# NC
docker exec -u 33 filantropia-nextcloud php occ status
docker exec filantropia-nextcloud cat /var/www/html/custom_apps/filantropia_solar/appinfo/info.xml | grep version
# expect: installed, needsDbUpgrade false, version 3.2.26

# ML
curl -sS http://127.0.0.1:8501/health
python3 nextcloud-app/scripts/verify-ml-production.py --json /tmp/ml-acc.json
# expect: exit 0, PASS

# Frontend unit
cd nextcloud-app && npm test

# Series roll-forward interval (list has no interval column)
docker exec -u 33 filantropia-nextcloud php occ background-job:list \
  -c 'OCA\FilantropiaSolar\BackgroundJob\SeriesRollForwardJob'
docker exec -u 33 filantropia-nextcloud php occ background-job:execute --force-execute <id> -vvv
# expect Type: timed; Next execution = Last executed + 1h
```

## UI smoke (hard-refresh browser)

| Step | Expect |
|------|--------|
| Open FilantropiaSolar app | Map + list load |
| Open **WeRa Global** analysis | Modal opens (no blank crash) |
| Historical + Day | Hourly chart; badge SIMULATED or MIXED; hours 0–23 Lisbon |
| View data | Overlay table with rows |
| Toggle **Predicted** | Loading then chart; badge **SIMULATED**; totals ~6 kWh/kWp clear summer day |
| Generate analysis (if no-data) | Produces chart; errors surface in panel if fail |
| Add historical data | Upload modal **above** Analysis; black text on white |
| Export | Computer download and/or Nextcloud Files path |
| Edit location on map | Pin icon visible |
| Dataset station (e.g. Lisbon) Historical | NC series / dataset path still works |

## Sign-off

| Check | Pass | Initials | Date |
|-------|------|----------|------|
| occ 3.2.26 / no maintenance | eng | — | 2026-08-14 |
| ML health + verifier PASS | eng | — | 2026-08-14 |
| CI + Revisor on tip | eng | — | 2026-08-14 |
| Historical chart | | | |
| Predicted chart (ops station) | | | |
| View data | | | |
| Upload modal stacking/font | | | |

## Related

- `docs/ops/ML-PRODUCTION-ACCURACY.md`  
- `docs/mvp/MVP-7-GATES-TRL5.md`  
- Gitea PR: `/wera-global/FilantropiaSolar/pulls/31` (merged)
