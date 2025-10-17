import pandas as pd
from datetime import datetime

import importlib

main = importlib.import_module("main")


def test_determine_energy_column_for_mode_predicted():
    app = main.FilantropiaSolarApp()
    df = pd.DataFrame({"predicted_total_energy": [1, 2, 3]})
    col, label = app._determine_energy_column_for_mode(df, "simulation", {"used_simulation": True})
    assert col == "predicted_total_energy"
    assert label == "PREDICTED"


def test_get_day_hourly_matches_date():
    app = main.FilantropiaSolarApp()
    idx = pd.date_range("2024-01-01", periods=24, freq="h")
    df = pd.DataFrame({"x": range(24)}, index=idx)
    day = datetime(2024, 1, 1)
    out = app._get_day_hourly(df, day)
    assert len(out) == 24