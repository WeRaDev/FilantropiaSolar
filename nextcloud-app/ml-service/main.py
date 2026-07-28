"""
FilantropiaSolar ML Microservice

FastAPI application providing energy prediction and weather simulation endpoints.
Inherits ML logic from v1.2.x Python application.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import os
from pathlib import Path
from typing import Any

from constraints import (
    PRODUCTION_RADIATION_THRESHOLD,
    REFERENCE_TEMP,
    enforce_physical_constraints,
)
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from features import (
    ALL_FEATURES,
    align_features_to_training,
    enhance_features,
    prepare_features_for_prediction,
)
import httpx
import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from solar import calculate_solar_elevation, calculate_solar_elevations_batch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths from environment
MODEL_PATH = os.environ.get("MODEL_PATH", "/app/models")
DATA_PATH = os.environ.get("DATA_PATH", "/app/data")
WEATHER_PATH = os.environ.get("WEATHER_PATH", "/app/weather_files")

# Portuguese location coordinates (from v1.2.x)
LOCATION_COORDS = {
    "Lisbon": {"lat": 38.7223, "lon": -9.1393},
    "Setubal": {"lat": 38.5244, "lon": -8.8882},
    "Faro": {"lat": 37.0194, "lon": -7.9304},
    "Braga": {"lat": 41.5454, "lon": -8.4265},
    "Tavira": {"lat": 37.1279, "lon": -7.6486},
    "Loule": {"lat": 37.1376, "lon": -8.0197},
}

# Ensemble weights (from v1.2.x)
ENSEMBLE_WEIGHT_RF = 0.4
ENSEMBLE_WEIGHT_GB = 0.35
ENSEMBLE_WEIGHT_LINEAR = 0.25
GRID_PRICE_EUR_PER_KWH = 0.15
MINIMUM_TRAINING_SAMPLES = 200
DASHBOARD_CACHE_TTL_SECONDS = 900
MAX_SIMULATION_DAYS = 400
MIN_ENSEMBLE_MODELS = 2
MIN_RADIATION_FOR_PRODUCTION = 10.0  # W/m2 - simple-model zero-production cutoff
# Cloud cover thresholds (percent) for physics-based estimation
CLOUD_COVER_LOW_THRESHOLD = 20.0
CLOUD_COVER_MEDIUM_THRESHOLD = 50.0
CLOUD_COVER_HIGH_THRESHOLD = 80.0
CLOUD_COVER_REDUCTION_THRESHOLD = 50.0
# Specific-energy rank thresholds (kWh/kWp) for the 0-5 rank scale
DAILY_RANK_THRESHOLDS = (0.1, 0.3, 0.5, 0.7, 0.9)
HOURLY_RANK_THRESHOLDS = (0.01, 0.05, 0.10, 0.15, 0.20)


# Pydantic models for API
class WeatherDataPoint(BaseModel):
    timestamp: str
    temperature_2m: float
    relative_humidity_2m: float
    cloud_cover: float
    wind_speed_10m: float
    shortwave_radiation: float


class PredictionRequest(BaseModel):
    installation_id: str
    weather_data: list[WeatherDataPoint]
    capacity_kwp: float = Field(gt=0)
    latitude: float | None = None
    longitude: float | None = None


class PredictionResult(BaseModel):
    timestamp: str
    predicted_kwh: float
    specific_energy_kwh_kwp: float
    confidence: float


class PredictionResponse(BaseModel):
    predictions: list[PredictionResult]
    model_used: str
    feature_count: int


class WeatherSimulationRequest(BaseModel):
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    start_date: str
    end_date: str


class HealthResponse(BaseModel):
    status: str
    models_loaded: int
    locations_available: list[str]


class EstimateRequest(BaseModel):
    latitude: float
    longitude: float
    capacity_kwp: float = Field(gt=0)
    location: str | None = None


class EstimateResponse(BaseModel):
    annual_production_kwh: float
    annual_savings_eur: float
    specific_energy_kwh_kwp: float
    method: str


# Initialize FastAPI app
app = FastAPI(
    title="FilantropiaSolar ML Service",
    description="Energy prediction and weather simulation for solar installations",
    version="3.0.0",
)

# CORS middleware for Nextcloud integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model cache
_models_cache = {}
_scalers_cache = {}
_feature_names_cache = {}
_model_metrics_cache = {}
_model_name_cache = {}

# Data cache (loaded from Excel files)
_installations_cache: dict[str, dict[str, Any]] = {}
_energy_data_cache: dict[str, pd.DataFrame] = {}
_weather_data_cache: dict[str, pd.DataFrame] = {}
_dashboard_cache: dict[str, Any] = {"computed_at": None, "data": None}


@dataclass
class WeightedEnsembleRegressor:
    models: dict[str, Any]
    weights: dict[str, float]

    def predict(self, features: np.ndarray) -> np.ndarray:
        blended = np.zeros(len(features))
        for model_name, model in self.models.items():
            blended += self.weights[model_name] * model.predict(features)
        return blended


def load_model(installation_id: str) -> dict:
    """Load model from cache or disk."""
    if installation_id in _models_cache:
        return {
            "model": _models_cache[installation_id],
            "scaler": _scalers_cache.get(installation_id),
            "feature_names": _feature_names_cache.get(installation_id, ALL_FEATURES),
            "best_model_name": _model_name_cache.get(installation_id, "unknown"),
            "metrics": _model_metrics_cache.get(installation_id, {}),
        }

    model_file = Path(MODEL_PATH) / f"{installation_id}_model.joblib"
    if model_file.exists():
        try:
            bundle = joblib.load(model_file)
            _models_cache[installation_id] = bundle.get("model") or bundle.get(
                "best_model"
            )
            _scalers_cache[installation_id] = bundle.get("scaler")
            _feature_names_cache[installation_id] = bundle.get(
                "feature_names", ALL_FEATURES
            )
            _model_name_cache[installation_id] = bundle.get(
                "best_model_name", "unknown"
            )
            _model_metrics_cache[installation_id] = bundle.get("metrics", {})
            return {
                "model": _models_cache[installation_id],
                "scaler": _scalers_cache[installation_id],
                "feature_names": _feature_names_cache[installation_id],
                "best_model_name": _model_name_cache[installation_id],
                "metrics": _model_metrics_cache[installation_id],
            }
        except Exception as e:
            logger.error(f"Failed to load model for {installation_id}: {e}")

    return None


def create_fallback_prediction(
    weather_data: list[WeatherDataPoint],
    capacity_kwp: float,
) -> list[PredictionResult]:
    """
    Create rule-based fallback predictions when no ML model is available.
    Uses simplified physics-based estimation.
    """
    results = []

    for point in weather_data:
        radiation = point.shortwave_radiation
        cloud_factor = 1 - (point.cloud_cover / 100) * 0.75

        # Simple estimation: capacity * radiation/1000 * efficiency * cloud
        # Assumes 18% panel efficiency at STC
        estimated_kwh = capacity_kwp * (radiation / 1000) * 0.85 * cloud_factor

        # Zero at night (low radiation)
        if radiation < PRODUCTION_RADIATION_THRESHOLD:
            estimated_kwh = 0.0

        results.append(
            PredictionResult(
                timestamp=point.timestamp,
                predicted_kwh=max(0, estimated_kwh),
                specific_energy_kwh_kwp=max(0, estimated_kwh / capacity_kwp)
                if capacity_kwp > 0
                else 0,
                confidence=0.5,  # Lower confidence for fallback
            )
        )

    return results


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    model_count = len(_models_cache)

    # Check for models on disk
    model_dir = Path(MODEL_PATH)
    if model_dir.exists():
        model_files = [
            f.name for f in model_dir.iterdir() if f.name.endswith("_model.joblib")
        ]
        model_count = max(model_count, len(model_files))

    return HealthResponse(
        status="healthy",
        models_loaded=model_count,
        locations_available=list(LOCATION_COORDS.keys()),
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict_energy(request: PredictionRequest):
    """
    Generate energy predictions for an installation.

    Uses trained ML model if available, falls back to physics-based estimation.
    """
    # Determine location
    lat = request.latitude
    lon = request.longitude

    if lat is None or lon is None:
        # Default to Lisbon if no coordinates provided
        lat = LOCATION_COORDS["Lisbon"]["lat"]
        lon = LOCATION_COORDS["Lisbon"]["lon"]

    # Load model
    model_bundle = load_model(request.installation_id)

    if model_bundle is None or model_bundle.get("model") is None:
        # Use fallback prediction
        logger.info(f"No model for {request.installation_id}, using fallback")
        predictions = create_fallback_prediction(
            request.weather_data,
            request.capacity_kwp,
        )
        return PredictionResponse(
            predictions=predictions,
            model_used="fallback_physics",
            feature_count=5,
        )

    try:
        # Parse timestamps and calculate solar elevations
        timestamps = [
            datetime.fromisoformat(p.timestamp.replace("Z", "+00:00"))
            for p in request.weather_data
        ]
        solar_elevations = calculate_solar_elevations_batch(timestamps, lat, lon)

        # Prepare weather data as list of dicts
        weather_dicts = [p.model_dump() for p in request.weather_data]

        # Apply feature engineering
        features_df = prepare_features_for_prediction(weather_dicts, solar_elevations)

        # Align to training features
        expected_features = model_bundle.get("feature_names", ALL_FEATURES)
        features_df = align_features_to_training(features_df, expected_features)

        # Scale features if scaler available
        scaler = model_bundle.get("scaler")
        if scaler is not None:
            features_array = scaler.transform(features_df.values)
        else:
            features_array = features_df.values

        # Make predictions
        model = model_bundle["model"]
        raw_predictions = model.predict(features_array)

        # Apply physical constraints
        radiation = np.array([p.shortwave_radiation for p in request.weather_data])
        cloud_cover = np.array([p.cloud_cover for p in request.weather_data])
        temperature = np.array([p.temperature_2m for p in request.weather_data])

        constrained = enforce_physical_constraints(
            raw_predictions,
            radiation,
            cloud_cover,
            temperature,
        )

        # Scale by capacity (model predicts per kWp)
        final_predictions = constrained * request.capacity_kwp

        # Build response
        results = []
        for i, point in enumerate(request.weather_data):
            kwh = float(final_predictions[i])
            results.append(
                PredictionResult(
                    timestamp=point.timestamp,
                    predicted_kwh=kwh,
                    specific_energy_kwh_kwp=kwh / request.capacity_kwp
                    if request.capacity_kwp > 0
                    else 0,
                    confidence=0.85,  # Higher confidence for ML model
                )
            )

        return PredictionResponse(
            predictions=results,
            model_used="ensemble_ml",
            feature_count=len(expected_features),
        )

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        # Fall back to physics-based on error
        predictions = create_fallback_prediction(
            request.weather_data,
            request.capacity_kwp,
        )
        return PredictionResponse(
            predictions=predictions,
            model_used="fallback_error",
            feature_count=5,
        )


@app.post("/simulate-weather")
async def simulate_weather(request: WeatherSimulationRequest):
    """
    Generate simulated weather data for future dates.

    Uses historical patterns from known Portuguese locations.
    """
    # Determine location
    if request.location and request.location in LOCATION_COORDS:
        coords = LOCATION_COORDS[request.location]
        lat, lon = coords["lat"], coords["lon"]
    elif request.latitude is not None and request.longitude is not None:
        lat, lon = request.latitude, request.longitude
        # Find nearest known location
        request.location = min(
            LOCATION_COORDS.keys(),
            key=lambda k: (
                (LOCATION_COORDS[k]["lat"] - lat) ** 2
                + (LOCATION_COORDS[k]["lon"] - lon) ** 2
            ),
        )
    else:
        raise HTTPException(400, "Must provide location name or coordinates")

    # Parse dates
    try:
        start = datetime.fromisoformat(request.start_date)
        end = datetime.fromisoformat(request.end_date)
    except ValueError:
        raise HTTPException(
            400, "Invalid date format. Use ISO format (YYYY-MM-DD)"
        ) from None

    if end < start:
        raise HTTPException(400, "end_date must be after start_date")

    if (end - start).days > MAX_SIMULATION_DAYS:
        raise HTTPException(
            400, f"Maximum simulation period is {MAX_SIMULATION_DAYS} days"
        )

    # Generate synthetic weather based on seasonal patterns
    # This is a simplified simulation - real implementation would use KNN from historical data
    results = []
    current = start

    while current <= end:
        for hour in range(24):
            timestamp = current.replace(hour=hour)
            day_of_year = timestamp.timetuple().tm_yday

            # Seasonal temperature pattern (Portugal)
            base_temp = 15 + 10 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
            temp_variation = 5 * np.sin(2 * np.pi * hour / 24 - np.pi / 2)
            temperature = base_temp + temp_variation + np.random.normal(0, 2)

            # Solar radiation pattern
            solar_elev = calculate_solar_elevation(timestamp, lat, lon)
            if solar_elev > 0:
                # Clear sky radiation approximation
                radiation = 1000 * np.sin(np.radians(solar_elev))
                # Add some variability
                radiation *= 0.8 + 0.4 * np.random.random()
            else:
                radiation = 0

            # Cloud cover (more variability)
            cloud_base = 30 + 20 * np.sin(2 * np.pi * day_of_year / 365)
            cloud_cover = max(0, min(100, cloud_base + np.random.normal(0, 20)))

            # Reduce radiation by cloud cover
            if cloud_cover > CLOUD_COVER_REDUCTION_THRESHOLD:
                radiation *= 1 - (cloud_cover - CLOUD_COVER_REDUCTION_THRESHOLD) / 100

            # Humidity
            humidity = 60 + 20 * np.sin(2 * np.pi * hour / 24 + np.pi)
            humidity = max(20, min(100, humidity + np.random.normal(0, 10)))

            # Wind
            wind = 3 + 5 * np.random.random()

            results.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "temperature_2m": round(temperature, 1),
                    "relative_humidity_2m": round(humidity, 1),
                    "cloud_cover": round(cloud_cover, 1),
                    "wind_speed_10m": round(wind, 1),
                    "shortwave_radiation": round(max(0, radiation), 1),
                }
            )

        current += timedelta(days=1)

    return results


@app.get("/locations")
async def get_locations():
    """Get available Portuguese locations with coordinates."""
    return LOCATION_COORDS


@app.post("/train")
async def train_all_models():
    """Train models for all dataset installations and persist bundles to MODEL_PATH."""
    installations = load_installations_from_excel()
    if not installations:
        raise HTTPException(404, "No installations available for training")

    trained = {}
    failed = {}
    for installation_id in installations:
        try:
            trained[installation_id] = train_single_installation(installation_id)
        except Exception as exc:
            failed[installation_id] = str(exc)
            logger.error("Training failed for %s: %s", installation_id, exc)

    if not trained:
        raise HTTPException(
            500, {"message": "Training failed for all installations", "failed": failed}
        )

    _refresh_dashboard_cache(force=True)
    return {
        "success": True,
        "trained_count": len(trained),
        "failed_count": len(failed),
        "trained_models": trained,
        "failed_models": failed,
    }


@app.post("/train/{installation_id}")
async def train_one_model(installation_id: str):
    """Retrain one installation model and persist to MODEL_PATH."""
    installations = load_installations_from_excel()
    if installation_id not in installations:
        raise HTTPException(404, f"Installation not found: {installation_id}")

    result = train_single_installation(installation_id)
    return {"success": True, "trained_model": result}


@app.post("/estimate", response_model=EstimateResponse)
async def estimate_annual_production(request: EstimateRequest):
    """
    Estimate annual production and savings for a virtual station.
    Uses nearest trained model when available, otherwise physics fallback.
    """
    location = request.location or "Lisbon"
    if location not in LOCATION_COORDS:
        location = min(
            LOCATION_COORDS.keys(),
            key=lambda key: (
                (LOCATION_COORDS[key]["lat"] - request.latitude) ** 2
                + (LOCATION_COORDS[key]["lon"] - request.longitude) ** 2
            ),
        )

    weather_df = load_weather_data(location)
    if weather_df.empty:
        start_date = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        weather_df = generate_synthetic_weather(location, start_date, 365)
    else:
        weather_df = _normalize_weather_columns(weather_df)
        if "timestamp" not in weather_df.columns and "date" in weather_df.columns:
            weather_df["timestamp"] = pd.to_datetime(
                weather_df["date"], errors="coerce"
            )
        weather_df = weather_df.dropna(subset=["timestamp"]).sort_values("timestamp")
        if len(weather_df) > 24 * 365:
            weather_df = weather_df.tail(24 * 365).copy()

    nearest_model_installation = _nearest_installation_with_model(
        request.latitude, request.longitude
    )
    model_bundle = (
        load_model(nearest_model_installation) if nearest_model_installation else None
    )
    annual_production_kwh: float
    method: str

    if model_bundle and model_bundle.get("model"):
        weather_records = []
        for _, row in weather_df.iterrows():
            weather_records.append(
                {
                    "timestamp": pd.to_datetime(row["timestamp"]).isoformat(),
                    "temperature_2m": float(row.get("temperature_2m", 20.0)),
                    "relative_humidity_2m": float(
                        row.get("relative_humidity_2m", 60.0)
                    ),
                    "cloud_cover": float(row.get("cloud_cover", 35.0)),
                    "wind_speed_10m": float(row.get("wind_speed_10m", 4.0)),
                    "shortwave_radiation": float(row.get("shortwave_radiation", 200.0)),
                }
            )
        solar_elevations = calculate_solar_elevations_batch(
            [datetime.fromisoformat(rec["timestamp"]) for rec in weather_records],
            request.latitude,
            request.longitude,
        )
        features_df = prepare_features_for_prediction(weather_records, solar_elevations)
        expected_features = model_bundle.get("feature_names", ALL_FEATURES)
        features_df = align_features_to_training(features_df, expected_features)
        scaler = model_bundle.get("scaler")
        feature_matrix = (
            scaler.transform(features_df.values)
            if scaler is not None
            else features_df.values
        )

        raw_predictions = model_bundle["model"].predict(feature_matrix)
        constrained = enforce_physical_constraints(
            raw_predictions,
            features_df["shortwave_radiation"].to_numpy(),
            features_df["cloud_cover"].to_numpy(),
            features_df["temperature_2m"].to_numpy(),
        )
        annual_production_kwh = float(
            np.clip(constrained, 0, None).sum() * request.capacity_kwp
        )
        method = f"ml:{nearest_model_installation}"
    else:
        annual_production_kwh = 0.0
        for _, row in weather_df.iterrows():
            annual_production_kwh += predict_production_simple(
                request.capacity_kwp,
                float(row.get("shortwave_radiation", 200.0)),
                float(row.get("cloud_cover", 35.0)),
                float(row.get("temperature_2m", 20.0)),
            )
        method = "physics_fallback"

    specific_energy = annual_production_kwh / request.capacity_kwp
    return EstimateResponse(
        annual_production_kwh=round(annual_production_kwh, 2),
        annual_savings_eur=round(annual_production_kwh * GRID_PRICE_EUR_PER_KWH, 2),
        specific_energy_kwh_kwp=round(specific_energy, 4),
        method=method,
    )


# ============================================================================
# DATA LOADING ENDPOINTS (v3.0.1 - Load from Mendeley Dataset)
# ============================================================================


def load_installations_from_excel() -> dict[str, dict[str, Any]]:
    """
    Load PV plant metadata from the Mendeley dataset Excel file.
    Returns dict keyed by installation_id (location_serialnumber).
    """
    if _installations_cache:
        return _installations_cache

    metadata_file = Path(DATA_PATH) / "PV Plants Metadata.xlsx"
    if not metadata_file.exists():
        logger.warning(f"Metadata file not found: {metadata_file}")
        return {}

    try:
        # Read Excel with header on row 2 (index 1)
        df = pd.read_excel(metadata_file, header=1)
        df = df.dropna(how="all").reset_index(drop=True)
        df.columns = df.columns.str.strip()

        logger.info(f"Loading metadata for {len(df)} installations")

        for _, row in df.iterrows():
            try:
                serial_number = str(int(row["PV Serial Number"]))
                location = str(row["Location"]).strip()
                installation_id = f"{location}_{serial_number}"

                _installations_cache[installation_id] = {
                    "id": installation_id,
                    "serial_number": serial_number,
                    "name": f"{location} PV Plant",
                    "location": location,
                    "latitude": float(row["Latitude"]),
                    "longitude": float(row["Longitude"]),
                    "capacity_kwp": float(row["Installed Power (kWp)"]),
                    "connection_power_kwn": float(row["Connection Power (kWn)"]),
                    "from_date": pd.to_datetime(row["From date"]).isoformat(),
                    "to_date": pd.to_datetime(row["To date"]).isoformat(),
                }
                logger.info(f"Loaded installation: {installation_id}")
            except Exception as e:
                logger.error(f"Error processing row: {e}")
                continue

        logger.info(f"Successfully loaded {len(_installations_cache)} installations")

    except Exception as e:
        logger.error(f"Error loading metadata: {e}")

    return _installations_cache


def load_energy_data_for_installation(installation_id: str) -> pd.DataFrame:
    """
    Load energy production data for a specific installation from Excel.
    Data is in separate sheets named by serial number.
    """
    if installation_id in _energy_data_cache:
        return _energy_data_cache[installation_id]

    # Get serial number from installation_id
    installations = load_installations_from_excel()
    if installation_id not in installations:
        return pd.DataFrame()

    serial_number = installations[installation_id]["serial_number"]
    datasets_file = Path(DATA_PATH) / "PV Plants Datasets.xlsx"

    if not datasets_file.exists():
        logger.warning(f"Datasets file not found: {datasets_file}")
        return pd.DataFrame()

    try:
        # Read the sheet with this serial number
        df = pd.read_excel(datasets_file, sheet_name=serial_number)

        # Standardize column names
        df.columns = df.columns.str.strip()

        # Parse date column
        if "Date" in df.columns:
            df["timestamp"] = pd.to_datetime(df["Date"])
        elif "date" in df.columns:
            df["timestamp"] = pd.to_datetime(df["date"])

        # Rename energy column
        energy_cols = [c for c in df.columns if "Produced" in c or "Energy" in c]
        if energy_cols:
            df["produced_kwh"] = df[energy_cols[0]].fillna(0)

        # Specific energy column
        specific_cols = [c for c in df.columns if "Specific" in c]
        if specific_cols:
            df["specific_energy_kwh_kwp"] = df[specific_cols[0]].fillna(0)

        # Sort by timestamp
        df = df.sort_values("timestamp").reset_index(drop=True)

        _energy_data_cache[installation_id] = df
        logger.info(f"Loaded {len(df)} energy readings for {installation_id}")

        return df

    except Exception as e:
        logger.error(f"Error loading energy data for {installation_id}: {e}")
        return pd.DataFrame()


def load_weather_data(location: str) -> pd.DataFrame:
    """
    Load historical weather data for a location.
    """
    if location in _weather_data_cache:
        return _weather_data_cache[location]

    weather_file = Path(WEATHER_PATH) / f"{location}_weather.csv"
    if not weather_file.exists():
        logger.warning(f"Weather file not found: {weather_file}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(weather_file)
        df["timestamp"] = pd.to_datetime(df["date"])
        _weather_data_cache[location] = df
        logger.info(f"Loaded {len(df)} weather records for {location}")
        return df
    except Exception as e:
        logger.error(f"Error loading weather data for {location}: {e}")
        return pd.DataFrame()


def _normalize_weather_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize weather/energy column names to expected schema."""
    normalized = df.copy()
    column_map = {col.lower().strip(): col for col in normalized.columns}

    aliases = {
        "temperature_2m": [
            "temperature_2m",
            "temperature",
            "temp",
            "air_temperature",
        ],
        "relative_humidity_2m": [
            "relative_humidity_2m",
            "relative_humidity",
            "humidity",
        ],
        "cloud_cover": ["cloud_cover", "cloudiness"],
        "wind_speed_10m": ["wind_speed_10m", "wind_speed", "wind"],
        "shortwave_radiation": [
            "shortwave_radiation",
            "solar_radiation",
            "radiation",
            "irradiance",
        ],
    }

    for canonical, options in aliases.items():
        if canonical in normalized.columns:
            continue
        for option in options:
            source = column_map.get(option)
            if source and source in normalized.columns:
                normalized[canonical] = normalized[source]
                break

    return normalized


def _build_training_frame(installation_id: str) -> pd.DataFrame | None:
    """Build aligned training dataframe for one installation."""
    installations = load_installations_from_excel()
    installation = installations.get(installation_id)
    if installation is None:
        return None

    energy_df = load_energy_data_for_installation(installation_id)
    if energy_df.empty or "timestamp" not in energy_df.columns:
        return None

    df = _normalize_weather_columns(energy_df)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")

    if "produced_kwh" not in df.columns:
        if "specific_energy_kwh_kwp" in df.columns:
            df["produced_kwh"] = pd.to_numeric(
                df["specific_energy_kwh_kwp"], errors="coerce"
            ) * float(installation["capacity_kwp"])
        else:
            return None

    if "specific_energy_kwh_kwp" not in df.columns:
        df["specific_energy_kwh_kwp"] = pd.to_numeric(
            df["produced_kwh"], errors="coerce"
        ) / float(installation["capacity_kwp"])

    for weather_col, default_value in (
        ("temperature_2m", 20.0),
        ("relative_humidity_2m", 60.0),
        ("cloud_cover", 35.0),
        ("wind_speed_10m", 4.0),
        ("shortwave_radiation", 200.0),
    ):
        if weather_col not in df.columns:
            df[weather_col] = default_value
        df[weather_col] = pd.to_numeric(df[weather_col], errors="coerce").fillna(
            default_value
        )

    coords = (installation["latitude"], installation["longitude"])
    solar_elevations = calculate_solar_elevations_batch(
        list(df["timestamp"]),
        float(coords[0]),
        float(coords[1]),
    )

    df["hour"] = df["timestamp"].dt.hour
    df["day_of_year"] = df["timestamp"].dt.dayofyear
    df["month"] = df["timestamp"].dt.month
    df["solar_elevation"] = solar_elevations
    df = df.set_index("timestamp")

    features = enhance_features(
        df[
            [
                "temperature_2m",
                "relative_humidity_2m",
                "cloud_cover",
                "wind_speed_10m",
                "shortwave_radiation",
                "hour",
                "day_of_year",
                "month",
                "solar_elevation",
            ]
        ]
    )
    target = pd.to_numeric(df["specific_energy_kwh_kwp"], errors="coerce").fillna(0.0)

    frame = features.copy()
    frame["target_specific_energy"] = target
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna()
    return frame


def _create_ensemble(
    trained_models: dict[str, Any],
    metrics: dict[str, dict[str, float]],
) -> WeightedEnsembleRegressor | None:
    available = {
        name: trained_models[name]
        for name in ("random_forest", "gradient_boost", "linear")
        if name in trained_models
    }
    if len(available) < MIN_ENSEMBLE_MODELS:
        return None

    raw_weights = {}
    for name in available:
        baseline_weight = {
            "random_forest": ENSEMBLE_WEIGHT_RF,
            "gradient_boost": ENSEMBLE_WEIGHT_GB,
            "linear": ENSEMBLE_WEIGHT_LINEAR,
        }[name]
        quality = max(metrics[name]["r2"], 0.01)
        raw_weights[name] = baseline_weight * quality

    total = sum(raw_weights.values())
    if total <= 0:
        return None

    return WeightedEnsembleRegressor(
        models=available,
        weights={name: value / total for name, value in raw_weights.items()},
    )


def train_single_installation(installation_id: str) -> dict[str, Any]:
    """Train one installation model and persist model bundle to disk."""
    frame = _build_training_frame(installation_id)
    if frame is None or len(frame) < MINIMUM_TRAINING_SAMPLES:
        raise HTTPException(
            400,
            f"Insufficient training data for {installation_id}; need at least {MINIMUM_TRAINING_SAMPLES} rows",
        )

    features = frame[ALL_FEATURES]
    target = frame["target_specific_energy"]
    X_train, X_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.2,
        random_state=42,
        shuffle=True,
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    candidates = {
        "random_forest": RandomForestRegressor(
            n_estimators=200,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        ),
        "gradient_boost": GradientBoostingRegressor(random_state=42),
        "linear": LinearRegression(),
    }

    trained_models: dict[str, Any] = {}
    metrics: dict[str, dict[str, float]] = {}

    for model_name, template in candidates.items():
        model = clone(template)
        model.fit(X_train_scaled, y_train)
        preds = model.predict(X_test_scaled)
        metrics[model_name] = {
            "r2": float(r2_score(y_test, preds)),
            "mae": float(mean_absolute_error(y_test, preds)),
            "feature_count": len(ALL_FEATURES),
            "model_used": model_name,
        }
        trained_models[model_name] = model

    ensemble_model = _create_ensemble(trained_models, metrics)
    if ensemble_model:
        ensemble_preds = ensemble_model.predict(X_test_scaled)
        metrics["ensemble"] = {
            "r2": float(r2_score(y_test, ensemble_preds)),
            "mae": float(mean_absolute_error(y_test, ensemble_preds)),
            "feature_count": len(ALL_FEATURES),
            "model_used": "ensemble",
        }
        trained_models["ensemble"] = ensemble_model

    best_model_name = max(metrics.keys(), key=lambda key: metrics[key]["r2"])
    best_model = trained_models[best_model_name]

    Path(MODEL_PATH).mkdir(parents=True, exist_ok=True)
    model_file = Path(MODEL_PATH) / f"{installation_id}_model.joblib"
    joblib.dump(
        {
            "model": best_model,
            "best_model_name": best_model_name,
            "all_models": trained_models,
            "scaler": scaler,
            "feature_names": list(ALL_FEATURES),
            "metrics": metrics,
            "trained_at": datetime.utcnow().isoformat(),
        },
        model_file,
    )

    _models_cache[installation_id] = best_model
    _scalers_cache[installation_id] = scaler
    _feature_names_cache[installation_id] = list(ALL_FEATURES)
    _model_metrics_cache[installation_id] = metrics
    _model_name_cache[installation_id] = best_model_name

    return {
        "installation_id": installation_id,
        "best_model": best_model_name,
        "metrics": metrics,
    }


def _nearest_installation_with_model(latitude: float, longitude: float) -> str | None:
    """Find nearest installation that has an available trained model."""
    installations = load_installations_from_excel()
    nearest_id: str | None = None
    nearest_distance = float("inf")

    for inst_id, inst in installations.items():
        bundle = load_model(inst_id)
        if not bundle or not bundle.get("model"):
            continue
        distance = (float(inst["latitude"]) - latitude) ** 2 + (
            float(inst["longitude"]) - longitude
        ) ** 2
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_id = inst_id

    return nearest_id


def _build_dashboard_payload() -> dict[str, Any]:
    """Build dashboard aggregate payload from cached dataset metadata/readings."""
    installations = load_installations_from_excel()
    total_capacity = sum(i["capacity_kwp"] for i in installations.values())
    total_production = 0.0

    for inst_id in installations:
        df = load_energy_data_for_installation(inst_id)
        if not df.empty and "produced_kwh" in df.columns:
            total_production += float(
                pd.to_numeric(df["produced_kwh"], errors="coerce").fillna(0).sum()
            )

    location_stats: dict[str, dict[str, Any]] = {}
    for inst in installations.values():
        location = inst["location"]
        if location not in location_stats:
            location_stats[location] = {
                "name": location,
                "lat": inst["latitude"],
                "lon": inst["longitude"],
                "count": 0,
                "capacity_kwp": 0.0,
            }
        location_stats[location]["count"] += 1
        location_stats[location]["capacity_kwp"] += inst["capacity_kwp"]

    return {
        "total_installations": len(installations),
        "total_capacity_kwp": round(total_capacity, 2),
        "total_production_kwh": round(total_production, 2),
        "total_savings_eur": round(total_production * GRID_PRICE_EUR_PER_KWH, 2),
        "locations": list(location_stats.values()),
    }


def _refresh_dashboard_cache(force: bool = False) -> dict[str, Any]:
    computed_at = _dashboard_cache.get("computed_at")
    if (
        not force
        and computed_at is not None
        and (datetime.utcnow() - computed_at).total_seconds()
        < DASHBOARD_CACHE_TTL_SECONDS
        and _dashboard_cache.get("data") is not None
    ):
        return _dashboard_cache["data"]

    payload = _build_dashboard_payload()
    _dashboard_cache["computed_at"] = datetime.utcnow()
    _dashboard_cache["data"] = payload
    return payload


@app.get("/data/installations")
async def get_installations():
    """
    Get all PV installations from the Mendeley dataset.
    Returns installation metadata with locations and capacities.
    """
    installations = load_installations_from_excel()
    return {
        "installations": list(installations.values()),
        "count": len(installations),
    }


@app.get("/data/installations/{installation_id}")
async def get_installation(installation_id: str):
    """
    Get details for a specific installation.
    """
    installations = load_installations_from_excel()
    if installation_id not in installations:
        raise HTTPException(404, f"Installation not found: {installation_id}")
    return installations[installation_id]


@app.get("/data/installations/{installation_id}/readings")
async def get_installation_readings(
    installation_id: str,
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(504, description="Max records (default 21 days * 24 hours)"),
):
    """
    Get energy readings for an installation within a date range.
    Default returns 21 days centered around latest data.
    """
    df = load_energy_data_for_installation(installation_id)
    if df.empty:
        raise HTTPException(404, f"No data found for installation: {installation_id}")

    # Filter by date range if provided
    if start_date:
        start = pd.to_datetime(start_date)
        df = df[df["timestamp"] >= start]
    if end_date:
        end = pd.to_datetime(end_date)
        df = df[df["timestamp"] <= end]

    # Limit results
    df = df.tail(limit)

    # Convert to list of dicts
    readings = []
    for _, row in df.iterrows():
        readings.append(
            {
                "timestamp": row["timestamp"].isoformat(),
                "produced_kwh": float(row.get("produced_kwh", 0)),
                "specific_energy_kwh_kwp": float(row.get("specific_energy_kwh_kwp", 0)),
            }
        )

    return {
        "installation_id": installation_id,
        "readings": readings,
        "count": len(readings),
    }


@app.get("/data/installations/{installation_id}/stats")
async def get_installation_stats(installation_id: str):
    """
    Get summary statistics for an installation.
    """
    installations = load_installations_from_excel()
    if installation_id not in installations:
        raise HTTPException(404, f"Installation not found: {installation_id}")

    df = load_energy_data_for_installation(installation_id)
    if df.empty:
        return {
            "installation_id": installation_id,
            "total_production_kwh": 0,
            "avg_daily_production_kwh": 0,
            "data_days": 0,
        }

    total_kwh = df["produced_kwh"].sum() if "produced_kwh" in df.columns else 0

    # Calculate days of data
    if "timestamp" in df.columns and len(df) > 1:
        date_range = (df["timestamp"].max() - df["timestamp"].min()).days + 1
    else:
        date_range = 1

    avg_daily = total_kwh / date_range if date_range > 0 else 0

    installation = installations[installation_id]
    grid_price = 0.15  # EUR/kWh default
    total_savings = total_kwh * grid_price

    return {
        "installation_id": installation_id,
        "capacity_kwp": installation["capacity_kwp"],
        "total_production_kwh": round(total_kwh, 2),
        "avg_daily_production_kwh": round(avg_daily, 2),
        "total_savings_eur": round(total_savings, 2),
        "data_days": date_range,
        "from_date": installation["from_date"],
        "to_date": installation["to_date"],
    }


@app.get("/data/dashboard")
async def get_dashboard_stats():
    """
    Get network-wide dashboard statistics.
    """
    return _refresh_dashboard_cache()


@app.get("/data/weather/{location}")
async def get_weather_history(
    location: str,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Get historical weather data for a location.
    """
    df = load_weather_data(location)
    if df.empty:
        raise HTTPException(404, f"No weather data for location: {location}")

    if start_date:
        df = df[df["timestamp"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["timestamp"] <= pd.to_datetime(end_date)]

    # Return subset of columns
    cols = [
        "timestamp",
        "temperature_2m",
        "relative_humidity_2m",
        "cloud_cover",
        "wind_speed_10m",
        "shortwave_radiation",
    ]
    available_cols = [c for c in cols if c in df.columns]

    return df[available_cols].to_dict(orient="records")


# ===== Period Prediction Endpoints (v3.0.2) =====


class PeriodPredictionRequest(BaseModel):
    """Request for generating 21-day analysis."""

    mode: str  # 'historical' or 'simulation' or 'custom'
    installation_id: str | None = None
    center_date: str  # YYYY-MM-DD
    days: int = 21
    # For custom station simulation
    location: str | None = None
    capacity_kwp: float | None = None


class HourlyData(BaseModel):
    timestamp: str
    hour: int
    production_kwh: float
    specific_energy: float  # kWh/kWp for this hour
    rank: int  # 0-5 performance ranking based on specific energy
    temperature: float | None = None
    humidity: float | None = None
    cloud_cover: float | None = None
    wind_speed: float | None = None
    radiation: float | None = None


class DailyData(BaseModel):
    date: str
    total_production_kwh: float
    specific_energy_kwh_kwp: float  # Daily kWh/kWp
    avg_production_kwh: float
    peak_hour: int
    peak_production_kwh: float
    rank: int  # 0-5 ranking based on daily specific energy
    avg_temperature: float | None = None
    avg_humidity: float | None = None
    avg_cloud_cover: float | None = None
    avg_wind_speed: float | None = None
    avg_radiation: float | None = None


class PeriodPredictionResponse(BaseModel):
    success: bool
    installation_info: dict
    period_statistics: dict
    daily_data: list[DailyData]
    hourly_data: list[HourlyData]
    weather_source: str | None = (
        None  # 'api', 'historical_file', 'synthetic', 'measured'
    )
    model_info: dict | None = None
    error: str | None = None


def calculate_energy_rank(specific_energy: float) -> int:
    """
    Calculate energy rank (0-5) based on specific energy (kWh/kWp).

    Thresholds (per day for daily, per hour for hourly):
    - R0: < 0.1 kWh/kWp (Zero/negligible - excluded from charts)
    - R1: 0.1 - 0.3 kWh/kWp (Poor - red)
    - R2: 0.3 - 0.5 kWh/kWp (Below Avg - orange)
    - R3: 0.5 - 0.7 kWh/kWp (Average - yellow)
    - R4: 0.7 - 0.9 kWh/kWp (Good - green)
    - R5: > 0.9 kWh/kWp (Excellent - light-blue)

    For hourly data, thresholds are divided by 24 (per-hour basis).
    """
    for rank, threshold in enumerate(DAILY_RANK_THRESHOLDS):
        if specific_energy < threshold:
            return rank
    return 5  # R5: Excellent


def calculate_hourly_rank(specific_energy_hourly: float) -> int:
    """
    Calculate rank for hourly data.
    Peak solar hours produce ~0.15-0.20 kWh/kWp per hour in good conditions.
    Thresholds adjusted for hourly granularity.
    """
    # Hourly thresholds (roughly daily / 8 peak hours)
    for rank, threshold in enumerate(HOURLY_RANK_THRESHOLDS):
        if specific_energy_hourly < threshold:
            return rank
    return 5  # R5: Excellent


async def fetch_weather_from_api(
    lat: float,
    lon: float,
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame | None:
    """
    Fetch weather data from Open-Meteo API.
    Returns DataFrame with hourly weather data, or None if API fails.
    """
    try:
        # Open-Meteo API for historical and forecast data
        # Use archive for past dates, forecast for future
        today = datetime.now().date()

        # Determine which API to use
        if end_date.date() <= today:
            # All dates in past - use archive API
            base_url = "https://archive-api.open-meteo.com/v1/archive"
        elif start_date.date() > today:
            # All dates in future - use forecast API
            base_url = "https://api.open-meteo.com/v1/forecast"
        else:
            # Mixed - we'll use forecast which includes recent past
            base_url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "hourly": "temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m,shortwave_radiation",
            "timezone": "Europe/Lisbon",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

        if "hourly" not in data:
            logger.warning("No hourly data in API response")
            return None

        hourly = data["hourly"]
        timestamps = pd.to_datetime(hourly["time"])

        df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "temperature_2m": hourly.get(
                    "temperature_2m", [20.0] * len(timestamps)
                ),
                "relative_humidity_2m": hourly.get(
                    "relative_humidity_2m", [60.0] * len(timestamps)
                ),
                "cloud_cover": hourly.get("cloud_cover", [30.0] * len(timestamps)),
                "wind_speed_10m": hourly.get("wind_speed_10m", [5.0] * len(timestamps)),
                "shortwave_radiation": hourly.get(
                    "shortwave_radiation", [200.0] * len(timestamps)
                ),
            }
        )

        # Fill any None/NaN values
        df = df.fillna(
            {
                "temperature_2m": 20.0,
                "relative_humidity_2m": 60.0,
                "cloud_cover": 30.0,
                "wind_speed_10m": 5.0,
                "shortwave_radiation": 200.0,
            }
        )

        logger.info(f"Fetched {len(df)} hours of weather data from Open-Meteo API")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch weather from API: {e}")
        return None


def generate_synthetic_weather(
    location: str,
    start_date: datetime,
    days: int,
) -> pd.DataFrame:
    """
    Generate synthetic weather data based on seasonal patterns.
    Fallback when API is unavailable.
    """
    timestamps = []
    for day_offset in range(days):
        date = start_date + timedelta(days=day_offset)
        for hour in range(24):
            timestamps.append(date.replace(hour=hour))

    result_data = []
    coords = LOCATION_COORDS.get(location, LOCATION_COORDS["Lisbon"])

    for ts in timestamps:
        solar_elev = calculate_solar_elevation(ts, coords["lat"], coords["lon"])

        # Improved radiation model based on solar elevation
        if solar_elev > 0:
            # Clear-sky radiation using more realistic formula
            air_mass = 1 / (
                np.sin(np.radians(solar_elev)) + 0.15 * (solar_elev + 3.885) ** (-1.253)
            )
            clear_sky_radiation = (
                1361 * 0.7 ** (air_mass**0.678) * np.sin(np.radians(solar_elev))
            )
        else:
            clear_sky_radiation = 0

        # Add seasonal cloud variability
        month = ts.month
        hour = ts.hour

        # Portugal seasonal cloud patterns (more clouds in winter)
        seasonal_cloud_base = 40 + 25 * np.cos(
            (month - 1) * np.pi / 6
        )  # Higher in winter
        cloud_variation = np.random.normal(0, 15)
        cloud_cover = max(0, min(100, seasonal_cloud_base + cloud_variation))

        # Apply cloud factor to radiation
        cloud_factor = 1 - (cloud_cover / 100) * 0.75
        radiation = clear_sky_radiation * cloud_factor

        # Temperature model with better seasonal variation for Portugal
        base_temp = 14 + 8 * np.sin(
            (month - 4) * np.pi / 6
        )  # Seasonal (peaks in summer)
        daily_variation = 5 * np.sin((hour - 6) * np.pi / 12)  # Daily cycle
        temp = base_temp + daily_variation + np.random.normal(0, 2)

        # Humidity (inverse of temperature, higher at night and in winter)
        humidity = (
            65
            - 15 * np.sin((month - 4) * np.pi / 6)
            + 10 * np.sin((hour - 14) * np.pi / 12)
        )
        humidity = max(30, min(95, humidity + np.random.normal(0, 5)))

        result_data.append(
            {
                "timestamp": ts,
                "temperature_2m": round(temp, 1),
                "relative_humidity_2m": round(humidity, 1),
                "cloud_cover": round(cloud_cover, 1),
                "wind_speed_10m": round(3 + 4 * np.random.random(), 1),
                "shortwave_radiation": round(max(0, radiation), 1),
            }
        )

    return pd.DataFrame(result_data)


async def generate_weather_for_period(
    location: str,
    start_date: datetime,
    days: int,
) -> pd.DataFrame:
    """
    Generate weather data for prediction period.
    Priority: 1) Open-Meteo API, 2) Historical files, 3) Synthetic generation
    """
    end_date = start_date + timedelta(days=days - 1)
    coords = LOCATION_COORDS.get(location, LOCATION_COORDS["Lisbon"])

    # Try Open-Meteo API first
    api_weather = await fetch_weather_from_api(
        coords["lat"],
        coords["lon"],
        start_date,
        end_date,
    )

    if (
        api_weather is not None and len(api_weather) >= days * 20
    ):  # At least 20 hours per day
        logger.info(f"Using Open-Meteo API weather data for {location}")
        api_weather.attrs["weather_source"] = "api"
        return api_weather

    # Try historical weather files
    weather_df = load_weather_data(location)
    if not weather_df.empty:
        # Try to match historical data by day-of-year
        timestamps = []
        for day_offset in range(days):
            date = start_date + timedelta(days=day_offset)
            for hour in range(24):
                timestamps.append(date.replace(hour=hour))

        result_data = []
        for ts in timestamps:
            doy = ts.timetuple().tm_yday
            hour = ts.hour

            similar = weather_df[
                (weather_df["timestamp"].dt.dayofyear == doy)
                & (weather_df["timestamp"].dt.hour == hour)
            ]

            if len(similar) > 0:
                result_data.append(
                    {
                        "timestamp": ts,
                        "temperature_2m": similar["temperature_2m"].mean()
                        if "temperature_2m" in similar.columns
                        else 20.0,
                        "relative_humidity_2m": similar["relative_humidity_2m"].mean()
                        if "relative_humidity_2m" in similar.columns
                        else 60.0,
                        "cloud_cover": similar["cloud_cover"].mean()
                        if "cloud_cover" in similar.columns
                        else 30.0,
                        "wind_speed_10m": similar["wind_speed_10m"].mean()
                        if "wind_speed_10m" in similar.columns
                        else 5.0,
                        "shortwave_radiation": similar["shortwave_radiation"].mean()
                        if "shortwave_radiation" in similar.columns
                        else 200.0,
                    }
                )
            else:
                # Fill gaps with synthetic
                solar_elev = calculate_solar_elevation(ts, coords["lat"], coords["lon"])
                radiation = max(0, solar_elev * 12) if solar_elev > 0 else 0
                result_data.append(
                    {
                        "timestamp": ts,
                        "temperature_2m": 15.0,
                        "relative_humidity_2m": 60.0,
                        "cloud_cover": 40.0,
                        "wind_speed_10m": 5.0,
                        "shortwave_radiation": radiation,
                    }
                )

        if result_data:
            logger.info(f"Using historical weather data for {location}")
            df_result = pd.DataFrame(result_data)
            df_result.attrs["weather_source"] = "historical_file"
            return df_result

    # Fallback to synthetic generation
    logger.info(f"Using synthetic weather data for {location}")
    df_synth = generate_synthetic_weather(location, start_date, days)
    df_synth.attrs["weather_source"] = "synthetic"
    return df_synth


def predict_production_simple(
    capacity_kwp: float,
    radiation: float,
    cloud_cover: float,
    temperature: float,
) -> float:
    """
    Physics-based production prediction aligned with v1.2.3 methodology.
    Uses improved efficiency factors and temperature derating.
    """
    # No production below threshold radiation
    if radiation < MIN_RADIATION_FOR_PRODUCTION:
        return 0.0

    # System losses (inverter, wiring, soiling, etc.)
    system_efficiency = 0.85

    # Cloud cover impact - non-linear, clouds affect diffuse vs direct radiation
    # High clouds have less impact than low clouds
    if cloud_cover < CLOUD_COVER_LOW_THRESHOLD:
        cloud_factor = 1.0
    elif cloud_cover < CLOUD_COVER_MEDIUM_THRESHOLD:
        cloud_factor = (
            1 - (cloud_cover - CLOUD_COVER_LOW_THRESHOLD) / 100 * 0.4
        )  # Gradual reduction
    elif cloud_cover < CLOUD_COVER_HIGH_THRESHOLD:
        cloud_factor = (
            0.88 - (cloud_cover - CLOUD_COVER_MEDIUM_THRESHOLD) / 100 * 0.5
        )  # Steeper reduction
    else:
        cloud_factor = (
            0.73 - (cloud_cover - CLOUD_COVER_HIGH_THRESHOLD) / 100 * 0.3
        )  # Heavy clouds

    cloud_factor = max(0.3, cloud_factor)  # Minimum 30% even with full clouds (diffuse)

    # Temperature coefficient - typical -0.4%/C for crystalline silicon above 25C
    temp_coefficient = -0.004
    if temperature > REFERENCE_TEMP:
        temp_factor = 1 + temp_coefficient * (temperature - REFERENCE_TEMP)
    else:
        # Slight improvement below 25C (max +2%)
        temp_factor = min(1.02, 1 + 0.001 * (REFERENCE_TEMP - temperature))

    # Base production: capacity * radiation/1000 * panel_eff * system_eff
    # radiation is in W/m2, 1000 W/m2 is STC
    base_production = capacity_kwp * (radiation / 1000)

    # Apply all factors
    production = base_production * system_efficiency * cloud_factor * temp_factor

    return max(0, production)


@app.post("/predict/period", response_model=PeriodPredictionResponse)
async def predict_period(request: PeriodPredictionRequest):
    """
    Generate 21-day analysis for an installation or custom station.
    Returns hourly data with performance rankings.
    """
    try:
        # Parse center date
        center_date = datetime.strptime(request.center_date, "%Y-%m-%d")
        half_period = request.days // 2
        start_date = center_date - timedelta(days=half_period)
        end_date = center_date + timedelta(days=half_period)

        # Determine installation info
        if request.mode == "custom":
            # Custom station simulation
            location = request.location or "Lisbon"
            capacity_kwp = request.capacity_kwp or 5.0
            installation_info = {
                "id": "custom",
                "name": f"Custom Station ({location})",
                "location": location,
                "capacity_kwp": capacity_kwp,
                "serial_number": "CUSTOM",
            }
        else:
            # Load installation from Excel
            installations = load_installations_from_excel()
            if request.installation_id not in installations:
                # Fallback: if location and capacity are provided (e.g. virtual installations),
                # treat as a custom station instead of returning error
                if request.location and request.capacity_kwp:
                    location = request.location
                    capacity_kwp = request.capacity_kwp
                    installation_info = {
                        "id": request.installation_id or "custom",
                        "name": f"Custom Station ({location})",
                        "location": location,
                        "capacity_kwp": capacity_kwp,
                        "serial_number": "VIRTUAL",
                    }
                else:
                    return PeriodPredictionResponse(
                        success=False,
                        installation_info={},
                        period_statistics={},
                        daily_data=[],
                        hourly_data=[],
                        error=f"Installation not found: {request.installation_id}",
                    )
            else:
                inst = installations[request.installation_id]
                location = inst["location"]
                capacity_kwp = inst["capacity_kwp"]
                installation_info = {
                    "id": request.installation_id,
                    "name": inst["name"],
                    "location": location,
                    "capacity_kwp": capacity_kwp,
                    "serial_number": inst.get("serial_number", ""),
                }

        # Generate weather data for the period (async call to try API first)
        weather_df = await generate_weather_for_period(
            location, start_date, request.days
        )
        weather_source = getattr(weather_df, "attrs", {}).get(
            "weather_source", "synthetic"
        )

        # For historical mode, try to load actual measured energy data
        historical_energy = {}
        if request.mode == "historical" and request.installation_id:
            energy_df = load_energy_data_for_installation(request.installation_id)
            if (
                not energy_df.empty
                and "timestamp" in energy_df.columns
                and "produced_kwh" in energy_df.columns
            ):
                for _, erow in energy_df.iterrows():
                    ts = erow["timestamp"]
                    if hasattr(ts, "isoformat"):
                        key = ts.strftime("%Y-%m-%d %H")
                        historical_energy[key] = float(erow["produced_kwh"])
                if historical_energy:
                    weather_source = "measured"
                    logger.info(
                        f"Loaded {len(historical_energy)} historical energy readings for {request.installation_id}"
                    )

        # Generate predictions for each hour
        hourly_results = []
        for _, row in weather_df.iterrows():
            ts = row["timestamp"]
            ts_key = ts.strftime("%Y-%m-%d %H") if hasattr(ts, "strftime") else ""

            # Use measured data if available, otherwise estimate
            if ts_key in historical_energy:
                production = historical_energy[ts_key]
            else:
                production = predict_production_simple(
                    capacity_kwp,
                    row["shortwave_radiation"],
                    row["cloud_cover"],
                    row["temperature_2m"],
                )

            hourly_results.append(
                {
                    "timestamp": row["timestamp"],
                    "production_kwh": production,
                    "temperature": row["temperature_2m"],
                    "humidity": row["relative_humidity_2m"],
                    "cloud_cover": row["cloud_cover"],
                    "wind_speed": row["wind_speed_10m"],
                    "radiation": row["shortwave_radiation"],
                }
            )

        # Calculate specific energy and rankings for hourly data
        # Filter out R0 (zero/negligible production) hours
        hourly_data = []
        for r in hourly_results:
            specific_energy_hourly = (
                r["production_kwh"] / capacity_kwp if capacity_kwp > 0 else 0
            )
            rank = calculate_hourly_rank(specific_energy_hourly)

            # Skip R0 hours (zero/negligible production - users don't need these)
            if rank == 0:
                continue

            hourly_data.append(
                HourlyData(
                    timestamp=r["timestamp"].isoformat(),
                    hour=r["timestamp"].hour,
                    production_kwh=round(r["production_kwh"], 3),
                    specific_energy=round(specific_energy_hourly, 4),
                    rank=rank,
                    temperature=round(r["temperature"], 1)
                    if r["temperature"] is not None
                    else None,
                    humidity=round(r["humidity"], 1)
                    if r["humidity"] is not None
                    else None,
                    cloud_cover=round(r["cloud_cover"], 1)
                    if r["cloud_cover"] is not None
                    else None,
                    wind_speed=round(r["wind_speed"], 1)
                    if r["wind_speed"] is not None
                    else None,
                    radiation=round(r["radiation"], 1)
                    if r["radiation"] is not None
                    else None,
                )
            )

        # Aggregate daily data with all weather metrics
        daily_data = []
        for day_offset in range(request.days):
            day = start_date + timedelta(days=day_offset)
            day_str = day.strftime("%Y-%m-%d")

            day_hourly = [
                h for h in hourly_results if h["timestamp"].date() == day.date()
            ]
            if day_hourly:
                total = sum(h["production_kwh"] for h in day_hourly)
                avg = total / len(day_hourly)
                peak = max(day_hourly, key=lambda h: h["production_kwh"])

                # Calculate all weather averages
                avg_temp = sum(h["temperature"] or 0 for h in day_hourly) / len(
                    day_hourly
                )
                avg_humidity = sum(h["humidity"] or 0 for h in day_hourly) / len(
                    day_hourly
                )
                avg_cloud = sum(h["cloud_cover"] or 0 for h in day_hourly) / len(
                    day_hourly
                )
                avg_wind = sum(h["wind_speed"] or 0 for h in day_hourly) / len(
                    day_hourly
                )
                avg_rad = sum(h["radiation"] or 0 for h in day_hourly) / len(day_hourly)

                # Calculate daily specific energy and rank
                daily_specific_energy = total / capacity_kwp if capacity_kwp > 0 else 0
                daily_rank = calculate_energy_rank(daily_specific_energy)

                # Skip R0 days (zero/negligible production)
                if daily_rank == 0:
                    continue

                daily_data.append(
                    DailyData(
                        date=day_str,
                        total_production_kwh=round(total, 2),
                        specific_energy_kwh_kwp=round(daily_specific_energy, 3),
                        avg_production_kwh=round(avg, 3),
                        peak_hour=peak["timestamp"].hour,
                        peak_production_kwh=round(peak["production_kwh"], 3),
                        rank=daily_rank,
                        avg_temperature=round(avg_temp, 1),
                        avg_humidity=round(avg_humidity, 1),
                        avg_cloud_cover=round(avg_cloud, 1),
                        avg_wind_speed=round(avg_wind, 1),
                        avg_radiation=round(avg_rad, 1),
                    )
                )

        # Calculate period statistics
        total_energy = sum(d.total_production_kwh for d in daily_data)
        avg_daily = total_energy / len(daily_data) if daily_data else 0
        grid_price = 0.15
        total_savings = total_energy * grid_price

        period_statistics = {
            "total_energy_kwh": round(total_energy, 2),
            "avg_daily_kwh": round(avg_daily, 2),
            "total_savings_eur": round(total_savings, 2),
            "analysis_days": len(daily_data),
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "center_date": request.center_date,
        }

        # Model info for frontend
        model_bundle = (
            load_model(request.installation_id) if request.installation_id else None
        )
        model_info = None
        if model_bundle and model_bundle.get("model"):
            model_info = {
                "name": type(model_bundle["model"]).__name__,
                "feature_count": len(model_bundle.get("feature_names", [])),
                "r2": None,
                "mae": None,
            }
        else:
            model_info = {
                "name": "Physics-based Estimation",
                "feature_count": 5,
                "r2": None,
                "mae": None,
            }

        return PeriodPredictionResponse(
            success=True,
            installation_info=installation_info,
            period_statistics=period_statistics,
            daily_data=daily_data,
            hourly_data=hourly_data,
            weather_source=weather_source,
            model_info=model_info,
        )

    except Exception as e:
        logger.error(f"Period prediction failed: {e}")
        return PeriodPredictionResponse(
            success=False,
            installation_info={},
            period_statistics={},
            daily_data=[],
            hourly_data=[],
            error=str(e),
        )


# ===== Installation Statistics Endpoint (v3.0.4) =====


class InstallationStatsResponse(BaseModel):
    """Quick statistics for installation info popup."""

    success: bool
    installation_id: str
    location: str
    capacity_kwp: float
    avg_yearly_production_kwh: float | None = None
    avg_daily_kwh: float | None = None
    efficiency_kwh_kwp: float | None = None
    data_days: int = 0
    error: str | None = None


@app.get(
    "/installations/{installation_id}/stats", response_model=InstallationStatsResponse
)
async def get_installation_quick_stats(installation_id: str):
    """
    Get quick statistics for an installation (calculated on-the-fly from historical data).
    Used for the installation info popup on click.
    """
    try:
        installations = load_installations_from_excel()
        if installation_id not in installations:
            return InstallationStatsResponse(
                success=False,
                installation_id=installation_id,
                location="Unknown",
                capacity_kwp=0,
                error=f"Installation not found: {installation_id}",
            )

        inst = installations[installation_id]
        location = inst["location"]
        capacity_kwp = inst["capacity_kwp"]

        # Load energy data for this installation
        energy_df = load_energy_data_for_installation(installation_id)

        if energy_df.empty:
            # No historical data - return basic info
            return InstallationStatsResponse(
                success=True,
                installation_id=installation_id,
                location=location,
                capacity_kwp=capacity_kwp,
                data_days=0,
            )

        # Calculate statistics from historical data
        # Group by date and sum production
        if "timestamp" in energy_df.columns:
            energy_df["date"] = pd.to_datetime(energy_df["timestamp"]).dt.date
        elif "datetime" in energy_df.columns:
            energy_df["date"] = pd.to_datetime(energy_df["datetime"]).dt.date
        else:
            # Try to find any datetime-like column
            date_cols = [
                c
                for c in energy_df.columns
                if "date" in c.lower() or "time" in c.lower()
            ]
            if date_cols:
                energy_df["date"] = pd.to_datetime(energy_df[date_cols[0]]).dt.date
            else:
                return InstallationStatsResponse(
                    success=True,
                    installation_id=installation_id,
                    location=location,
                    capacity_kwp=capacity_kwp,
                    data_days=0,
                )

        # Find production column
        prod_col = None
        for col in ["production_kwh", "energy_kwh", "kwh", "production", "energy"]:
            if col in energy_df.columns:
                prod_col = col
                break

        if prod_col is None:
            return InstallationStatsResponse(
                success=True,
                installation_id=installation_id,
                location=location,
                capacity_kwp=capacity_kwp,
                data_days=0,
            )

        # Calculate daily totals
        daily_totals = energy_df.groupby("date")[prod_col].sum()
        data_days = len(daily_totals)

        if data_days == 0:
            return InstallationStatsResponse(
                success=True,
                installation_id=installation_id,
                location=location,
                capacity_kwp=capacity_kwp,
                data_days=0,
            )

        total_production = daily_totals.sum()
        avg_daily = total_production / data_days

        # Estimate yearly production (extrapolate from average daily)
        avg_yearly = avg_daily * 365

        # Calculate efficiency (kWh/kWp/day)
        efficiency = avg_daily / capacity_kwp if capacity_kwp > 0 else 0

        return InstallationStatsResponse(
            success=True,
            installation_id=installation_id,
            location=location,
            capacity_kwp=capacity_kwp,
            avg_yearly_production_kwh=round(avg_yearly, 1),
            avg_daily_kwh=round(avg_daily, 2),
            efficiency_kwh_kwp=round(efficiency, 3),
            data_days=data_days,
        )

    except Exception as e:
        logger.error(f"Failed to get installation stats: {e}")
        return InstallationStatsResponse(
            success=False,
            installation_id=installation_id,
            location="Unknown",
            capacity_kwp=0,
            error=str(e),
        )


# ===== Admin Endpoints (v3.0.6) =====


@app.get("/admin/cache")
async def admin_cache_status():
    """Return cache status: loaded models, cached data, memory usage."""
    import sys

    model_ids = list(_models_cache.keys())
    energy_ids = list(_energy_data_cache.keys())
    weather_ids = list(_weather_data_cache.keys())

    # Estimate memory usage
    model_mem = sum(sys.getsizeof(m) for m in _models_cache.values())
    energy_mem = sum(
        df.memory_usage(deep=True).sum()
        for df in _energy_data_cache.values()
        if not df.empty
    )
    weather_mem = sum(
        df.memory_usage(deep=True).sum()
        for df in _weather_data_cache.values()
        if not df.empty
    )

    return {
        "models": {
            "count": len(model_ids),
            "ids": model_ids,
            "memory_bytes": model_mem,
        },
        "energy_data": {
            "count": len(energy_ids),
            "ids": energy_ids,
            "memory_bytes": int(energy_mem),
        },
        "weather_data": {
            "count": len(weather_ids),
            "ids": weather_ids,
            "memory_bytes": int(weather_mem),
        },
        "installations_loaded": len(_installations_cache),
        "total_memory_bytes": model_mem + int(energy_mem) + int(weather_mem),
    }


@app.post("/admin/cache/clear")
async def admin_clear_cache():
    """Clear all model and data caches."""
    cleared = {
        "models": len(_models_cache),
        "energy_data": len(_energy_data_cache),
        "weather_data": len(_weather_data_cache),
    }

    _models_cache.clear()
    _scalers_cache.clear()
    _feature_names_cache.clear()
    _model_metrics_cache.clear()
    _model_name_cache.clear()
    _installations_cache.clear()
    _energy_data_cache.clear()
    _weather_data_cache.clear()
    _dashboard_cache.clear()
    _dashboard_cache.update({"computed_at": None, "data": None})

    logger.info(f"Cache cleared: {cleared}")
    return {"success": True, "cleared": cleared}


@app.get("/admin/model/{installation_id}")
async def admin_model_info(installation_id: str):
    """Get model metadata for a specific installation."""
    model_bundle = load_model(installation_id)

    if not model_bundle or not model_bundle.get("model"):
        return {
            "installation_id": installation_id,
            "has_model": False,
            "model_type": "Physics-based Estimation",
            "feature_count": 5,
        }

    model = model_bundle["model"]
    feature_names = model_bundle.get("feature_names", [])

    return {
        "installation_id": installation_id,
        "has_model": True,
        "model_type": model_bundle.get("best_model_name") or type(model).__name__,
        "feature_count": len(feature_names),
        "feature_names": feature_names[:10],  # First 10 for display
        "has_scaler": model_bundle.get("scaler") is not None,
        "metrics": model_bundle.get("metrics", {}),
    }


@app.get("/model-info")
async def model_info_aggregate():
    """
    Get aggregate model metadata for all installations.
    Used by the ML Info button in the frontend.
    """
    installations = load_installations_from_excel()
    models_available = []
    models_missing = []

    for inst_id in installations:
        bundle = load_model(inst_id)
        if bundle and bundle.get("model"):
            metrics = bundle.get("metrics", {})
            selected_model = bundle.get(
                "best_model_name", type(bundle["model"]).__name__
            )
            models_available.append(
                {
                    "id": inst_id,
                    "model_type": selected_model,
                    "feature_count": len(bundle.get("feature_names", [])),
                    "r2": metrics.get(selected_model, {}).get("r2"),
                    "mae": metrics.get(selected_model, {}).get("mae"),
                }
            )
        else:
            models_missing.append(inst_id)

    return {
        "total_installations": len(installations),
        "models_available": len(models_available),
        "models_missing": len(models_missing),
        "models": models_available,
        "missing_ids": models_missing,
        "default_method": "Physics-based Estimation",
        "dataset_citation": {
            "authors": "Sarmas et al.",
            "year": 2025,
            "title": "Photovoltaic Power Production Dataset",
            "doi": "10.17632/dbh93b6vp8.3",
            "publisher": "Mendeley Data",
        },
    }


# Load data on startup
@app.on_event("startup")
async def startup_event():
    """Pre-load data on startup for faster responses."""
    logger.info("Loading dataset on startup...")
    try:
        installations = load_installations_from_excel()
        logger.info(f"Startup: loaded {len(installations)} installations")
        for installation_id in installations:
            load_model(installation_id)
        _refresh_dashboard_cache(force=True)
        logger.info("Startup: warmed model cache and dashboard aggregates")
    except Exception as e:
        logger.error(f"Startup data loading failed: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8501)  # nosec B104 - container service on the Docker bridge network
