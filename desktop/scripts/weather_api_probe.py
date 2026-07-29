import asyncio
from pathlib import Path
import sys

# Ensure project root on sys.path so 'src' package is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.weather_api.async_weather_client import AsyncWeatherClient


async def main():
    async with AsyncWeatherClient() as client:
        current = await client.get_current_weather("Lisbon")
        print("Current weather data points (keys):")
        for k in sorted(current.keys()):
            print(f"- {k}")

        df = await client.get_weather_forecast("Lisbon", days_ahead=1)
        print("\nHourly forecast data points (columns):")
        for c in df.columns:
            print(f"- {c}")

        print("\nSample rows (first 5):")
        print(df.head().to_string())


if __name__ == "__main__":
    asyncio.run(main())
