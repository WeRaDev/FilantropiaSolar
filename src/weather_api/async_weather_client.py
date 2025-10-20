"""
Async Weather API Client for FilantropiaSolar
Provides asynchronous weather data retrieval for improved performance and responsiveness
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
import pandas as pd

logger = logging.getLogger(__name__)


class AsyncWeatherClient:
    """Asynchronous weather API client for retrieving current and forecast weather data"""

    def __init__(
        self,
        api_key: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ):
        """
        Initialize Async Weather Client

        Args:
            api_key: API key for weather service (if required)
            session: Optional existing aiohttp session
        """
        self.api_key = api_key
        self.base_url = "https://api.open-meteo.com/v1"
        self.session = session
        self._owned_session = session is None

        # Location coordinates for major Portuguese cities
        self.locations = {
            "Lisbon": {"latitude": 38.7223, "longitude": -9.1393},
            "Faro": {"latitude": 37.0194, "longitude": -7.9322},
            "Braga": {"latitude": 41.5518, "longitude": -8.4229},
            "Setubal": {"latitude": 38.5244, "longitude": -8.8882},
            "Tavira": {"latitude": 37.1266, "longitude": -7.6481},
            "Loule": {"latitude": 37.1375, "longitude": -8.0244},
        }

        # Default timeout and retry settings
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.max_retries = 3
        self.retry_delay = 1.0

    async def __aenter__(self):
        """Async context manager entry"""
        if self._owned_session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._owned_session and self.session:
            await self.session.close()

    async def get_current_weather(self, location: str = "Lisbon") -> dict[str, Any]:
        """
        Get current weather data for specified location

        Args:
            location: Location name (e.g., 'Lisbon', 'Faro')

        Returns:
            Current weather conditions
        """
        if location not in self.locations:
            raise ValueError(
                f"Location '{location}' not supported. Available: {list(self.locations.keys())}",
            )

        coordinates = self.locations[location]

        try:
            url = f"{self.base_url}/forecast"
            params = {
                "latitude": coordinates["latitude"],
                "longitude": coordinates["longitude"],
                "current": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "cloud_cover",
                    "wind_speed_10m",
                    "wind_direction_10m",
                ],
                "timezone": "Europe/Lisbon",
            }

            data = await self._make_request_with_retry(url, params)
            current = data.get("current", {})

            return {
                "location": location,
                "time": current.get("time", datetime.now().isoformat()),
                "temperature_2m": current.get("temperature_2m", 0),
                "relative_humidity_2m": current.get("relative_humidity_2m", 0),
                "apparent_temperature": current.get("apparent_temperature", 0),
                "cloud_cover": current.get("cloud_cover", 0),
                "wind_speed_10m": current.get("wind_speed_10m", 0),
                "wind_direction_10m": current.get("wind_direction_10m", 0),
            }

        except Exception as e:
            logger.error(f"Error fetching current weather for {location}: {e}")
            return self._get_default_weather(location)

    async def get_weather_forecast(
        self,
        location: str = "Lisbon",
        days_ahead: int = 7,
    ) -> pd.DataFrame:
        """
        Get weather forecast for specified location

        Args:
            location: Location name
            days_ahead: Number of days to forecast

        Returns:
            Weather forecast data
        """
        if location not in self.locations:
            raise ValueError(
                f"Location '{location}' not supported. Available: {list(self.locations.keys())}",
            )

        coordinates = self.locations[location]

        try:
            end_date = datetime.now() + timedelta(days=days_ahead)

            url = f"{self.base_url}/forecast"
            params = {
                "latitude": coordinates["latitude"],
                "longitude": coordinates["longitude"],
                "hourly": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "dew_point_2m",
                    "apparent_temperature",
                    "cloud_cover",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "shortwave_radiation",
                ],
                "end_date": end_date.strftime("%Y-%m-%d"),
                "timezone": "Europe/Lisbon",
            }

            data = await self._make_request_with_retry(url, params)
            hourly = data.get("hourly", {})

            # Create DataFrame with proper column names
            df = pd.DataFrame(
                {
                    "time": pd.to_datetime(hourly.get("time", [])),
                    "temperature_2m": hourly.get("temperature_2m", []),
                    "relative_humidity_2m": hourly.get("relative_humidity_2m", []),
                    "dew_point_2m": hourly.get("dew_point_2m", []),
                    "apparent_temperature": hourly.get("apparent_temperature", []),
                    "cloud_cover": hourly.get("cloud_cover", []),
                    "wind_speed_10m": hourly.get("wind_speed_10m", []),
                    "wind_direction_10m": hourly.get("wind_direction_10m", []),
                    "shortwave_radiation": hourly.get("shortwave_radiation", []),
                },
            )

            if df.empty:
                return self._get_default_forecast_df(location, days_ahead)

            # Add location metadata
            df["location"] = location
            return df

        except Exception as e:
            logger.error(f"Error fetching weather forecast for {location}: {e}")
            return self._get_default_forecast_df(location, days_ahead)

    async def get_historical_weather(
        self,
        location: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Get historical weather data for specified location

        Args:
            location: Location name
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Historical weather data
        """
        if location not in self.locations:
            raise ValueError(
                f"Location '{location}' not supported. Available: {list(self.locations.keys())}",
            )

        coordinates = self.locations[location]

        try:
            url = f"{self.base_url}/archive"
            params = {
                "latitude": coordinates["latitude"],
                "longitude": coordinates["longitude"],
                "start_date": start_date,
                "end_date": end_date,
                "hourly": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "dew_point_2m",
                    "apparent_temperature",
                    "cloud_cover",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "shortwave_radiation",
                ],
                "timezone": "Europe/Lisbon",
            }

            data = await self._make_request_with_retry(url, params)
            hourly = data.get("hourly", {})

            # Create DataFrame with proper column names
            df = pd.DataFrame(
                {
                    "time": pd.to_datetime(hourly.get("time", [])),
                    "temperature_2m": hourly.get("temperature_2m", []),
                    "relative_humidity_2m": hourly.get("relative_humidity_2m", []),
                    "dew_point_2m": hourly.get("dew_point_2m", []),
                    "apparent_temperature": hourly.get("apparent_temperature", []),
                    "cloud_cover": hourly.get("cloud_cover", []),
                    "wind_speed_10m": hourly.get("wind_speed_10m", []),
                    "wind_direction_10m": hourly.get("wind_direction_10m", []),
                    "shortwave_radiation": hourly.get("shortwave_radiation", []),
                },
            )

            # Add location metadata
            if not df.empty:
                df["location"] = location

            return df

        except Exception as e:
            logger.error(f"Error fetching historical weather for {location}: {e}")
            return pd.DataFrame()

    async def get_weather_for_multiple_locations(
        self,
        locations: list[str],
        days_ahead: int = 7,
    ) -> dict[str, pd.DataFrame]:
        """
        Get weather forecasts for multiple locations concurrently

        Args:
            locations: List of location names
            days_ahead: Number of days to forecast

        Returns:
            Dictionary mapping location names to forecast DataFrames
        """
        tasks = [
            self.get_weather_forecast(location, days_ahead)
            for location in locations
            if location in self.locations
        ]

        if not tasks:
            logger.warning("No valid locations provided")
            return {}

        try:
            # Execute all requests concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            forecasts = {}
            valid_locations = [loc for loc in locations if loc in self.locations]

            for location, result in zip(valid_locations, results, strict=False):
                if isinstance(result, Exception):
                    logger.error(f"Error fetching weather for {location}: {result}")
                    forecasts[location] = self._get_default_forecast_df(
                        location,
                        days_ahead,
                    )
                else:
                    forecasts[location] = result

            return forecasts

        except Exception as e:
            logger.error(f"Error in concurrent weather fetching: {e}")
            return {}

    async def _make_request_with_retry(
        self,
        url: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Make HTTP request with retry logic

        Args:
            url: Request URL
            params: Request parameters

        Returns:
            Response data
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                async with self.session.get(url, params=params) as response:
                    response.raise_for_status()
                    return await response.json()

            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(
                        self.retry_delay * (2**attempt),
                    )  # Exponential backoff
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}",
                    )
                else:
                    logger.error(f"All retry attempts failed: {e}")

        raise last_exception

    def _get_default_weather(self, location: str) -> dict[str, Any]:
        """Get default weather data for fallback"""
        return {
            "location": location,
            "time": datetime.now().isoformat(),
            "temperature_2m": 15.0,  # Default temperature
            "relative_humidity_2m": 60.0,
            "apparent_temperature": 15.0,
            "cloud_cover": 50.0,
            "wind_speed_10m": 5.0,
            "wind_direction_10m": 180.0,
        }

    def _get_default_forecast_df(self, location: str, days_ahead: int) -> pd.DataFrame:
        """Get default forecast DataFrame for fallback"""
        hours = days_ahead * 24
        time_range = pd.date_range(
            start=datetime.now().replace(minute=0, second=0, microsecond=0),
            periods=hours,
            freq="h",
        )

        return pd.DataFrame(
            {
                "time": time_range,
                "temperature_2m": [15.0] * hours,
                "relative_humidity_2m": [60.0] * hours,
                "dew_point_2m": [10.0] * hours,
                "apparent_temperature": [15.0] * hours,
                "cloud_cover": [50.0] * hours,
                "wind_speed_10m": [5.0] * hours,
                "wind_direction_10m": [180.0] * hours,
                "shortwave_radiation": [200.0] * hours,
                "location": [location] * hours,
            },
        )


# Utility functions for backward compatibility and easy migration
async def get_current_weather_async(location: str = "Lisbon") -> dict[str, Any]:
    """
    Convenience function to get current weather asynchronously

    Args:
        location: Location name

    Returns:
        Current weather data
    """
    async with AsyncWeatherClient() as client:
        return await client.get_current_weather(location)


async def get_weather_forecast_async(
    location: str = "Lisbon",
    days_ahead: int = 7,
) -> pd.DataFrame:
    """
    Convenience function to get weather forecast asynchronously

    Args:
        location: Location name
        days_ahead: Number of days to forecast

    Returns:
        Weather forecast DataFrame
    """
    async with AsyncWeatherClient() as client:
        return await client.get_weather_forecast(location, days_ahead)


async def get_multiple_locations_weather_async(
    locations: list[str],
    days_ahead: int = 7,
) -> dict[str, pd.DataFrame]:
    """
    Convenience function to get weather for multiple locations concurrently

    Args:
        locations: List of location names
        days_ahead: Number of days to forecast

    Returns:
        Dictionary mapping locations to forecast DataFrames
    """
    async with AsyncWeatherClient() as client:
        return await client.get_weather_for_multiple_locations(locations, days_ahead)


if __name__ == "__main__":
    # Example usage
    async def main():
        async with AsyncWeatherClient() as client:
            # Get current weather
            current = await client.get_current_weather("Lisbon")
            print(f"Current weather in Lisbon: {current}")

            # Get forecast
            forecast = await client.get_weather_forecast("Lisbon", days_ahead=3)
            print(f"3-day forecast shape: {forecast.shape}")

            # Get weather for multiple locations
            locations = ["Lisbon", "Faro", "Braga"]
            multi_weather = await client.get_weather_for_multiple_locations(locations)
            print(f"Weather data for {len(multi_weather)} locations")

    asyncio.run(main())
