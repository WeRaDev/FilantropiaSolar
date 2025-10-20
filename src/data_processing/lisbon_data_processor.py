"""
Data Processing Module for Lisbon PV Installations
Handles data loading, processing, correlation analysis for Lisbon_1 through Lisbon_4
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.energy_ranking import calculate_specific_energy_ranking

logger = logging.getLogger(__name__)

# Constants for data processing and analysis
MINIMUM_CORRELATION_SAMPLES = (
    10  # Minimum data points needed for meaningful correlation analysis
)
OPTIMAL_RANKING_THRESHOLD = (
    4  # Rankings >= 4 are considered optimal (good to excellent)
)
MONTHS_PER_YEAR = 12  # Number of months in a year for date calculations
DEFAULT_PV_CAPACITY_KWP = 10.0  # Default PV capacity in kWp if not specified


class LisbonDataProcessor:
    """Data processor for Lisbon PV installations"""

    def __init__(self, data_path=""):
        """
        Initialize Lisbon Data Processor

        Args:
            data_path (str): Path to the data directory
        """
        if data_path:
            self.data_path = Path(data_path)
        else:
            # Default to project_root/data directory
            project_root = Path(__file__).parent.parent.parent
            self.data_path = project_root / "data"
        self.lisbon_installations = ["Lisbon_1", "Lisbon_2", "Lisbon_3", "Lisbon_4"]
        self.correspondence = {
            "Lisbon_1": ["84071567"],
            "Lisbon_2": ["84071569"],
            "Lisbon_3": ["84071570"],
            "Lisbon_4": ["62032213"],
        }
        self.pv_data = {}
        self.weather_data = None
        self.merged_data = {}

    def load_pv_data(self, excel_file="PV Plants Datasets.xlsx"):
        """
        Load PV data for all Lisbon installations

        Args:
            excel_file (str): Name of the Excel file containing PV data

        Returns:
            dict: Dictionary containing DataFrames for each installation
        """
        try:
            file_path = self.data_path / excel_file

            for installation, sheet_names in self.correspondence.items():
                for sheet_name in sheet_names:
                    try:
                        df = pd.read_excel(file_path, sheet_name=sheet_name)

                        # Ensure Date column exists and is datetime
                        if "Date" in df.columns:
                            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

                        # Calculate specific energy if needed
                        if (
                            "Specific Energy (kWh/kWp)" not in df.columns
                            and "Produced Energy (kWh)" in df.columns
                        ):
                            # Assuming default kWp rating if not available
                            df["Specific Energy (kWh/kWp)"] = (
                                df["Produced Energy (kWh)"] / DEFAULT_PV_CAPACITY_KWP
                            )

                        # Add ranking
                        if "Specific Energy (kWh/kWp)" in df.columns:
                            df["Ranking"] = calculate_specific_energy_ranking(
                                df["Specific Energy (kWh/kWp)"]
                            )

                        # Add hour column for analysis
                        if "Date" in df.columns:
                            df["Hour"] = df["Date"].dt.hour
                            df["Month"] = df["Date"].dt.month
                            df["DayOfYear"] = df["Date"].dt.dayofyear

                        self.pv_data[installation] = df
                        logger.info(f"Loaded {len(df)} records for {installation}")

                    except Exception as e:
                        logger.error(
                            f"Error loading {installation} from sheet {sheet_name}: {e}"
                        )

        except Exception as e:
            logger.error(f"Error loading PV data file {excel_file}: {e}")

        return self.pv_data

    def load_weather_data(self, weather_file="weather_files/Lisbon_weather.csv"):
        """
        Load weather data for Lisbon

        Args:
            weather_file (str): Path to weather CSV file

        Returns:
            pd.DataFrame: Weather data DataFrame
        """
        try:
            file_path = self.data_path / weather_file

            self.weather_data = pd.read_csv(
                file_path, delimiter=",", on_bad_lines="skip"
            )

            # Ensure time column is datetime
            if "time" in self.weather_data.columns:
                self.weather_data["time"] = pd.to_datetime(
                    self.weather_data["time"], errors="coerce"
                )
                self.weather_data = self.weather_data.dropna(subset=["time"])

                # Add time components
                self.weather_data["Hour"] = self.weather_data["time"].dt.hour
                self.weather_data["Month"] = self.weather_data["time"].dt.month
                self.weather_data["DayOfYear"] = self.weather_data["time"].dt.dayofyear

            logger.info(f"Loaded {len(self.weather_data)} weather records")

        except Exception as e:
            logger.error(f"Error loading weather data: {e}")
            self.weather_data = pd.DataFrame()

        return self.weather_data

    def merge_pv_weather_data(self, installation):
        """
        Merge PV and weather data for a specific installation

        Args:
            installation (str): Installation name (e.g., 'Lisbon_1')

        Returns:
            pd.DataFrame: Merged data
        """
        if installation not in self.pv_data or self.weather_data is None:
            logger.error(f"Data not loaded for {installation} or weather data missing")
            return pd.DataFrame()

        try:
            pv_df = self.pv_data[installation].copy()
            weather_df = self.weather_data.copy()

            # Sort both DataFrames by time
            pv_df = pv_df.sort_values("Date")
            weather_df = weather_df.sort_values("time")

            # Merge using closest time match
            merged_df = pd.merge_asof(
                pv_df,
                weather_df,
                left_on="Date",
                right_on="time",
                direction="nearest",
                suffixes=("_pv", "_weather"),
            )

            self.merged_data[installation] = merged_df
            logger.info(f"Merged {len(merged_df)} records for {installation}")

            return merged_df

        except Exception as e:
            logger.error(f"Error merging data for {installation}: {e}")
            return pd.DataFrame()

    def calculate_seasonal_correlations(self, installation):
        """
        Calculate correlations between weather and energy production by season

        Args:
            installation (str): Installation name

        Returns:
            dict: Seasonal correlation matrices
        """
        if installation not in self.merged_data:
            self.merge_pv_weather_data(installation)

        merged_df = self.merged_data.get(installation, pd.DataFrame())

        if merged_df.empty:
            return {}

        # Define seasons
        def get_season(month):
            if month in [12, 1, 2]:
                return "Winter"
            elif month in [3, 4, 5]:
                return "Spring"
            elif month in [6, 7, 8]:
                return "Summer"
            else:
                return "Autumn"

        merged_df["Season"] = merged_df["Month"].apply(get_season)

        # Weather features for correlation
        weather_features = [
            "temperature_2m (°C)",
            "relative_humidity_2m (%)",
            "dew_point_2m (°C)",
            "apparent_temperature (°C)",
            "cloud_cover (%)",
            "wind_speed_10m (km/h)",
            "shortwave_radiation (W/m²)",
        ]

        # Energy features
        energy_features = [
            "Produced Energy (kWh)",
            "Specific Energy (kWh/kWp)",
            "Ranking",
        ]

        # Available features (some might be missing)
        available_weather = [f for f in weather_features if f in merged_df.columns]
        available_energy = [f for f in energy_features if f in merged_df.columns]

        seasonal_correlations = {}

        for season in ["Winter", "Spring", "Summer", "Autumn"]:
            season_data = merged_df[merged_df["Season"] == season]

            if len(season_data) > MINIMUM_CORRELATION_SAMPLES:
                correlation_features = available_weather + available_energy
                correlation_data = season_data[correlation_features].select_dtypes(
                    include="number"
                )

                if not correlation_data.empty:
                    seasonal_correlations[season] = correlation_data.corr()

        return seasonal_correlations

    def calculate_hourly_patterns(self, installation):
        """
        Calculate hourly patterns for energy production and weather

        Args:
            installation (str): Installation name

        Returns:
            pd.DataFrame: Hourly patterns
        """
        if installation not in self.merged_data:
            self.merge_pv_weather_data(installation)

        merged_df = self.merged_data.get(installation, pd.DataFrame())

        if merged_df.empty:
            return pd.DataFrame()

        # Group by hour and calculate means
        hourly_patterns = (
            merged_df.groupby("Hour")
            .agg(
                {
                    "Produced Energy (kWh)": ["mean", "std", "count"],
                    "Specific Energy (kWh/kWp)": ["mean", "std"]
                    if "Specific Energy (kWh/kWp)" in merged_df.columns
                    else [],
                    "Ranking": ["mean", "std"]
                    if "Ranking" in merged_df.columns
                    else [],
                    "temperature_2m (°C)": "mean"
                    if "temperature_2m (°C)" in merged_df.columns
                    else [],
                    "shortwave_radiation (W/m²)": "mean"
                    if "shortwave_radiation (W/m²)" in merged_df.columns
                    else [],
                    "cloud_cover (%)": "mean"
                    if "cloud_cover (%)" in merged_df.columns
                    else [],
                }
            )
            .round(2)
        )

        # Flatten column names
        hourly_patterns.columns = [
            "_".join(col).strip("_") for col in hourly_patterns.columns
        ]
        hourly_patterns = hourly_patterns.reset_index()

        return hourly_patterns

    def process_weather_data(self, weather_file="weather_files/Lisbon_weather.csv"):
        """
        Process weather data - alias for load_weather_data for backward compatibility

        Args:
            weather_file (str): Path to weather CSV file

        Returns:
            pd.DataFrame: Processed weather data
        """
        return self.load_weather_data(weather_file)

    def get_installation_summary(self, installation):
        """
        Get summary statistics for an installation

        Args:
            installation (str): Installation name

        Returns:
            dict: Summary statistics
        """
        if installation not in self.pv_data:
            return {}

        df = self.pv_data[installation]

        if df.empty:
            return {}

        summary = {
            "installation": installation,
            "total_records": len(df),
            "date_range": {
                "start": df["Date"].min().strftime("%Y-%m-%d")
                if df["Date"].notna().any()
                else None,
                "end": df["Date"].max().strftime("%Y-%m-%d")
                if df["Date"].notna().any()
                else None,
            },
            "energy_production": {
                "total_kwh": df["Produced Energy (kWh)"].sum()
                if "Produced Energy (kWh)" in df.columns
                else 0,
                "avg_hourly_kwh": df["Produced Energy (kWh)"].mean()
                if "Produced Energy (kWh)" in df.columns
                else 0,
                "max_hourly_kwh": df["Produced Energy (kWh)"].max()
                if "Produced Energy (kWh)" in df.columns
                else 0,
            },
        }

        # Add specific energy stats if available
        if "Specific Energy (kWh/kWp)" in df.columns:
            summary["specific_energy"] = {
                "avg": df["Specific Energy (kWh/kWp)"].mean(),
                "max": df["Specific Energy (kWh/kWp)"].max(),
                "std": df["Specific Energy (kWh/kWp)"].std(),
            }

        # Add ranking stats if available
        if "Ranking" in df.columns:
            summary["ranking"] = {
                "avg": df["Ranking"].mean(),
                "distribution": df["Ranking"].value_counts().to_dict(),
                "optimal_hours_pct": (df["Ranking"] >= OPTIMAL_RANKING_THRESHOLD).mean()
                * 100,
            }

        return summary

    def get_all_installations_summary(self):
        """
        Get summary for all Lisbon installations

        Returns:
            dict: Combined summary
        """
        summaries = {}

        for installation in self.lisbon_installations:
            summaries[installation] = self.get_installation_summary(installation)

        # Add combined stats
        if self.pv_data:
            total_records = sum(len(df) for df in self.pv_data.values())
            total_energy = sum(
                df["Produced Energy (kWh)"].sum()
                for df in self.pv_data.values()
                if "Produced Energy (kWh)" in df.columns
            )

            summaries["combined"] = {
                "total_installations": len(
                    [k for k in self.pv_data if k in self.lisbon_installations]
                ),
                "total_records": total_records,
                "total_energy_kwh": total_energy,
                "avg_energy_per_installation": total_energy / len(self.pv_data)
                if self.pv_data
                else 0,
            }

        return summaries

    def prepare_prediction_data(self, installation, target_date, days_window=30):
        """
        Prepare historical data for prediction model training

        Args:
            installation (str): Installation name
            target_date (str or datetime): Target date for prediction
            days_window (int): Days of historical data to use

        Returns:
            pd.DataFrame: Prepared data for prediction
        """
        if installation not in self.merged_data:
            self.merge_pv_weather_data(installation)

        merged_df = self.merged_data.get(installation, pd.DataFrame())

        if merged_df.empty:
            return pd.DataFrame()

        # Convert target date
        if isinstance(target_date, str):
            target_date = pd.to_datetime(target_date)

        # Get historical data around the same time of year
        target_month = target_date.month

        # Filter data within the same month ± 1 month
        month_window = [target_month - 1, target_month, target_month + 1]
        month_window = [
            (m - 1) % MONTHS_PER_YEAR + 1
            if m <= 0
            else (m - 1) % MONTHS_PER_YEAR + 1
            if m > MONTHS_PER_YEAR
            else m
            for m in month_window
        ]

        historical_data = merged_df[merged_df["Month"].isin(month_window)].copy()

        # Add features for prediction
        if not historical_data.empty:
            historical_data["DaysSinceEpoch"] = (
                historical_data["Date"] - pd.Timestamp("1970-01-01")
            ).dt.days
            historical_data["SinHour"] = np.sin(
                2 * np.pi * historical_data["Hour"] / 24
            )
            historical_data["CosHour"] = np.cos(
                2 * np.pi * historical_data["Hour"] / 24
            )
            historical_data["SinMonth"] = np.sin(
                2 * np.pi * historical_data["Month"] / 12
            )
            historical_data["CosMonth"] = np.cos(
                2 * np.pi * historical_data["Month"] / 12
            )

        return historical_data.tail(days_window * 24)  # Last N days of hourly data
