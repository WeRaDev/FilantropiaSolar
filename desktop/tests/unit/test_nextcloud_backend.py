"""Tests for the Nextcloud server backend (API-client mode).

HTTP is fully mocked: no server is required to run these tests.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.nextcloud_backend import (
    NextcloudBackend,
    NextcloudBackendError,
    _adapt_period_response,
)


def _make_backend(session_mock) -> NextcloudBackend:
    with patch("src.nextcloud_backend.requests.Session", return_value=session_mock):
        return NextcloudBackend("http://nc.test/", "user", "pass")


def test_from_environment_requires_server_url(monkeypatch):
    monkeypatch.delenv("FS_SERVER_URL", raising=False)
    with pytest.raises(NextcloudBackendError, match="FS_SERVER_URL"):
        NextcloudBackend.from_environment()


def test_from_environment_reads_env(monkeypatch):
    monkeypatch.setenv("FS_SERVER_URL", "http://nc.test/")
    monkeypatch.setenv("FS_SERVER_USER", "u")
    monkeypatch.setenv("FS_SERVER_PASSWORD", "p")
    backend = NextcloudBackend.from_environment()
    assert backend.server_url == "http://nc.test"


def test_get_installation_list_maps_payload():
    session = MagicMock()
    response = MagicMock()
    response.json.return_value = {
        "installations": [
            {
                "id": "Lisbon_84071567",
                "serial_number": "84071567",
                "location": "Lisbon",
                "latitude": 38.7223,
                "longitude": -9.1393,
                "capacity_kwp": 46.0,
                "connection_power_kwn": 40.0,
                "from_date": "2019-01-01T00:00:00+00:00",
                "to_date": "2022-12-31T00:00:00+00:00",
            },
        ],
    }
    session.get.return_value = response

    backend = _make_backend(session)
    result = backend.get_installation_list()

    assert session.auth == ("user", "pass")
    session.get.assert_called_once_with(
        "http://nc.test/apps/filantropia_solar/api/v1/installations",
        timeout=120,
    )
    inst_id, info = result[0]
    assert inst_id == "Lisbon_84071567"
    assert info.location == "Lisbon"
    assert info.serial_number == "84071567"
    assert info.installed_power_kwp == 46.0
    assert info.latitude == pytest.approx(38.7223)


def test_predict_15day_period_posts_and_adapts():
    session = MagicMock()
    response = MagicMock()
    response.json.return_value = {
        "success": True,
        "installation_info": {
            "id": "Lisbon_84071567",
            "location": "Lisbon",
            "capacity_kwp": 46.0,
        },
        "period_statistics": {
            "total_energy_kwh": 100.0,
            "avg_daily_kwh": 4.76,
            "total_savings_eur": 15.0,
            "analysis_days": 21,
            "start_date": "2024-06-01",
            "end_date": "2024-06-21",
            "center_date": "2024-06-11",
        },
        "daily_data": [
            {
                "date": "2024-06-11",
                "total_production_kwh": 5.0,
                "specific_energy_kwh_kwp": 0.11,
                "avg_production_kwh": 0.21,
                "peak_hour": 12,
                "peak_production_kwh": 1.0,
                "rank": 4,
                "avg_temperature": 25.0,
                "avg_humidity": 50.0,
                "avg_cloud_cover": 20.0,
                "avg_wind_speed": 5.0,
                "avg_radiation": 800.0,
            },
        ],
        "hourly_data": [
            {
                "timestamp": "2024-06-11T10:00:00+00:00",
                "hour": 10,
                "production_kwh": 0.5,
                "specific_energy": 0.011,
                "rank": 3,
                "temperature": 24.0,
                "humidity": 55.0,
                "cloud_cover": 25.0,
                "wind_speed": 4.0,
                "radiation": 750.0,
            },
        ],
        "weather_source": "measured",
        "model_info": {"name": "Physics-based Estimation", "feature_count": 5},
    }
    session.post.return_value = response

    backend = _make_backend(session)
    result = backend.predict_15day_period("Lisbon_84071567", "2024-06-11", False)

    body = session.post.call_args.kwargs["json"]
    assert body["mode"] == "historical"
    assert body["installation_id"] == "Lisbon_84071567"
    assert body["center_date"] == "2024-06-11"
    assert body["days"] == 21

    hourly = result["hourly_data"]
    assert isinstance(hourly, pd.DataFrame)
    assert hourly.index.name == "timestamp"
    assert hourly["predicted_total_energy"].iloc[0] == 0.5
    assert hourly["temperature_2m"].iloc[0] == 24.0
    # historical + measured surfaces the Produced Energy column
    assert "Produced Energy (kWh)" in hourly.columns

    daily = result["daily_summary"]
    assert daily["predicted_total_energy"].iloc[0] == 5.0
    assert daily["ranking"].iloc[0] == 4

    assert result["period_statistics"]["total_energy_kwh"] == 100.0
    assert result["data_source"]["weather_source"] == "measured"


def test_predict_period_raises_on_server_error():
    session = MagicMock()
    response = MagicMock()
    response.json.return_value = {
        "success": False,
        "error": "Installation not found: nope",
        "installation_info": {},
        "period_statistics": {},
        "daily_data": [],
        "hourly_data": [],
    }
    session.post.return_value = response

    backend = _make_backend(session)
    with pytest.raises(NextcloudBackendError, match="Installation not found"):
        backend.predict_15day_period("nope", "2024-06-11", False)


def test_adapt_simulated_marks_weather_flag():
    payload = {
        "success": True,
        "weather_source": "synthetic",
        "hourly_data": [
            {
                "timestamp": "2024-06-11T10:00:00+00:00",
                "production_kwh": 0.5,
                "specific_energy": 0.011,
                "rank": 3,
                "temperature": 24.0,
                "humidity": 55.0,
                "cloud_cover": 25.0,
                "wind_speed": 4.0,
                "radiation": 750.0,
            },
        ],
        "daily_data": [],
        "period_statistics": {},
        "installation_info": {},
        "model_info": {},
    }
    result = _adapt_period_response(payload, use_simulation=True)
    assert bool(result["hourly_data"]["is_simulated_weather"].iloc[0])
