"""
Energy Production Prediction Model for FilantropiaSolar
Uses machine learning to predict solar energy production based on weather forecasts
"""

import logging

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.utils.energy_ranking import calculate_specific_energy_ranking

logger = logging.getLogger(__name__)

# Training constants
MINIMUM_TRAINING_SAMPLES = 50  # Minimum samples required for model training


class EnergyPredictor:
    """Energy production prediction model for Lisbon PV installations"""

    def __init__(self, installation="Lisbon_1"):
        """
        Initialize Energy Predictor

        Args:
            installation (str): PV installation name
        """
        self.installation = installation
        self.models = {
            "random_forest": RandomForestRegressor(n_estimators=100, random_state=42),
            "gradient_boost": GradientBoostingRegressor(
                n_estimators=100,
                random_state=42,
            ),
            "linear": LinearRegression(),
        }
        self.best_model = None
        self.best_model_name = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.is_trained = False
        self.model_performance = {}

    def prepare_features(self, df):
        """
        Prepare features for machine learning model

        Args:
            df (pd.DataFrame): Merged PV and weather data

        Returns:
            pd.DataFrame: Feature DataFrame
        """
        if df.empty:
            return pd.DataFrame()

        # Create a copy to avoid modifying original data
        features_df = df.copy()

        # Weather features
        weather_features = [
            "temperature_2m (°C)",
            "relative_humidity_2m (%)",
            "dew_point_2m (°C)",
            "apparent_temperature (°C)",
            "cloud_cover (%)",
            "wind_speed_10m (km/h)",
            "shortwave_radiation (W/m²)",
        ]

        # Available weather features
        available_weather = [f for f in weather_features if f in features_df.columns]

        # Time-based features
        if "Date" in features_df.columns:
            features_df["Hour"] = features_df["Date"].dt.hour
            features_df["Month"] = features_df["Date"].dt.month
            features_df["DayOfYear"] = features_df["Date"].dt.dayofyear
            features_df["DayOfWeek"] = features_df["Date"].dt.dayofweek

            # Cyclical encoding for time features
            features_df["SinHour"] = np.sin(2 * np.pi * features_df["Hour"] / 24)
            features_df["CosHour"] = np.cos(2 * np.pi * features_df["Hour"] / 24)
            features_df["SinMonth"] = np.sin(2 * np.pi * features_df["Month"] / 12)
            features_df["CosMonth"] = np.cos(2 * np.pi * features_df["Month"] / 12)
            features_df["SinDayOfYear"] = np.sin(
                2 * np.pi * features_df["DayOfYear"] / 365,
            )
            features_df["CosDayOfYear"] = np.cos(
                2 * np.pi * features_df["DayOfYear"] / 365,
            )

        # Interaction features
        if (
            "shortwave_radiation (W/m²)" in features_df.columns
            and "cloud_cover (%)" in features_df.columns
        ):
            features_df["radiation_cloud_interaction"] = (
                features_df["shortwave_radiation (W/m²)"]
                * (100 - features_df["cloud_cover (%)"])
                / 100
            )

        if (
            "temperature_2m (°C)" in features_df.columns
            and "relative_humidity_2m (%)" in features_df.columns
        ):
            features_df["temp_humidity_interaction"] = features_df[
                "temperature_2m (°C)"
            ] / (features_df["relative_humidity_2m (%)"] + 1)

        # Season indicator
        if "Month" in features_df.columns:

            def get_season_num(month):
                match month:
                    case 12 | 1 | 2:
                        return 0  # Winter
                    case 3 | 4 | 5:
                        return 1  # Spring
                    case 6 | 7 | 8:
                        return 2  # Summer
                    case _:
                        return 3  # Autumn

            features_df["Season"] = features_df["Month"].apply(get_season_num)

        # Solar angle approximation (simplified)
        if "Hour" in features_df.columns and "DayOfYear" in features_df.columns:
            # Solar elevation angle approximation
            features_df["SolarElevation"] = np.maximum(
                0,
                np.sin(np.pi * (features_df["Hour"] - 6) / 12)
                * np.sin(np.pi * (features_df["DayOfYear"] - 80) / 365),
            )

        # Select final feature columns
        time_features = [
            "Hour",
            "Month",
            "SinHour",
            "CosHour",
            "SinMonth",
            "CosMonth",
            "SinDayOfYear",
            "CosDayOfYear",
            "Season",
            "DayOfWeek",
        ]
        interaction_features = [
            "radiation_cloud_interaction",
            "temp_humidity_interaction",
            "SolarElevation",
        ]

        self.feature_columns = available_weather + time_features + interaction_features

        # Filter to existing columns
        self.feature_columns = [
            col for col in self.feature_columns if col in features_df.columns
        ]

        return features_df[self.feature_columns]

    def train_models(self, training_data):
        """
        Train multiple models and select the best one

        Args:
            training_data (pd.DataFrame): Training dataset with features and target

        Returns:
            dict: Training results and performance metrics
        """
        if training_data.empty or "Produced Energy (kWh)" not in training_data.columns:
            logger.error("Training data is empty or missing target variable")
            return {}

        # Prepare features
        X = self.prepare_features(training_data)
        y = training_data["Produced Energy (kWh)"]

        if X.empty:
            logger.error("No features available for training")
            return {}

        # Remove rows with NaN values
        valid_indices = ~(X.isna().any(axis=1) | y.isna())
        X = X[valid_indices]
        y = y[valid_indices]

        if len(X) < MINIMUM_TRAINING_SAMPLES:
            logger.warning("Insufficient training samples")
            return {}

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train models
        results = {}

        for model_name, model in self.models.items():
            try:
                # Train model using modern match-case syntax
                match model_name:
                    case "linear":
                        model.fit(X_train_scaled, y_train)
                        y_pred = model.predict(X_test_scaled)
                    case _:
                        model.fit(X_train, y_train)
                        y_pred = model.predict(X_test)

                # Calculate metrics
                mae = mean_absolute_error(y_test, y_pred)
                r2 = r2_score(y_test, y_pred)

                results[model_name] = {"mae": mae, "r2": r2, "model": model}

                logger.info(f"{model_name}: MAE={mae:.3f}, R²={r2:.3f}")

            except Exception as e:
                logger.error(f"Error training {model_name}: {e}")
                continue

        # Select best model (lowest MAE, but R² > 0)
        valid_results = {k: v for k, v in results.items() if v["r2"] > 0}

        if valid_results:
            self.best_model_name = min(
                valid_results.keys(),
                key=lambda k: valid_results[k]["mae"],
            )
            self.best_model = valid_results[self.best_model_name]["model"]
            self.model_performance = valid_results[self.best_model_name]
            self.is_trained = True

            logger.info(f"Best model: {self.best_model_name}")
        else:
            logger.warning("No models achieved positive R²")

        return results

    def predict_energy(self, weather_data, installed_capacity_kwp=10.0):
        """
        Predict energy production based on weather data

        Args:
            weather_data (pd.DataFrame): Weather forecast data
            installed_capacity_kwp (float): Installed capacity in kWp

        Returns:
            pd.DataFrame: Predictions with energy, specific energy, and ranking
        """
        if not self.is_trained or self.best_model is None:
            logger.error("Model is not trained")
            return pd.DataFrame()

        if weather_data.empty:
            logger.error("Weather data is empty")
            return pd.DataFrame()

        try:
            # Prepare features
            features_df = weather_data.copy()

            # Add time features if time column exists
            if "time" in features_df.columns:
                features_df["Date"] = features_df["time"]
            elif "Date" not in features_df.columns:
                logger.error("No time column found in weather data")
                return pd.DataFrame()

            X = self.prepare_features(features_df)

            if X.empty or not all(col in X.columns for col in self.feature_columns):
                logger.error("Required features missing from weather data")
                return pd.DataFrame()

            X = X[self.feature_columns]

            # Handle missing values
            X = X.fillna(X.mean())

            # Make predictions using modern match-case syntax
            match self.best_model_name:
                case "linear":
                    X_scaled = self.scaler.transform(X)
                    predictions = self.best_model.predict(X_scaled)
                case _:
                    predictions = self.best_model.predict(X)

            # Ensure non-negative predictions
            predictions = np.maximum(predictions, 0)

            # Create results DataFrame
            results_df = weather_data.copy()
            results_df["Predicted Energy (kWh)"] = predictions
            results_df["Specific Energy (kWh/kWp)"] = (
                predictions / installed_capacity_kwp
            )
            results_df["Ranking"] = calculate_specific_energy_ranking(
                results_df["Specific Energy (kWh/kWp)"],
            )

            # Add confidence intervals (simple approach using model performance)
            if hasattr(self, "model_performance") and "mae" in self.model_performance:
                mae = self.model_performance["mae"]
                results_df["Prediction Lower Bound"] = np.maximum(predictions - mae, 0)
                results_df["Prediction Upper Bound"] = predictions + mae

            return results_df

        except Exception as e:
            logger.error(f"Error making predictions: {e}")
            return pd.DataFrame()

    def get_daily_summary(self, predictions_df):
        """
        Get daily summary from hourly predictions

        Args:
            predictions_df (pd.DataFrame): Hourly predictions

        Returns:
            pd.DataFrame: Daily summary
        """
        if predictions_df.empty:
            return pd.DataFrame()

        # Ensure time column
        if "time" in predictions_df.columns:
            time_col = "time"
        elif "Date" in predictions_df.columns:
            time_col = "Date"
        else:
            return pd.DataFrame()

        predictions_df["Date"] = pd.to_datetime(predictions_df[time_col]).dt.date

        # Daily aggregation
        daily_summary = (
            predictions_df.groupby("Date")
            .agg(
                {
                    "Predicted Energy (kWh)": ["sum", "mean", "max"],
                    "Specific Energy (kWh/kWp)": "mean",
                    "Ranking": "mean",
                    "temperature_2m (°C)": "mean"
                    if "temperature_2m (°C)" in predictions_df.columns
                    else lambda _: np.nan,
                    "shortwave_radiation (W/m²)": "mean"
                    if "shortwave_radiation (W/m²)" in predictions_df.columns
                    else lambda _: np.nan,
                    "cloud_cover (%)": "mean"
                    if "cloud_cover (%)" in predictions_df.columns
                    else lambda _: np.nan,
                },
            )
            .round(2)
        )

        # Flatten column names
        daily_summary.columns = [
            "_".join(col).strip("_") if isinstance(col, tuple) else col
            for col in daily_summary.columns
        ]
        daily_summary = daily_summary.reset_index()

        return daily_summary

    def save_model(self, filepath):
        """
        Save trained model to file

        Args:
            filepath (str): Path to save the model
        """
        if not self.is_trained:
            logger.error("No trained model to save")
            return False

        try:
            model_data = {
                "installation": self.installation,
                "best_model": self.best_model,
                "best_model_name": self.best_model_name,
                "scaler": self.scaler,
                "feature_columns": self.feature_columns,
                "model_performance": self.model_performance,
            }

            joblib.dump(model_data, filepath)
            logger.info(f"Model saved to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

    def load_model(self, filepath):
        """
        Load trained model from file

        Args:
            filepath (str): Path to load the model from
        """
        try:
            model_data = joblib.load(filepath)

            self.installation = model_data.get("installation", self.installation)
            self.best_model = model_data["best_model"]
            self.best_model_name = model_data["best_model_name"]
            self.scaler = model_data["scaler"]
            self.feature_columns = model_data["feature_columns"]
            self.model_performance = model_data.get("model_performance", {})
            self.is_trained = True

            logger.info(f"Model loaded from {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False

    def get_feature_importance(self):
        """
        Get feature importance from the best model

        Returns:
            pd.DataFrame: Feature importance scores
        """
        if not self.is_trained or self.best_model is None:
            return pd.DataFrame()

        try:
            if hasattr(self.best_model, "feature_importances_"):
                importance_df = pd.DataFrame(
                    {
                        "feature": self.feature_columns,
                        "importance": self.best_model.feature_importances_,
                    },
                ).sort_values("importance", ascending=False)

                return importance_df
            else:
                logger.info("Model doesn't support feature importance")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error getting feature importance: {e}")
            return pd.DataFrame()
