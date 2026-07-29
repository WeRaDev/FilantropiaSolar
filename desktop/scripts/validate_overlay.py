from __future__ import annotations

from pathlib import Path
import sys

# Use non-interactive backend for matplotlib
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import FilantropiaSolarApp
from src.data_processing.comprehensive_data_processor import ComprehensiveDataProcessor
from src.prediction.enhanced_energy_predictor import EnhancedEnergyPredictor
from src.weather_simulation.weather_simulator import WeatherSimulator


def main() -> int:
    print("[VALIDATE] Starting overlay validation (headless)...")

    # Core pipeline
    dp = ComprehensiveDataProcessor()
    ws = WeatherSimulator("weather_files")
    predictor = EnhancedEnergyPredictor(dp, ws)

    installs = dp.get_installation_list()
    if not installs:
        print("[VALIDATE] No installations available")
        return 1

    inst_id, _info = installs[0]
    data = dp.get_combined_data(inst_id)
    if data is None or data.empty:
        print("[VALIDATE] No combined data for installation")
        return 1

    center_date = pd.to_datetime(data.index.max()).normalize().to_pydatetime()
    results = predictor.predict_15day_period(inst_id, center_date, False)

    hourly = results["hourly_data"]
    daily = results["daily_summary"]
    target_date = daily.index[len(daily) // 2]

    # Instantiate app and load baseline
    app = FilantropiaSolarApp()
    app._load_validation_baseline()
    if app.validation_baseline_df is None or app.validation_baseline_df.empty:
        print("[VALIDATE] Baseline CSV not found or empty; overlay will be skipped")
    else:
        print(
            f"[VALIDATE] Baseline loaded with columns: {list(app.validation_baseline_df.columns)}"
        )

    # Prepare Matplotlib axes without Tk
    fig = plt.figure(figsize=(10, 4), dpi=100)
    app.hourly_energy_ax = fig.add_subplot(111)

    # Compute productive hour window
    min_h, max_h = app._calculate_dynamic_productive_hours(hourly)

    # Slice current day
    try:
        current_day_hourly = hourly[
            hourly.index.date
            == (target_date.date() if hasattr(target_date, "date") else target_date)
        ]
    except Exception:
        current_day_hourly = hourly[hourly.index == target_date]

    # Create chart (will render baseline if available)
    app._create_hourly_energy_chart(
        current_day_hourly,
        target_date,
        productive_hour_min=min_h,
        productive_hour_max=max_h,
        energy_column="predicted_total_energy",
    )

    out_path = ROOT / "baseline_overlay_test.png"
    fig.savefig(out_path, bbox_inches="tight")
    print(f"[VALIDATE] Saved overlay chart: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
