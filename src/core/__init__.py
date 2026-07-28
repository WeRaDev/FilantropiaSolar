"""Legacy ``src.core`` shim re-exporting the packaged ``filantropia_solar.core`` API.

Transitional: kept until the package-layout migration completes; new code
should import from ``filantropia_solar.core`` directly. The legacy-only
``src.core.exceptions`` module (retry/circuit-breaker machinery) remains
importable as a submodule and is unaffected by this shim.
"""

from src.filantropia_solar.core import (
    BusinessLogicError,
    ColoredFormatter,
    ConfigurationError,
    ConfigurationManager,
    DataError,
    DataLoadingError,
    DataValidationError,
    EnergyPredictionError,
    Environment,
    ErrorCode,
    FilantropiaSolarError,
    FileNotFoundError,
    FileSystemError,
    GUIError,
    JSONFormatter,
    LogContext,
    LoggingManager,
    LogLevel,
    ModelError,
    ModelPredictionError,
    ModelTrainingError,
    PerformanceLogger,
    Settings,
    UserInputError,
    ValidationError,
    WeatherAPIError,
    WeatherAPIRateLimitError,
    WeatherAPITimeoutError,
    create_error_response,
    get_config,
    get_data_dir,
    get_environment,
    get_logger,
    get_logs_dir,
    get_models_dir,
    get_performance_logger,
    get_settings,
    handle_exception,
    is_debug,
    is_production,
    log_api_request,
    log_context,
    log_data_processing,
    log_error,
    log_exceptions,
    log_model_operation,
    log_performance,
    log_shutdown,
    log_startup,
    log_user_action,
    reload_config,
    setup_logging,
)

__all__ = [name for name in dir() if not name.startswith("_")]
