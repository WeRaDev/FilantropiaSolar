from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_processing.comprehensive_data_processor import ComprehensiveDataProcessor
from src.weather_simulation.weather_simulator import WeatherSimulator
from src.prediction.enhanced_energy_predictor import EnhancedEnergyPredictor
from src.prediction.weather_ranking_system import WeatherRankingSystem


def main() -> int:
    print("[SMOKE] FilantropiaSolar headless run starting...")

    dp = ComprehensiveDataProcessor()
    ws = WeatherSimulator("weather_files")
    predictor = EnhancedEnergyPredictor(dp, ws)
    wrs = WeatherRankingSystem(predictor, dp)

    installs = dp.get_installation_list()
    if not installs:
        print("[SMOKE] No installations found")
        return 1

    inst_id, info = installs[0]
    print(f"[SMOKE] Using installation: {info.location}_{info.serial_number} ({info.installed_power_kwp} kWp)")

    data = dp.get_combined_data(inst_id)
    if data is None or data.empty:
        print("[SMOKE] No combined data found; aborting")
        return 1

    center_date = pd.to_datetime(data.index.max()).to_pydatetime()
    center_date = center_date.replace(hour=0, minute=0, second=0, microsecond=0)
    print(f"[SMOKE] Center date: {center_date.date()}")

    results = predictor.predict_15day_period(inst_id, center_date, False)

    period = results.get("prediction_period", {})
    stats = results.get("period_statistics", {})
    source = results.get("data_source", {})

    print("[SMOKE] Period:", period)
    print("[SMOKE] Stats: total_kwh=", stats.get("total_energy_kwh"), "avg_specific=", stats.get("average_specific_energy"))
    print("[SMOKE] Data source:", source)

    hourly = results.get("hourly_data")
    daily = results.get("daily_summary")

    if isinstance(hourly, pd.DataFrame):
        print(f"[SMOKE] Hourly rows: {len(hourly)}, cols: {list(hourly.columns)[:10]}...")
        # Night radiation sanity: hours <6 or >20 must be zero
        if "shortwave_radiation" in hourly.columns:
            night = hourly[(hourly.index.hour < 6) | (hourly.index.hour > 20)]["shortwave_radiation"]
            night_max = float(pd.to_numeric(night, errors="coerce").fillna(0).max()) if len(night) else 0.0
            print(f"[SMOKE] Night radiation max: {night_max}")
    if isinstance(daily, pd.DataFrame):
        print(f"[SMOKE] Daily rows: {len(daily)}")

    # Rank check on one day
    try:
        target_date = daily.index[len(daily)//2]
        try:
            target_key = target_date.date()
        except Exception:
            target_key = target_date
        daily_ranks = wrs.rank_daily_weather_conditions(hourly, [target_key])
        print("[SMOKE] Daily weather rank for center day:", daily_ranks.get(target_key))
    except Exception as e:
        print("[SMOKE] Weather ranking check failed:", e)

    print("[SMOKE] FilantropiaSolar headless run completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
