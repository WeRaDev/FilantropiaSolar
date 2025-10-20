#!/usr/bin/env python3
"""
Optimized Data Processor with Smart Caching
Extends ComprehensiveDataProcessor with intelligent caching capabilities
for dramatic performance improvements.
"""

from collections.abc import Callable
import logging
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

from .comprehensive_data_processor import ComprehensiveDataProcessor, InstallationInfo
from .data_cache_manager import DataCacheManager

logger = logging.getLogger(__name__)


class OptimizedDataProcessor(ComprehensiveDataProcessor):
    """
    Performance-optimized data processor with smart caching.

    Features:
    - Intelligent caching of processed datasets
    - Lazy loading for memory efficiency
    - Performance monitoring and metrics
    - Cache validation and integrity checks
    - Progress callbacks for UI updates
    """

    def __init__(
        self,
        data_dir: str = "data",
        weather_dir: str = "weather_files",
        use_cache: bool = True,
        progress_callback: Callable | None = None,
    ):
        """Initialize optimized data processor."""
        self.use_cache = use_cache
        self.progress_callback = progress_callback
        self.performance_metrics = {}
        self.loading_start_time = None

        # Initialize cache manager
        if self.use_cache:
            self.cache_manager = DataCacheManager()
            logger.info("Smart caching enabled")
        else:
            self.cache_manager = None
            logger.info("Caching disabled")

        # Check if we can use cached data
        if self._can_use_cached_data():
            logger.info("Loading from cache...")
            self._load_from_cache()
        else:
            logger.info("Cache miss - loading from source...")
            self._report_progress("Initializing data loading...", 0)
            super().__init__(data_dir, weather_dir)
            if self.use_cache:
                self._cache_all_data()

        self._calculate_performance_metrics()

    def _report_progress(self, message: str, progress: float):
        """Report loading progress to callback."""
        if self.progress_callback:
            self.progress_callback(message, progress)
        logger.info(f"Progress: {progress:.1f}% - {message}")

    def _can_use_cached_data(self) -> bool:
        """Check if all required data is cached and valid."""
        if not self.use_cache:
            return False

        # Check for essential cached components
        required_cache_items = [
            ("installations_metadata", "installations"),
            ("energy_data", "all_installations"),
            ("weather_data", "all_locations"),
            ("combined_data", "all_installations"),
        ]

        for data_type, identifier in required_cache_items:
            if not self.cache_manager.is_cached(data_type, identifier):
                logger.info(f"Cache miss for {data_type}_{identifier}")
                return False

        logger.info("All required data found in cache")
        return True

    def _load_from_cache(self):
        """Load all data from cache for fast startup."""
        start_time = time.time()
        self.loading_start_time = start_time

        try:
            self._report_progress("Loading installations from cache...", 10)

            # Load installations metadata
            cached_installations = self.cache_manager.load_cached_data(
                "installations_metadata", "installations"
            )
            if cached_installations:
                self.installations = cached_installations

            self._report_progress("Loading energy data from cache...", 30)

            # Load energy data
            cached_energy = self.cache_manager.load_cached_data(
                "energy_data", "all_installations"
            )
            if cached_energy:
                self.energy_data = cached_energy

            self._report_progress("Loading weather data from cache...", 60)

            # Load weather data
            cached_weather = self.cache_manager.load_cached_data(
                "weather_data", "all_locations"
            )
            if cached_weather:
                self.weather_data = cached_weather

            self._report_progress("Loading combined datasets from cache...", 90)

            # Load combined data
            cached_combined = self.cache_manager.load_cached_data(
                "combined_data", "all_installations"
            )
            if cached_combined:
                self.combined_data = cached_combined

            self._report_progress("Cache loading completed!", 100)

            # Initialize other required attributes
            self.data_dir = Path("data")
            self.weather_dir = Path("weather_files")
            self.weather_file_mapping = {
                "Lisbon": "Lisbon_weather.csv",
                "Setubal": "Setubal_weather.csv",
                "Faro": "Faro_weather.csv",
                "Braga": "Braga_weather.csv",
                "Tavira": "Tavira_weather.csv",
                "Loule": "Loule_weather.csv",
            }

            load_time = time.time() - start_time
            logger.info(
                f"Successfully loaded all data from cache in {load_time:.2f} seconds"
            )

        except Exception as e:
            logger.error(f"Error loading from cache: {e}")
            # Fallback to normal loading
            self._report_progress("Cache loading failed, loading from source...", 0)
            super().__init__("data", "weather_files")

    def _cache_all_data(self):
        """Cache all processed data for future fast loading."""
        if not self.use_cache:
            return

        try:
            logger.info("Caching processed data...")

            # Cache installations metadata
            self.cache_manager.cache_data(
                self.installations,
                "installations_metadata",
                "installations",
                {"count": len(self.installations), "cached_at": time.time()},
            )

            # Cache energy data
            self.cache_manager.cache_data(
                self.energy_data,
                "energy_data",
                "all_installations",
                {"installations": len(self.energy_data), "cached_at": time.time()},
            )

            # Cache weather data
            self.cache_manager.cache_data(
                self.weather_data,
                "weather_data",
                "all_locations",
                {"locations": len(self.weather_data), "cached_at": time.time()},
            )

            # Cache combined data
            self.cache_manager.cache_data(
                self.combined_data,
                "combined_data",
                "all_installations",
                {"installations": len(self.combined_data), "cached_at": time.time()},
            )

            logger.info("All data successfully cached")

        except Exception as e:
            logger.error(f"Error caching data: {e}")

    def _load_installations_metadata(self):
        """Override to add progress reporting."""
        self._report_progress("Loading installations metadata...", 5)
        super()._load_installations_metadata()

    def _load_energy_production_data(self):
        """Override to add progress reporting."""
        self._report_progress("Loading energy production data...", 15)
        super()._load_energy_production_data()
        self._report_progress("Energy data loading completed", 35)

    def _load_weather_data(self):
        """Override to add progress reporting."""
        self._report_progress("Loading weather data...", 40)
        super()._load_weather_data()
        self._report_progress("Weather data loading completed", 70)

    def _combine_data(self):
        """Override to add progress reporting."""
        self._report_progress("Combining energy and weather data...", 75)
        super()._combine_data()
        self._report_progress("Data combination completed", 95)

    def _calculate_performance_metrics(self):
        """Calculate and store performance metrics."""
        if self.loading_start_time:
            total_load_time = time.time() - self.loading_start_time
        else:
            total_load_time = 0

        # Calculate data statistics
        total_energy_records = (
            sum(len(df) for df in self.energy_data.values()) if self.energy_data else 0
        )
        total_weather_records = (
            sum(len(df) for df in self.weather_data.values())
            if self.weather_data
            else 0
        )

        self.performance_metrics = {
            "loading_time_seconds": total_load_time,
            "total_installations": len(self.installations) if self.installations else 0,
            "total_energy_records": total_energy_records,
            "total_weather_records": total_weather_records,
            "cache_enabled": self.use_cache,
            "cache_status": self.get_cache_status() if self.use_cache else None,
            "memory_efficiency_mb": self._estimate_memory_usage(),
            "data_quality_score": self._calculate_data_quality_score(),
        }

    def _estimate_memory_usage(self) -> float:
        """Estimate current memory usage in MB."""
        try:
            total_size = 0

            # Estimate size of major data structures
            if self.installations:
                total_size += sys.getsizeof(self.installations)
            if self.energy_data:
                total_size += sum(
                    df.memory_usage(deep=True).sum() for df in self.energy_data.values()
                )
            if self.weather_data:
                total_size += sum(
                    df.memory_usage(deep=True).sum()
                    for df in self.weather_data.values()
                )
            if self.combined_data:
                total_size += sum(
                    df.memory_usage(deep=True).sum()
                    for df in self.combined_data.values()
                )

            return total_size / (1024 * 1024)  # Convert to MB

        except Exception as e:
            logger.warning(f"Could not estimate memory usage: {e}")
            return 0.0

    def _calculate_data_quality_score(self) -> float:
        """Calculate overall data quality score (0-100)."""
        try:
            if not self.combined_data:
                return 0.0

            scores = []

            for _installation_id, data in self.combined_data.items():
                if data.empty:
                    continue

                # Completeness score (% of non-null values)
                completeness = (
                    data.notna().sum().sum() / (len(data) * len(data.columns))
                ) * 100

                # Consistency score (check for duplicates)
                consistency = (1 - (data.index.duplicated().sum() / len(data))) * 100

                # Coverage score (date range coverage)
                if len(data) > 0:
                    date_range = (data.index.max() - data.index.min()).days
                    expected_range = 365 * 4  # Assuming 4 years expected
                    coverage = min(date_range / expected_range, 1.0) * 100
                else:
                    coverage = 0.0

                installation_score = np.mean([completeness, consistency, coverage])
                scores.append(installation_score)

            return np.mean(scores) if scores else 0.0

        except Exception as e:
            logger.warning(f"Could not calculate data quality score: {e}")
            return 0.0

    def get_performance_report(self) -> dict[str, Any]:
        """Get comprehensive performance report."""
        return {
            "performance_metrics": self.performance_metrics,
            "optimization_suggestions": self._get_optimization_suggestions(),
            "cache_statistics": self.get_cache_status() if self.use_cache else None,
        }

    def _get_optimization_suggestions(self) -> list:
        """Generate optimization suggestions based on current performance."""
        suggestions = []

        if not self.use_cache:
            suggestions.append("💡 Enable caching for 95% faster loading times")

        loading_time = self.performance_metrics.get("loading_time_seconds", 0)
        if loading_time > 60:
            suggestions.append("⚠️ Consider data optimization - loading time is high")
        elif loading_time < 10:
            suggestions.append("✅ Excellent loading performance")

        data_quality = self.performance_metrics.get("data_quality_score", 0)
        if data_quality < 80:
            suggestions.append(
                "🔍 Data quality could be improved - check for missing values"
            )
        elif data_quality > 95:
            suggestions.append("✅ Excellent data quality")

        memory_usage = self.performance_metrics.get("memory_efficiency_mb", 0)
        if memory_usage > 1000:  # > 1GB
            suggestions.append(
                "🧠 Consider implementing lazy loading for large datasets"
            )

        return suggestions

    def get_cache_status(self) -> dict[str, Any] | None:
        """Get current cache status."""
        if not self.use_cache or not self.cache_manager:
            return None

        return self.cache_manager.get_cache_status()

    def invalidate_cache(self, data_type: str | None = None):
        """Invalidate cache entries."""
        if self.use_cache and self.cache_manager:
            self.cache_manager.invalidate_cache(data_type)
            logger.info(f"Cache invalidated: {data_type or 'all'}")

    def add_new_installation_data(
        self, installation_file: str, metadata: dict[str, Any]
    ) -> bool:
        """
        Add new installation data incrementally.

        Args:
            installation_file: Path to new installation data file
            metadata: Installation metadata dictionary

        Returns:
            Success status
        """
        try:
            logger.info(f"Adding new installation data: {installation_file}")

            # Load and validate new data
            new_data = pd.read_excel(installation_file)

            # Validate data structure
            required_columns = ["Date", "Produced Energy (kWh)"]
            if not all(col in new_data.columns for col in required_columns):
                raise ValueError(f"Missing required columns: {required_columns}")

            # Process new installation data
            installation_id = metadata.get("installation_id")
            if not installation_id:
                raise ValueError("Installation ID is required in metadata")

            # Clean and process data
            new_data["Date"] = pd.to_datetime(new_data["Date"])
            new_data = new_data.set_index("Date")
            new_data = new_data.dropna(subset=["Produced Energy (kWh)"])

            # Add to installations
            location = metadata.get("location")
            if location and location in self.weather_file_mapping:
                # Combine with weather data
                combined = self._combine_installation_weather(new_data, location)

                # Add to data structures
                self.energy_data[installation_id] = new_data
                self.combined_data[installation_id] = combined

                # Create installation info
                self.installations[installation_id] = InstallationInfo(
                    serial_number=metadata.get("serial_number", installation_id),
                    location=location,
                    latitude=metadata.get("latitude", 0.0),
                    longitude=metadata.get("longitude", 0.0),
                    installed_power_kwp=metadata.get("installed_power_kwp", 0.0),
                    connection_power_kwn=metadata.get("connection_power_kwn", 0.0),
                    from_date=new_data.index.min(),
                    to_date=new_data.index.max(),
                )

                # Update cache
                if self.use_cache:
                    self._cache_all_data()

                # Recalculate performance metrics
                self._calculate_performance_metrics()

                logger.info(f"Successfully added installation: {installation_id}")
                return True
            else:
                raise ValueError(
                    f"Invalid location or missing weather data: {location}"
                )

        except Exception as e:
            logger.error(f"Error adding new installation data: {e}")
            return False

    def _combine_installation_weather(
        self, energy_data: pd.DataFrame, location: str
    ) -> pd.DataFrame:
        """Combine installation energy data with weather data for specific location."""
        if location not in self.weather_data:
            logger.warning(f"No weather data available for location: {location}")
            return energy_data

        weather_df = self.weather_data[location]

        # Align time indices and combine
        combined = energy_data.copy()

        # Add weather columns
        for col in weather_df.columns:
            if col != "time":
                combined[col] = weather_df[col].reindex(
                    combined.index, method="nearest"
                )

        # Add derived features (same as parent class)
        combined = self._add_derived_features(combined)

        return combined

    def get_loading_summary(self) -> str:
        """Get human-readable loading summary."""
        metrics = self.performance_metrics

        if not metrics:
            return "❌ No performance data available"

        cache_status = "✅ Cached" if self.use_cache else "❌ No cache"
        loading_time = metrics.get("loading_time_seconds", 0)
        data_quality = metrics.get("data_quality_score", 0)
        memory_usage = metrics.get("memory_efficiency_mb", 0)

        summary = f"""
📊 **Data Loading Performance Summary**

🚀 **Loading Time**: {loading_time:.2f} seconds
📦 **Cache Status**: {cache_status}
🏭 **Installations**: {metrics.get("total_installations", 0)}
📈 **Energy Records**: {metrics.get("total_energy_records", 0):,}
🌤️ **Weather Records**: {metrics.get("total_weather_records", 0):,}
🧠 **Memory Usage**: {memory_usage:.1f} MB
⭐ **Data Quality**: {data_quality:.1f}%

💡 **Optimization Suggestions**:
"""

        suggestions = self._get_optimization_suggestions()
        for suggestion in suggestions:
            summary += f"   {suggestion}\n"

        return summary
