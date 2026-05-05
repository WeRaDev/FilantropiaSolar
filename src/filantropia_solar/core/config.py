"""
Configuration management for FilantropiaSolar application.

This module provides centralized configuration management with type safety,
validation, and support for multiple environments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import Field, validator
from pydantic_settings import BaseSettings
import yaml

# Constants
MAX_PORT_NUMBER = 65535


class Environment(str, Enum):
    """Application environment enumeration."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(slots=True)
class DatabaseConfig:
    """Database configuration settings."""

    url: str | None = None
    host: str = "localhost"
    port: int = 5432
    name: str = "filantropia_solar"
    username: str | None = None
    password: str | None = None
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    echo: bool = False


@dataclass(slots=True)
class WeatherAPIConfig:
    """Weather API configuration settings."""

    base_url: str = "https://api.open-meteo.com/v1/forecast"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    cache_ttl: int = 3600  # 1 hour
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # 1 minute


@dataclass(slots=True)
class MLModelConfig:
    """Machine learning model configuration settings."""

    default_model_type: str = "random_forest"
    model_cache_size: int = 100
    training_batch_size: int = 1000
    prediction_batch_size: int = 500
    cross_validation_folds: int = 5
    hyperparameter_optimization: bool = True
    feature_selection: bool = True
    auto_retrain_threshold: float = 0.8  # R² threshold
    model_versioning: bool = True


@dataclass(slots=True)
class SecurityConfig:
    """Security configuration settings."""

    secret_key: str = field(default_factory=lambda: os.urandom(32).hex())
    api_key_header: str = "X-API-Key"
    rate_limit_enabled: bool = True
    cors_enabled: bool = True
    cors_origins: list[str] = field(default_factory=list)
    session_timeout: int = 3600  # 1 hour
    password_min_length: int = 8
    max_login_attempts: int = 5


@dataclass(slots=True)
class MonitoringConfig:
    """Monitoring and observability configuration."""

    metrics_enabled: bool = True
    metrics_port: int = 8001
    metrics_path: str = "/metrics"
    tracing_enabled: bool = False
    tracing_sample_rate: float = 0.1
    health_check_enabled: bool = True
    health_check_path: str = "/health"
    performance_tracking: bool = True


@dataclass(slots=True)
class CacheConfig:
    """Caching configuration settings."""

    enabled: bool = True
    backend: str = "memory"  # memory, redis, memcached
    redis_url: str | None = None
    default_ttl: int = 3600  # 1 hour
    max_entries: int = 10000
    key_prefix: str = "fs:"


def _detect_app_version() -> str:
    """Determine app version from installed package or package metadata."""
    # Prefer distribution metadata when installed
    try:
        return pkg_version("filantropia-solar")
    except PackageNotFoundError:
        pass
    # Fallback to package attribute
    try:
        from .. import __version__ as pkg_ver  # type: ignore
        return str(pkg_ver)
    except Exception:
        return "1.2.1"


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    Automatically loads configuration from environment variables,
    .env files, and configuration files.
    """

    # Application settings
    app_name: str = Field(default="FilantropiaSolar", env="APP_NAME")
    version: str = Field(default_factory=_detect_app_version, env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    environment: Environment = Field(default=Environment.DEVELOPMENT, env="ENVIRONMENT")

    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")

    # Logging settings
    log_level: LogLevel = Field(default=LogLevel.INFO, env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT",
    )
    log_file: str | None = Field(default=None, env="LOG_FILE")
    log_rotation: bool = Field(default=True, env="LOG_ROTATION")
    log_retention: int = Field(default=30, env="LOG_RETENTION")  # days

    # Paths
    data_dir: Path = Field(default=Path("data"), env="DATA_DIR")
    models_dir: Path = Field(default=Path("models"), env="MODELS_DIR")
    logs_dir: Path = Field(default=Path("logs"), env="LOGS_DIR")
    temp_dir: Path = Field(default=Path("temp"), env="TEMP_DIR")

    # Component configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    weather_api: WeatherAPIConfig = Field(default_factory=WeatherAPIConfig)
    ml_models: MLModelConfig = Field(default_factory=MLModelConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False
        validate_assignment = True

    @validator("data_dir", "models_dir", "logs_dir", "temp_dir", pre=True)
    def validate_paths(cls, v: str | Path) -> Path:
        """Validate and convert path strings to Path objects."""
        path = Path(v)
        if not path.is_absolute():
            # Make relative paths relative to project root
            path = Path.cwd() / path
        return path

    @validator("port")
    def validate_port(cls, v: int) -> int:
        """Validate port number."""
        if not 1 <= v <= MAX_PORT_NUMBER:
            raise ValueError(f"Port must be between 1 and {MAX_PORT_NUMBER}")
        return v

    @validator("workers")
    def validate_workers(cls, v: int) -> int:
        """Validate worker count."""
        if v < 1:
            raise ValueError("Workers must be at least 1")
        return v

    def create_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [self.data_dir, self.models_dir, self.logs_dir, self.temp_dir]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert settings to dictionary."""
        return self.dict()

    def to_json(self) -> str:
        """Convert settings to JSON string."""
        return self.json(indent=2, default=str)

    def save_to_file(self, file_path: str | Path) -> None:
        """Save configuration to file."""
        file_path = Path(file_path)
        config_data = self.to_dict()

        # Convert Path objects to strings for serialization
        def convert_paths(obj: Any) -> Any:
            if isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_paths(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_paths(item) for item in obj]
            return obj

        config_data = convert_paths(config_data)

        if file_path.suffix.lower() == ".yaml" or file_path.suffix.lower() == ".yml":
            with file_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(config_data, f, default_flow_style=False, indent=2)
        else:
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load_from_file(cls, file_path: str | Path) -> Settings:
        """Load configuration from file."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with file_path.open(encoding="utf-8") as f:
            if file_path.suffix.lower() in [".yaml", ".yml"]:
                config_data = yaml.safe_load(f)
            else:
                config_data = json.load(f)

        return cls(**config_data)


class ConfigurationManager:
    """
    Centralized configuration manager.

    Provides singleton access to application configuration and
    manages configuration lifecycle.
    """

    _instance: ConfigurationManager | None = None
    _settings: Settings | None = None

    def __new__(cls) -> ConfigurationManager:
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize configuration manager."""
        if self._settings is None:
            self._load_configuration()

    def _load_configuration(self) -> None:
        """Load configuration from environment and files."""
        # Try to load from configuration file if it exists
        config_files = [
            "config/settings.yaml",
            "config/settings.yml",
            "config/settings.json",
            "settings.yaml",
            "settings.yml",
            "settings.json",
        ]

        for config_file in config_files:
            if Path(config_file).exists():
                try:
                    self._settings = Settings.load_from_file(config_file)
                    logging.info(f"Configuration loaded from {config_file}")
                    break
                except Exception as e:
                    logging.warning(f"Failed to load config from {config_file}: {e}")

        # Fallback to environment variables and defaults
        if self._settings is None:
            self._settings = Settings()
            logging.info("Configuration loaded from environment variables and defaults")

        # Create necessary directories
        self._settings.create_directories()

    @property
    def settings(self) -> Settings:
        """Get current settings."""
        if self._settings is None:
            self._load_configuration()
        return self._settings

    def reload(self) -> None:
        """Reload configuration."""
        self._settings = None
        self._load_configuration()

    def update_settings(self, **kwargs: Any) -> None:
        """Update settings with new values."""
        if self._settings is None:
            self._load_configuration()

        # Create new settings instance with updated values
        current_dict = self._settings.dict()
        current_dict.update(kwargs)
        self._settings = Settings(**current_dict)

    def get_environment_config(self) -> dict[str, Any]:
        """Get environment-specific configuration."""
        env = self.settings.environment

        # Environment-specific overrides
        env_configs = {
            Environment.DEVELOPMENT: {
                "debug": True,
                "log_level": LogLevel.DEBUG,
                "database.echo": True,
                "monitoring.metrics_enabled": False,
            },
            Environment.TESTING: {
                "debug": False,
                "log_level": LogLevel.WARNING,
                "database.name": "filantropia_solar_test",
                "cache.enabled": False,
            },
            Environment.STAGING: {
                "debug": False,
                "log_level": LogLevel.INFO,
                "monitoring.metrics_enabled": True,
                "security.rate_limit_enabled": True,
            },
            Environment.PRODUCTION: {
                "debug": False,
                "log_level": LogLevel.WARNING,
                "monitoring.metrics_enabled": True,
                "security.rate_limit_enabled": True,
                "ml_models.auto_retrain_threshold": 0.9,
            },
        }

        return env_configs.get(env, {})


# Global configuration instance
config = ConfigurationManager()


def get_settings() -> Settings:
    """Get application settings."""
    return config.settings


def get_config() -> ConfigurationManager:
    """Get configuration manager instance."""
    return config


def reload_config() -> None:
    """Reload application configuration."""
    config.reload()


# Convenience functions for common configuration access
def is_debug() -> bool:
    """Check if debug mode is enabled."""
    return get_settings().debug


def get_environment() -> Environment:
    """Get current environment."""
    return get_settings().environment


def is_production() -> bool:
    """Check if running in production environment."""
    return get_environment() == Environment.PRODUCTION


def get_data_dir() -> Path:
    """Get data directory path."""
    return get_settings().data_dir


def get_models_dir() -> Path:
    """Get models directory path."""
    return get_settings().models_dir


def get_logs_dir() -> Path:
    """Get logs directory path."""
    return get_settings().logs_dir
