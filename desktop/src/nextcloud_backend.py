"""Nextcloud server backend for the desktop edition (API-client mode).

Replaces the legacy local data/ML pipeline with calls to the FilantropiaSolar
Nextcloud app running on a server. Exposes the subset of the legacy backend
surface that `main.py` consumes (installation listing, date ranges, period
predictions), converting server JSON into the DataFrame shapes the GUI
expects.

Authentication: HTTP Basic with a Nextcloud app password
(Settings -> Security -> App passwords). The app endpoints used here are
marked NoCSRFRequired server-side, so basic auth works for GET and POST.

Configuration is via environment variables (see desktop/README.md):
    FS_SERVER_URL       e.g. http://localhost:8080 (required)
    FS_SERVER_USER      Nextcloud username
    FS_SERVER_PASSWORD  Nextcloud app password
"""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd
import requests

from src.data_processing.comprehensive_data_processor import InstallationInfo

logger = logging.getLogger(__name__)

DEFAULT_ANALYSIS_DAYS = 21
MIN_PRODUCTION_KWH_FOR_SIMULATION_TAG = 0.0


class NextcloudBackendError(Exception):
    """Raised when the server rejects or fails a backend operation."""


class NextcloudBackend:
    """Drop-in backend exposing the legacy surface main.py expects.

    Used as data_processor, energy_predictor, and weather_simulator stand-in;
    the WeatherRankingSystem still runs locally on the returned data.
    """

    def __init__(
        self,
        server_url: str,
        username: str = "",
        app_password: str = "",
        timeout: int = 120,
    ):
        if not server_url:
            raise NextcloudBackendError(
                "FS_SERVER_URL is not set. Point it at your Nextcloud server "
                "(see desktop/README.md)."
            )
        self.server_url = server_url.rstrip("/")
        self._api = f"{self.server_url}/apps/filantropia_solar/api/v1"
        self._timeout = timeout
        self._session = requests.Session()
        if username or app_password:
            self._session.auth = (username, app_password)

    @classmethod
    def from_environment(cls) -> NextcloudBackend:
        """Build a backend from FS_SERVER_* environment variables."""
        return cls(
            server_url=os.environ.get("FS_SERVER_URL", ""),
            username=os.environ.get("FS_SERVER_USER", ""),
            app_password=os.environ.get("FS_SERVER_PASSWORD", ""),
        )

    # ------------------------------------------------------------------
    # data_processor surface
    # ------------------------------------------------------------------
    @property
    def cache_manager(self):
        """Server manages caching; the desktop keeps none."""
        return None

    def get_installation_list(self) -> list[tuple[str, InstallationInfo]]:
        """List installations from the server (merged dataset + user stations)."""
        payload = self._get("/installations")
        items = (
            payload.get("installations", []) if isinstance(payload, dict) else payload
        )
        result: list[tuple[str, InstallationInfo]] = []
        for item in items:
            info = self._to_installation_info(item)
            inst_id = str(item.get("id") or info.installation_id)
            result.append((inst_id, info))
        logger.info(f"Server returned {len(result)} installations")
        return result

    @property
    def installations(self) -> dict[str, InstallationInfo]:
        """Installations keyed by id (legacy attribute used by main.py)."""
        return dict(self.get_installation_list())

    def get_combined_data(self, installation_id: str) -> pd.DataFrame | None:
        """Date range for an installation, via the server stats endpoint.

        The server owns the actual time series; the GUI only needs the
        min/max dates here. Returns a two-row frame indexed [from, to].
        """
        try:
            stats = self._get(f"/installations/{installation_id}/stats")
            from_date = stats.get("from_date")
            to_date = stats.get("to_date")
            if from_date and to_date:
                idx = pd.to_datetime([from_date, to_date])
                return pd.DataFrame({"server_owned": [True, True]}, index=idx)
        except Exception as exc:
            logger.warning(f"Date-range lookup failed for {installation_id}: {exc}")
        return None

    # ------------------------------------------------------------------
    # energy_predictor surface
    # ------------------------------------------------------------------
    def get_available_installations(self) -> list[tuple[str, InstallationInfo]]:
        """Installations available for analysis (server-side models)."""
        return self.get_installation_list()

    def load_models(self):
        """No-op: models live on the server."""
        logger.debug("load_models() is a no-op in API-client mode")

    def predict_15day_period(
        self,
        installation_id: str,
        center_date,
        use_simulation: bool,
        days: int = DEFAULT_ANALYSIS_DAYS,
    ) -> dict[str, Any]:
        """21-day analysis for an installation via the server."""
        return self._predict_period(
            mode="simulated" if use_simulation else "historical",
            center_date=center_date,
            days=days,
            installation_id=installation_id,
        )

    def predict_period_for_custom(
        self,
        location: str,
        capacity_kwp: float,
        center_date,
        days: int = DEFAULT_ANALYSIS_DAYS,
    ) -> dict[str, Any]:
        """21-day analysis for a custom station via the server."""
        return self._predict_period(
            mode="custom",
            center_date=center_date,
            days=days,
            location=location,
            capacity_kwp=capacity_kwp,
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _get(self, path: str) -> Any:
        resp = self._session.get(f"{self._api}{path}", timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def _predict_period(
        self,
        *,
        mode: str,
        center_date,
        days: int,
        installation_id: str | None = None,
        location: str | None = None,
        capacity_kwp: float | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "mode": mode,
            "center_date": pd.Timestamp(center_date).strftime("%Y-%m-%d"),
            "days": days,
        }
        if installation_id is not None:
            body["installation_id"] = installation_id
        if location is not None:
            body["location"] = location
        if capacity_kwp is not None:
            body["capacity_kwp"] = capacity_kwp

        resp = self._session.post(
            f"{self._api}/predict/period",
            json=body,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success"):
            raise NextcloudBackendError(
                str(payload.get("error") or "server prediction failed")
            )
        return _adapt_period_response(payload, use_simulation=(mode != "historical"))

    @staticmethod
    def _to_installation_info(item: dict[str, Any]) -> InstallationInfo:
        serial = item.get("serial_number") or str(item.get("id", "")).split("_")[-1]
        return InstallationInfo(
            serial_number=str(serial),
            location=str(item.get("location", "Unknown")),
            latitude=float(item.get("latitude") or 0.0),
            longitude=float(item.get("longitude") or 0.0),
            installed_power_kwp=float(item.get("capacity_kwp") or 0.0),
            connection_power_kwn=float(item.get("connection_power_kwn") or 0.0),
            # Fall back to the dataset span when the server omits dates
            from_date=pd.to_datetime(item["from_date"])
            if item.get("from_date")
            else pd.Timestamp("2019-01-01"),
            to_date=pd.to_datetime(item["to_date"])
            if item.get("to_date")
            else pd.Timestamp.today().normalize(),
        )


def _adapt_period_response(
    payload: dict[str, Any],
    *,
    use_simulation: bool,
) -> dict[str, Any]:
    """Convert the server's PeriodPredictionResponse into the desktop's
    expected results dict (DataFrames with legacy column names)."""
    weather_source = payload.get("weather_source") or "synthetic"

    hourly_records = []
    for point in payload.get("hourly_data") or []:
        hourly_records.append(
            {
                "timestamp": point.get("timestamp"),
                "predicted_total_energy": point.get("production_kwh", 0.0),
                "predicted_specific_energy": point.get("specific_energy", 0.0),
                "weather_ranking": point.get("rank", 3),
                "temperature_2m": point.get("temperature"),
                "relative_humidity_2m": point.get("humidity"),
                "cloud_cover": point.get("cloud_cover"),
                "wind_speed_10m": point.get("wind_speed"),
                "shortwave_radiation": point.get("radiation"),
                "is_simulated_weather": weather_source == "synthetic",
            }
        )
    hourly_df = pd.DataFrame(hourly_records)
    if not hourly_df.empty:
        hourly_df["timestamp"] = pd.to_datetime(hourly_df["timestamp"])
        hourly_df = hourly_df.set_index("timestamp").sort_index()
        if not use_simulation and weather_source == "measured":
            hourly_df["Produced Energy (kWh)"] = hourly_df["predicted_total_energy"]

    daily_records = []
    for day in payload.get("daily_data") or []:
        daily_records.append(
            {
                "date": day.get("date"),
                "predicted_total_energy": day.get("total_production_kwh", 0.0),
                "ranking": day.get("rank", 3),
                "avg_production_kwh": day.get("avg_production_kwh", 0.0),
                "peak_hour": day.get("peak_hour"),
                "peak_production_kwh": day.get("peak_production_kwh", 0.0),
                "specific_energy": day.get("specific_energy_kwh_kwp", 0.0),
                "temperature_2m": day.get("avg_temperature"),
                "relative_humidity_2m": day.get("avg_humidity"),
                "cloud_cover": day.get("avg_cloud_cover"),
                "wind_speed_10m": day.get("avg_wind_speed"),
                "shortwave_radiation": day.get("avg_radiation"),
            }
        )
    daily_df = pd.DataFrame(daily_records)
    if not daily_df.empty:
        daily_df["date"] = pd.to_datetime(daily_df["date"])
        daily_df = daily_df.set_index("date").sort_index()

    stats = payload.get("period_statistics") or {}
    info = payload.get("installation_info") or {}
    model_info = payload.get("model_info") or {}

    return {
        "installation_id": info.get("id", ""),
        "installation_info": info,
        "prediction_period": {
            "start": stats.get("start_date"),
            "end": stats.get("end_date"),
            "center_date": stats.get("center_date"),
            "total_hours": len(hourly_df),
        },
        "hourly_data": hourly_df,
        "daily_summary": daily_df,
        "period_statistics": {
            "total_energy_kwh": stats.get("total_energy_kwh", 0.0),
            "average_specific_energy": (
                stats.get("total_energy_kwh", 0.0) / max(len(daily_df), 1)
            ),
            "avg_daily_kwh": stats.get("avg_daily_kwh", 0.0),
            "total_savings_eur": stats.get("total_savings_eur", 0.0),
            "analysis_days": stats.get("analysis_days", len(daily_df)),
        },
        "data_source": {
            "used_simulation": use_simulation,
            "model_used": model_info.get("name", "server"),
            "model_performance": {},
            "weather_source": weather_source,
        },
    }
