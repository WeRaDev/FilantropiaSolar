#!/usr/bin/env python3
"""Verify ML energy production scale (physics + optional PVGIS monthly mean).

Usage:
  python3 nextcloud-app/scripts/verify-ml-production.py
  ML_BASE=http://127.0.0.1:8501 python3 nextcloud-app/scripts/verify-ml-production.py --day 2026-08-12
  python3 nextcloud-app/scripts/verify-ml-production.py --skip-pvgis --json /tmp/out.json

Exit codes:
  0 PASS / PASS WITH NOTES
  1 REVIEW (flags or bias outside band)
  2 transport/API failure
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any

DEFAULT_STATIONS: list[dict[str, Any]] = [
    {"id": "1", "name": "Lisbon 46kWp", "lat": 38.728, "lon": -9.138, "kwp": 46.0, "loc": "Lisbon"},
    {"id": "3", "name": "Setubal 23.5kWp", "lat": 38.577, "lon": -8.872, "kwp": 23.52, "loc": "Setubal"},
    {"id": "5", "name": "Faro 7kWp", "lat": 37.031, "lon": -7.893, "kwp": 7.0, "loc": "Faro"},
    {"id": "6", "name": "Braga 65kWp", "lat": 41.493, "lon": -8.496, "kwp": 64.93, "loc": "Braga"},
    {"id": "14", "name": "WeRa Global 1.2kWp", "lat": 39.0855, "lon": -9.1791, "kwp": 1.2, "loc": "Lisbon"},
    {"id": "15", "name": "Vazinha 0.54kWp", "lat": 39.2369, "lon": -8.685, "kwp": 0.54, "loc": "Lisbon"},
    {"id": "16", "name": "ARIA 4.5kWp", "lat": 38.7336, "lon": -9.3014, "kwp": 4.5, "loc": "Lisbon"},
]


def post_json(url: str, body: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def get_json(url: str, timeout: float = 30.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def ml_sim(base: str, st: dict[str, Any], day: str) -> dict[str, Any]:
    return post_json(
        f"{base.rstrip('/')}/simulate/hourly",
        {
            "latitude": st["lat"],
            "longitude": st["lon"],
            "capacity_kwp": st["kwp"],
            "location": st.get("loc") or "Lisbon",
            "start": f"{day}T00:00:00Z",
            "end": f"{day}T23:00:00Z",
        },
    )


def ml_period(base: str, st: dict[str, Any], day: str) -> dict[str, Any]:
    return post_json(
        f"{base.rstrip('/')}/predict/period",
        {
            "mode": "simulated",
            "installation_id": str(st["id"]),
            "center_date": day,
            "days": 1,
            "location": st.get("loc") or "Lisbon",
            "capacity_kwp": st["kwp"],
            "latitude": st["lat"],
            "longitude": st["lon"],
        },
    )


def pvgis_aug_mean_daily(st: dict[str, Any]) -> float | None:
    params = {
        "lat": st["lat"],
        "lon": st["lon"],
        "peakpower": st["kwp"],
        "pvtechchoice": "crystSi",
        "mountingplace": "free",
        "loss": 14,
        "angle": 35,
        "aspect": 0,
        "outputformat": "json",
        "browser": 0,
    }
    url = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=90) as resp:
        data = json.loads(resp.read().decode())
    fixed = (((data.get("outputs") or {}).get("monthly") or {}).get("fixed")) or []
    aug = next((m for m in fixed if int(m.get("month", 0)) == 8), None)
    if not aug:
        return None
    return float(aug.get("E_m") or 0) / 31.0


def row_hour(h: dict[str, Any]) -> int | None:
    if h.get("hour") is not None and h.get("hour") != "":
        try:
            return int(h["hour"])
        except (TypeError, ValueError):
            pass
    ts = str(h.get("timestamp") or "")
    m = re.search(r"T(\d{1,2})", ts) or re.search(r"\s(\d{2}):", ts)
    return int(m.group(1)) if m else None


def summarize_hours(hours: list[dict[str, Any]], kwp: float) -> dict[str, Any] | None:
    if not hours:
        return None
    prods = [float(h.get("production_kwh") or 0) for h in hours]
    rads: list[float] = []
    for h in hours:
        for key in ("solar_radiation_wm2", "shortwave_radiation", "radiation"):
            if h.get(key) is not None:
                rads.append(float(h[key]))
                break
    total = sum(prods)
    peak = max(prods) if prods else 0.0
    night_nonzero = 0
    for h, p in zip(hours, prods, strict=False):
        hr = row_hour(h)
        if hr is not None and (hr < 5 or hr > 21) and p > 0.01:
            night_nonzero += 1
    return {
        "n": len(hours),
        "sum_kwh": round(total, 3),
        "kwh_kwp": round(total / kwp, 3) if kwp else None,
        "peak_kwh": round(peak, 3),
        "peak_over_kwp": round(peak / kwp, 3) if kwp else None,
        "max_rad": round(max(rads), 1) if rads else None,
        "night_nonzero_hours": night_nonzero,
    }


def flags_for(sh: dict[str, Any] | None, kwp: float, day: str, ml_vs_pvgis: float | None) -> list[str]:
    flags: list[str] = []
    if not sh:
        flags.append("no_hourly_data")
        return flags
    if sh.get("peak_over_kwp") is not None and float(sh["peak_over_kwp"]) > 1.05:
        flags.append(f"peak_over_capacity:{sh['peak_over_kwp']}")
    kwh_kwp = sh.get("kwh_kwp")
    if kwh_kwp is not None:
        if float(kwh_kwp) > 8.5:
            flags.append(f"kwh_kwp_very_high:{kwh_kwp}")
        if float(kwh_kwp) < 1.5 and day[5:7] in {"06", "07", "08"}:
            flags.append(f"kwh_kwp_low_for_summer:{kwh_kwp}")
    if sh.get("night_nonzero_hours"):
        flags.append(f"night_production:{sh['night_nonzero_hours']}")
    if ml_vs_pvgis is not None:
        if ml_vs_pvgis > 1.35:
            flags.append(f"ml_gt_pvgis:{ml_vs_pvgis}")
        elif ml_vs_pvgis < 0.65:
            flags.append(f"ml_lt_pvgis:{ml_vs_pvgis}")
    return flags


def run(args: argparse.Namespace) -> int:
    base = args.ml_base or os.environ.get("ML_BASE", "http://127.0.0.1:8501")
    day = args.day or (date.today() - timedelta(days=1)).isoformat()
    stations = DEFAULT_STATIONS

    try:
        health = get_json(f"{base.rstrip('/')}/health")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: ML health unreachable at {base}: {exc}", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    ratios: list[float] = []
    flag_count = 0

    print(f"ML base={base} day={day} health={health.get('status')} models={health.get('models_loaded')}")
    print("=" * 96)

    for st in stations:
        row: dict[str, Any] = {
            "station": st["name"],
            "id": st["id"],
            "kwp": st["kwp"],
            "day": day,
        }
        pvg = None
        if not args.skip_pvgis:
            try:
                pvg = pvgis_aug_mean_daily(st)
            except Exception as exc:  # noqa: BLE001
                row["pvgis_error"] = str(exc)
        row["pvgis_aug_mean_daily_kwh"] = round(pvg, 3) if pvg is not None else None
        row["pvgis_aug_kwh_kwp"] = round(pvg / st["kwp"], 3) if pvg and st["kwp"] else None

        try:
            sim = ml_sim(base, st, day)
            sh = summarize_hours(sim.get("hours") or [], float(st["kwp"]))
            row["simulate_success"] = sim.get("success")
            row["simulate_weather_source"] = sim.get("weather_source")
            row["simulate_hourly"] = sh
        except Exception as exc:  # noqa: BLE001
            row["simulate_hourly"] = None
            row["simulate_error"] = str(exc)
            sh = None

        try:
            per = ml_period(base, st, day)
            ph = summarize_hours(per.get("hourly_data") or [], float(st["kwp"]))
            row["predict_success"] = per.get("success")
            row["predict_error"] = per.get("error")
            row["predict_period"] = ph
            if sh and ph and sh.get("sum_kwh") and ph.get("sum_kwh") is not None:
                row["period_vs_sim_ratio"] = round(float(ph["sum_kwh"]) / float(sh["sum_kwh"]), 3)
        except Exception as exc:  # noqa: BLE001
            row["predict_period"] = None
            row["predict_error"] = str(exc)

        ml_vs = None
        if pvg and sh and sh.get("sum_kwh"):
            ml_vs = round(float(sh["sum_kwh"]) / pvg, 3)
            ratios.append(ml_vs)
        row["ml_vs_pvgis_aug_mean"] = ml_vs
        row["flags"] = flags_for(sh, float(st["kwp"]), day, ml_vs)
        flag_count += len(row["flags"])
        results.append(row)

        print(
            f"{st['name']:28} ML={None if not sh else sh.get('sum_kwh')} kWh "
            f"({None if not sh else sh.get('kwh_kwp')} kWh/kWp) "
            f"peak/kwp={None if not sh else sh.get('peak_over_kwp')} "
            f"PVGIS~{row['pvgis_aug_mean_daily_kwh']} ratio={ml_vs} "
            f"period/sim={row.get('period_vs_sim_ratio')} flags={row['flags']}"
        )

    # Capacity linearity at WeRa coords
    lin_ratio = None
    try:
        base_st = {"lat": 39.0855, "lon": -9.1791, "loc": "Lisbon"}
        s1 = ml_sim(base, {**base_st, "kwp": 1.2, "id": "lin-a"}, day)
        s2 = ml_sim(base, {**base_st, "kwp": 12.0, "id": "lin-b"}, day)
        sum1 = sum(float(h.get("production_kwh") or 0) for h in (s1.get("hours") or []))
        sum2 = sum(float(h.get("production_kwh") or 0) for h in (s2.get("hours") or []))
        lin_ratio = round(sum2 / sum1, 3) if sum1 else None
        print(f"linearity 12/1.2 = {lin_ratio} (expect ~10.0)")
    except Exception as exc:  # noqa: BLE001
        print(f"linearity check failed: {exc}", file=sys.stderr)

    lin_ok = lin_ratio is not None and 9.5 <= lin_ratio <= 10.5
    mean_ratio = round(sum(ratios) / len(ratios), 3) if ratios else None
    period_ok = all(
        (r.get("period_vs_sim_ratio") is None)
        or (0.95 <= float(r["period_vs_sim_ratio"]) <= 1.05)
        for r in results
    )
    peaks_ok = all(
        (r.get("simulate_hourly") or {}).get("peak_over_kwp") is None
        or float((r.get("simulate_hourly") or {}).get("peak_over_kwp") or 0) <= 1.05
        for r in results
    )

    if args.skip_pvgis:
        # Physics-only gate (no external JRC dependency)
        if flag_count == 0 and lin_ok and period_ok and peaks_ok:
            verdict = "PASS — physics bounds and capacity linearity OK (PVGIS skipped)"
            code = 0
        elif flag_count <= 2 and lin_ok and peaks_ok:
            verdict = "PASS WITH NOTES — physics mostly OK (PVGIS skipped)"
            code = 0
        else:
            verdict = "REVIEW — physics flags outside expected band (PVGIS skipped)"
            code = 1
    elif flag_count == 0 and lin_ok and mean_ratio is not None and 0.85 <= mean_ratio <= 1.25:
        verdict = "PASS — production scale consistent with PVGIS August means and physics bounds"
        code = 0
    elif flag_count <= 2 and lin_ok and mean_ratio is not None and 0.75 <= mean_ratio <= 1.35:
        verdict = "PASS WITH NOTES — reasonable; minor flags or clear-day bias vs monthly mean"
        code = 0
    else:
        verdict = "REVIEW — flags or bias outside expected band"
        code = 1

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ml_base": base,
        "day": day,
        "ml_health": health,
        "method": {
            "ml_endpoints": ["POST /simulate/hourly", "POST /predict/period mode=simulated"],
            "pvgis": None
            if args.skip_pvgis
            else "JRC PVcalc v5_2 monthly August E_m/31, tilt=35 aspect=0 loss=14%",
            "physics_checks": [
                "peak_hour <= ~1.05*capacity",
                "kWh/kWp band",
                "night zeros",
                "capacity linearity",
                "predict_period vs simulate_hourly",
            ],
        },
        "results": results,
        "summary": {
            "stations": len(results),
            "flag_count": flag_count,
            "ml_vs_pvgis_ratios": ratios,
            "mean_ml_vs_pvgis": mean_ratio,
            "capacity_linearity_ok": lin_ok,
            "linearity_ratio_12_over_1_2": lin_ratio,
        },
        "verdict": verdict,
    }

    if args.json:
        path = args.json
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
        print(f"wrote {path}")

    print("=" * 96)
    print("VERDICT:", verdict)
    print(
        "mean ML/PVGIS:",
        mean_ratio,
        "flags:",
        flag_count,
        "linearity_ok:",
        lin_ok,
    )
    return code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ml-base", default=None, help="ML service base URL (default ML_BASE or :8501)")
    parser.add_argument("--day", default=None, help="UTC day YYYY-MM-DD (default yesterday)")
    parser.add_argument("--skip-pvgis", action="store_true", help="Skip external PVGIS calls")
    parser.add_argument("--json", default=None, help="Write full JSON report path")
    args = parser.parse_args()
    try:
        raise SystemExit(run(args))
    except urllib.error.URLError as exc:
        print(f"FAIL: network error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
