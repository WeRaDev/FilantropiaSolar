"""
Configuration Settings for FilantropiaSolar
Central configuration file for application settings
"""

from pathlib import Path

# Project directories
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
LOGS_DIR = PROJECT_ROOT / "logs"
EXPORTS_DIR = PROJECT_ROOT / "exports"

# Data files
PV_DATA_FILE = "PV Plants Datasets.xlsx"
METADATA_FILE = "PV Plants Metadata.xlsx"
WEATHER_DATA_DIR = "weather_files"
LISBON_WEATHER_FILE = "Lisbon_weather.csv"

# Lisbon PV installations
LISBON_INSTALLATIONS = ["Lisbon_1", "Lisbon_2", "Lisbon_3", "Lisbon_4"]

# Installation to Excel sheet mapping
INSTALLATION_MAPPING = {
    'Lisbon_1': ['84071567'],
    'Lisbon_2': ['84071569'],
    'Lisbon_3': ['84071570'],
    'Lisbon_4': ['62032213']
}

# Lisbon coordinates for weather API
LISBON_COORDINATES = {
    "latitude": 38.7223,
    "longitude": -9.1393
}

# Weather API settings
WEATHER_API_TIMEOUT = 30  # seconds
WEATHER_API_RETRY_ATTEMPTS = 3

# Machine Learning settings
ML_MODELS = {
    'random_forest': {
        'n_estimators': 100,
        'random_state': 42,
        'max_depth': None
    },
    'gradient_boost': {
        'n_estimators': 100,
        'random_state': 42,
        'learning_rate': 0.1
    },
    'linear': {
        'fit_intercept': True,
        'normalize': False
    }
}

# Model training settings
MIN_TRAINING_SAMPLES = 50
TEST_SIZE = 0.2
RANDOM_STATE = 42

# Ranking system configuration
RANKING_THRESHOLDS = {
    1: (0.0, 0.2),    # Poor
    2: (0.2, 0.4),    # Fair
    3: (0.4, 0.6),    # Good
    4: (0.6, 0.8),    # Very Good
    5: (0.8, float('inf'))  # Excellent
}

RANKING_COLORS = {
    1: "#FF4444",  # Red
    2: "#FF8C00",  # Orange
    3: "#FFD700",  # Gold
    4: "#32CD32",  # Green
    5: "#00AA00"   # Dark Green
}

RANKING_DESCRIPTIONS = {
    1: "Poor (0.1-0.2 kWh/kWp)",
    2: "Fair (0.2-0.4 kWh/kWp)",
    3: "Good (0.4-0.6 kWh/kWp)",
    4: "Very Good (0.6-0.8 kWh/kWp)",
    5: "Excellent (≥0.8 kWh/kWp)"
}

# GUI settings
GUI_WINDOW_SIZE = "1400x900"
GUI_THEME = "clam"

# Prediction settings
DEFAULT_CAPACITY_KWP = 10.0
FORECAST_DAYS = 7
MAX_FORECAST_DAYS = 14

# Weather features for correlation analysis
WEATHER_FEATURES = [
    'temperature_2m (°C)',
    'relative_humidity_2m (%)', 
    'dew_point_2m (°C)',
    'apparent_temperature (°C)',
    'cloud_cover (%)',
    'wind_speed_10m (km/h)',
    'shortwave_radiation (W/m²)'
]

# Energy production features
ENERGY_FEATURES = [
    'Produced Energy (kWh)',
    'Specific Energy (kWh/kWp)',
    'Ranking'
]

# Logging configuration
LOGGING_LEVEL = "INFO"
LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Application metadata
APP_NAME = "FilantropiaSolar"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Solar Energy Prediction System for Lisbon PV Installations"
APP_AUTHOR = "FilantropiaSolar Team"

# Export settings
EXPORT_DATE_FORMAT = "%Y-%m-%d"
CSV_SEPARATOR = ","
EXCEL_ENGINE = "openpyxl"

# Seasonal definitions
SEASONS = {
    'Winter': [12, 1, 2],
    'Spring': [3, 4, 5],
    'Summer': [6, 7, 8],
    'Autumn': [9, 10, 11]
}