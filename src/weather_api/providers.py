"""
Weather providers abstraction and Open-Meteo integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Protocol

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class WeatherProvider(Protocol):
    def get_hourly_weather(
        self,
        *,
        latitude: float,
        longitude: float,
        start: datetime,
        end: datetime,
        prefer_historical: bool = True,
    ) -> pd.DataFrame | None:
        """Return hourly weather DataFrame indexed by datetime with required columns.

        Expected columns: temperature_2m, relative_humidity_2m, cloud_cover,
        wind_speed_10m, shortwave_radiation
        """
        ...


@dataclass
class OpenMeteoWeatherProvider:
    cache_manager: Any | None = None  # DataCacheManager-like
    session: requests.Session | None = None
    timeout: int = 20
    max_retries: int = 3

    BASE_FORECAST: str = "https://api.open-meteo.com/v1/forecast"
    BASE_ARCHIVE: str = "https://archive-api.open-meteo.com/v1/archive"

    def _cache_id(
        self, lat: float, lon: float, start: datetime, end: datetime, source: str
    ) -> str:
        return f"openmeteo_{source}_{lat:.4f}_{lon:.4f}_{start.strftime('%Y%m%d%H')}_{end.strftime('%Y%m%d%H')}"

    def _get_session(self) -> requests.Session:
        if self.session:
            return self.session
        s = requests.Session()
        retry = Retry(
            total=self.max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        return s

    def _request(self, url: str, params: dict) -> dict | None:
        s = self._get_session()
        try:
            resp = s.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:  # noqa: PLR2004
                return resp.json()
            logger.warning(f"Open-Meteo HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Open-Meteo request failed: {e}")
        return None

    def _normalize(self, payload: dict) -> pd.DataFrame | None:
        try:
            hourly = payload.get("hourly") or {}
            times = hourly.get("time")
            if not times:
                return None
            df = pd.DataFrame(hourly)
            df["datetime"] = pd.to_datetime(
                df["time"]
            )  # timezone already applied by API
            df = df.set_index("datetime").drop(columns=["time"])  # type: ignore[arg-type]

            # Rename to internal schema if needed
            rename_map: dict[str, str] = {
                # Open-Meteo already uses these names for requested variables
            }
            df = df.rename(columns=rename_map)

            # Ensure required columns exist
            required = [
                "temperature_2m",
                "relative_humidity_2m",
                "cloud_cover",
                "wind_speed_10m",
                "shortwave_radiation",
            ]
            for col in required:
                if col not in df.columns:
                    df[col] = pd.NA

            # Sort and drop duplicates
            df = df[required].sort_index()

            # Reindex to complete hourly coverage
            full_index = pd.date_range(df.index.min(), df.index.max(), freq="h")
            df = df.reindex(full_index)
            return df
        except Exception as e:
            logger.error(f"Error normalizing Open-Meteo payload: {e}")
            return None

    def get_hourly_weather(
        self,
        *,
        latitude: float,
        longitude: float,
        start: datetime,
        end: datetime,
        prefer_historical: bool = True,
    ) -> pd.DataFrame | None:
        # Choose endpoint
        now = datetime.utcnow()
        use_archive = prefer_historical and end <= now
        base = self.BASE_ARCHIVE if use_archive else self.BASE_FORECAST
        source = "archive" if use_archive else "forecast"

        cache_id = self._cache_id(latitude, longitude, start, end, source)
        import contextlib

        if self.cache_manager and getattr(self.cache_manager, "is_cached", None):
            with contextlib.suppress(Exception):
                if self.cache_manager.is_cached("weather_api", cache_id):
                    # For forecast, require freshness (e.g., <= 3 hours old)
                    fresh_ok = True
                    if source == "forecast" and getattr(
                        self.cache_manager, "get_data_cache_entry", None
                    ):
                        meta = self.cache_manager.get_data_cache_entry(
                            "weather_api", cache_id
                        )
                        if meta and meta.get("created_at"):
                            try:
                                created = pd.to_datetime(
                                    meta["created_at"]
                                )  # sqlite timestamp
                                fresh_ok = (
                                    datetime.utcnow() - created.to_pydatetime()
                                ) <= timedelta(hours=3)
                            except Exception:
                                fresh_ok = True
                    if fresh_ok:
                        cached = self.cache_manager.load_cached_data(
                            "weather_api", cache_id
                        )
                        if isinstance(cached, pd.DataFrame):
                            return cached

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "cloud_cover",
                    "wind_speed_10m",
                    "shortwave_radiation",
                ]
            ),
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "timezone": "auto",
        }
        payload = self._request(base, params)
        if not payload:
            return None
        df = self._normalize(payload)
        if df is None or df.empty:
            return None

        # Clip ranges and basic sanity
        df["relative_humidity_2m"] = pd.to_numeric(
            df["relative_humidity_2m"], errors="coerce"
        ).clip(0, 100)
        df["cloud_cover"] = pd.to_numeric(df["cloud_cover"], errors="coerce").clip(
            0, 100
        )
        df["wind_speed_10m"] = pd.to_numeric(
            df["wind_speed_10m"], errors="coerce"
        ).clip(lower=0)
        df["temperature_2m"] = pd.to_numeric(df["temperature_2m"], errors="coerce")
        df["shortwave_radiation"] = pd.to_numeric(
            df["shortwave_radiation"], errors="coerce"
        ).clip(lower=0)

        if self.cache_manager and getattr(self.cache_manager, "cache_data", None):
            with contextlib.suppress(Exception):
                self.cache_manager.cache_data(
                    df,
                    "weather_api",
                    cache_id,
                    metadata={
                        "provider": "open-meteo",
                        "source": source,
                        "lat": latitude,
                        "lon": longitude,
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                    },
                )
        return df
