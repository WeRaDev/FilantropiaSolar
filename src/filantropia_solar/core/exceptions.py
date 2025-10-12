"""
Comprehensive exception hierarchy for FilantropiaSolar application.

This module defines custom exceptions with proper error handling patterns,
error codes, and detailed error information for better debugging and user experience.
"""

from typing import Any, Dict, Optional, List, Union
from enum import Enum
import traceback
from datetime import datetime


class ErrorCode(str, Enum):
    """Error codes for categorizing exceptions."""
    
    # General errors (1000-1999)
    UNKNOWN_ERROR = "FS1000"
    VALIDATION_ERROR = "FS1001"
    CONFIGURATION_ERROR = "FS1002"
    INITIALIZATION_ERROR = "FS1003"
    PERMISSION_ERROR = "FS1004"
    
    # Data processing errors (2000-2999)
    DATA_LOADING_ERROR = "FS2000"
    DATA_VALIDATION_ERROR = "FS2001"
    DATA_PROCESSING_ERROR = "FS2002"
    DATA_EXPORT_ERROR = "FS2003"
    DATA_CORRUPTION_ERROR = "FS2004"
    MISSING_DATA_ERROR = "FS2005"
    
    # ML model errors (3000-3999)
    MODEL_TRAINING_ERROR = "FS3000"
    MODEL_PREDICTION_ERROR = "FS3001"
    MODEL_LOADING_ERROR = "FS3002"
    MODEL_SAVING_ERROR = "FS3003"
    MODEL_VALIDATION_ERROR = "FS3004"
    FEATURE_ENGINEERING_ERROR = "FS3005"
    
    # Weather API errors (4000-4999)
    WEATHER_API_ERROR = "FS4000"
    WEATHER_API_TIMEOUT = "FS4001"
    WEATHER_API_UNAUTHORIZED = "FS4002"
    WEATHER_API_RATE_LIMIT = "FS4003"
    WEATHER_DATA_INVALID = "FS4004"
    
    # GUI errors (5000-5999)
    GUI_INITIALIZATION_ERROR = "FS5000"
    GUI_RENDERING_ERROR = "FS5001"
    USER_INPUT_ERROR = "FS5002"
    DISPLAY_ERROR = "FS5003"
    
    # File system errors (6000-6999)
    FILE_NOT_FOUND_ERROR = "FS6000"
    FILE_PERMISSION_ERROR = "FS6001"
    FILE_CORRUPTION_ERROR = "FS6002"
    DIRECTORY_ERROR = "FS6003"
    
    # Database errors (7000-7999)
    DATABASE_CONNECTION_ERROR = "FS7000"
    DATABASE_QUERY_ERROR = "FS7001"
    DATABASE_CONSTRAINT_ERROR = "FS7002"
    DATABASE_TRANSACTION_ERROR = "FS7003"
    
    # Network errors (8000-8999)
    NETWORK_ERROR = "FS8000"
    CONNECTION_TIMEOUT = "FS8001"
    HTTP_ERROR = "FS8002"
    SSL_ERROR = "FS8003"
    
    # Business logic errors (9000-9999)
    BUSINESS_RULE_VIOLATION = "FS9000"
    INSUFFICIENT_DATA_ERROR = "FS9001"
    CALCULATION_ERROR = "FS9002"
    ENERGY_PREDICTION_ERROR = "FS9003"


class FilantropiaSolarError(Exception):
    """
    Base exception class for all FilantropiaSolar errors.
    
    Provides common error handling functionality including error codes,
    detailed messages, and context information.
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        user_message: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
    ):
        """
        Initialize FilantropiaSolar error.
        
        Args:
            message: Technical error message for developers
            error_code: Categorized error code
            details: Additional context information
            cause: Original exception that caused this error
            user_message: User-friendly message for end users
            suggestions: List of suggested solutions
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        self.user_message = user_message or self._generate_user_message()
        self.suggestions = suggestions or []
        self.timestamp = datetime.utcnow()
        
        # Add cause to chain if provided
        if cause:
            self.__cause__ = cause
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly message based on error code."""
        user_messages = {
            ErrorCode.VALIDATION_ERROR: "Invalid input data provided.",
            ErrorCode.CONFIGURATION_ERROR: "Application configuration error.",
            ErrorCode.DATA_LOADING_ERROR: "Failed to load data file.",
            ErrorCode.MODEL_TRAINING_ERROR: "Machine learning model training failed.",
            ErrorCode.WEATHER_API_ERROR: "Weather service is currently unavailable.",
            ErrorCode.FILE_NOT_FOUND_ERROR: "Required file not found.",
            ErrorCode.NETWORK_ERROR: "Network connection error.",
        }
        return user_messages.get(self.error_code, "An unexpected error occurred.")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            'error_code': self.error_code.value,
            'message': self.message,
            'user_message': self.user_message,
            'details': self.details,
            'suggestions': self.suggestions,
            'timestamp': self.timestamp.isoformat(),
            'cause': str(self.cause) if self.cause else None,
            'traceback': traceback.format_exc() if self.__traceback__ else None,
        }
    
    def __str__(self) -> str:
        """String representation of the error."""
        return f"[{self.error_code.value}] {self.message}"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"{self.__class__.__name__}("
                f"message='{self.message}', "
                f"error_code='{self.error_code.value}', "
                f"details={self.details})")


class ValidationError(FilantropiaSolarError):
    """Exception raised for validation errors."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        expected_type: Optional[type] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if field:
            details['field'] = field
        if value is not None:
            details['value'] = str(value)[:200]  # Limit length
        if expected_type:
            details['expected_type'] = expected_type.__name__
        
        super().__init__(
            message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details=details,
            suggestions=["Check input data format and types"],
            **kwargs
        )


class ConfigurationError(FilantropiaSolarError):
    """Exception raised for configuration errors."""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if config_key:
            details['config_key'] = config_key
        
        super().__init__(
            message,
            error_code=ErrorCode.CONFIGURATION_ERROR,
            details=details,
            suggestions=["Check configuration file", "Verify environment variables"],
            **kwargs
        )


class DataError(FilantropiaSolarError):
    """Base class for data-related errors."""
    
    def __init__(self, message: str, error_code: ErrorCode, **kwargs):
        if error_code.value.startswith('FS2'):  # Data error codes
            super().__init__(message, error_code=error_code, **kwargs)
        else:
            raise ValueError("Invalid error code for DataError")


class DataLoadingError(DataError):
    """Exception raised when data loading fails."""
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        data_source: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if file_path:
            details['file_path'] = file_path
        if data_source:
            details['data_source'] = data_source
        
        super().__init__(
            message,
            error_code=ErrorCode.DATA_LOADING_ERROR,
            details=details,
            suggestions=[
                "Check file path and permissions",
                "Verify data format",
                "Ensure data source is accessible"
            ],
            **kwargs
        )


class DataValidationError(DataError):
    """Exception raised when data validation fails."""
    
    def __init__(
        self,
        message: str,
        validation_rules: Optional[List[str]] = None,
        failed_records: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if validation_rules:
            details['validation_rules'] = validation_rules
        if failed_records is not None:
            details['failed_records'] = failed_records
        
        super().__init__(
            message,
            error_code=ErrorCode.DATA_VALIDATION_ERROR,
            details=details,
            suggestions=[
                "Review data quality requirements",
                "Clean data before processing",
                "Check for missing or invalid values"
            ],
            **kwargs
        )


class ModelError(FilantropiaSolarError):
    """Base class for ML model errors."""
    
    def __init__(self, message: str, error_code: ErrorCode, **kwargs):
        if error_code.value.startswith('FS3'):  # Model error codes
            super().__init__(message, error_code=error_code, **kwargs)
        else:
            raise ValueError("Invalid error code for ModelError")


class ModelTrainingError(ModelError):
    """Exception raised when model training fails."""
    
    def __init__(
        self,
        message: str,
        model_type: Optional[str] = None,
        training_samples: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if model_type:
            details['model_type'] = model_type
        if training_samples is not None:
            details['training_samples'] = training_samples
        
        super().__init__(
            message,
            error_code=ErrorCode.MODEL_TRAINING_ERROR,
            details=details,
            suggestions=[
                "Check training data quality",
                "Verify feature engineering",
                "Review model hyperparameters",
                "Ensure sufficient training samples"
            ],
            **kwargs
        )


class ModelPredictionError(ModelError):
    """Exception raised when model prediction fails."""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        input_features: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if model_name:
            details['model_name'] = model_name
        if input_features is not None:
            details['input_features'] = input_features
        
        super().__init__(
            message,
            error_code=ErrorCode.MODEL_PREDICTION_ERROR,
            details=details,
            suggestions=[
                "Check input data format",
                "Verify feature consistency",
                "Ensure model is properly loaded"
            ],
            **kwargs
        )


class WeatherAPIError(FilantropiaSolarError):
    """Base class for weather API errors."""
    
    def __init__(self, message: str, error_code: ErrorCode, **kwargs):
        if error_code.value.startswith('FS4'):  # Weather API error codes
            super().__init__(message, error_code=error_code, **kwargs)
        else:
            raise ValueError("Invalid error code for WeatherAPIError")


class WeatherAPITimeoutError(WeatherAPIError):
    """Exception raised when weather API request times out."""
    
    def __init__(
        self,
        message: str,
        timeout_duration: Optional[float] = None,
        api_endpoint: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if timeout_duration is not None:
            details['timeout_duration'] = timeout_duration
        if api_endpoint:
            details['api_endpoint'] = api_endpoint
        
        super().__init__(
            message,
            error_code=ErrorCode.WEATHER_API_TIMEOUT,
            details=details,
            suggestions=[
                "Check network connectivity",
                "Increase timeout duration",
                "Try again later"
            ],
            **kwargs
        )


class WeatherAPIRateLimitError(WeatherAPIError):
    """Exception raised when weather API rate limit is exceeded."""
    
    def __init__(
        self,
        message: str,
        requests_made: Optional[int] = None,
        rate_limit: Optional[int] = None,
        reset_time: Optional[datetime] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if requests_made is not None:
            details['requests_made'] = requests_made
        if rate_limit is not None:
            details['rate_limit'] = rate_limit
        if reset_time:
            details['reset_time'] = reset_time.isoformat()
        
        super().__init__(
            message,
            error_code=ErrorCode.WEATHER_API_RATE_LIMIT,
            details=details,
            suggestions=[
                "Wait for rate limit reset",
                "Implement request caching",
                "Reduce API call frequency"
            ],
            **kwargs
        )


class GUIError(FilantropiaSolarError):
    """Base class for GUI-related errors."""
    
    def __init__(self, message: str, error_code: ErrorCode, **kwargs):
        if error_code.value.startswith('FS5'):  # GUI error codes
            super().__init__(message, error_code=error_code, **kwargs)
        else:
            raise ValueError("Invalid error code for GUIError")


class UserInputError(GUIError):
    """Exception raised for invalid user input."""
    
    def __init__(
        self,
        message: str,
        input_field: Optional[str] = None,
        input_value: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if input_field:
            details['input_field'] = input_field
        if input_value:
            details['input_value'] = str(input_value)[:100]  # Limit length
        
        super().__init__(
            message,
            error_code=ErrorCode.USER_INPUT_ERROR,
            details=details,
            suggestions=[
                "Check input format",
                "Verify required fields are filled",
                "Ensure values are within valid ranges"
            ],
            **kwargs
        )


class FileSystemError(FilantropiaSolarError):
    """Base class for file system errors."""
    
    def __init__(self, message: str, error_code: ErrorCode, **kwargs):
        if error_code.value.startswith('FS6'):  # File system error codes
            super().__init__(message, error_code=error_code, **kwargs)
        else:
            raise ValueError("Invalid error code for FileSystemError")


class FileNotFoundError(FileSystemError):
    """Exception raised when a required file is not found."""
    
    def __init__(
        self,
        message: str,
        file_path: str,
        file_type: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        details['file_path'] = file_path
        if file_type:
            details['file_type'] = file_type
        
        super().__init__(
            message,
            error_code=ErrorCode.FILE_NOT_FOUND_ERROR,
            details=details,
            suggestions=[
                "Check file path is correct",
                "Verify file exists in expected location",
                "Check file permissions"
            ],
            **kwargs
        )


class BusinessLogicError(FilantropiaSolarError):
    """Base class for business logic errors."""
    
    def __init__(self, message: str, error_code: ErrorCode, **kwargs):
        if error_code.value.startswith('FS9'):  # Business logic error codes
            super().__init__(message, error_code=error_code, **kwargs)
        else:
            raise ValueError("Invalid error code for BusinessLogicError")


class EnergyPredictionError(BusinessLogicError):
    """Exception raised when energy prediction fails business rules."""
    
    def __init__(
        self,
        message: str,
        installation: Optional[str] = None,
        prediction_date: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if installation:
            details['installation'] = installation
        if prediction_date:
            details['prediction_date'] = prediction_date
        
        super().__init__(
            message,
            error_code=ErrorCode.ENERGY_PREDICTION_ERROR,
            details=details,
            suggestions=[
                "Check installation parameters",
                "Verify weather data availability",
                "Review prediction model performance"
            ],
            **kwargs
        )


# Error handling utilities
def handle_exception(
    func: callable,
    exception_mapping: Optional[Dict[type, ErrorCode]] = None,
    default_error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
    context: Optional[Dict[str, Any]] = None,
) -> callable:
    """
    Decorator to handle exceptions and convert them to FilantropiaSolar errors.
    
    Args:
        func: Function to wrap
        exception_mapping: Mapping of exception types to error codes
        default_error_code: Default error code for unmapped exceptions
        context: Additional context to include in error details
        
    Returns:
        Wrapped function with exception handling
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FilantropiaSolarError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            # Map external exceptions to our error hierarchy
            mapping = exception_mapping or {}
            error_code = mapping.get(type(e), default_error_code)
            
            details = context.copy() if context else {}
            details['original_exception'] = type(e).__name__
            
            raise FilantropiaSolarError(
                message=f"Unexpected error in {func.__name__}: {str(e)}",
                error_code=error_code,
                details=details,
                cause=e
            ) from e
    
    return wrapper


def create_error_response(
    error: FilantropiaSolarError,
    include_traceback: bool = False
) -> Dict[str, Any]:
    """
    Create standardized error response dictionary.
    
    Args:
        error: FilantropiaSolar error instance
        include_traceback: Whether to include traceback information
        
    Returns:
        Standardized error response dictionary
    """
    response = {
        'success': False,
        'error': {
            'code': error.error_code.value,
            'message': error.user_message,
            'details': error.details,
            'suggestions': error.suggestions,
            'timestamp': error.timestamp.isoformat(),
        }
    }
    
    if include_traceback and error.__traceback__:
        response['error']['traceback'] = traceback.format_exception(
            type(error), error, error.__traceback__
        )
    
    return response


def log_error(error: FilantropiaSolarError, logger) -> None:
    """
    Log error with appropriate level and context.
    
    Args:
        error: FilantropiaSolar error instance
        logger: Logger instance to use
    """
    # Determine log level based on error code
    if error.error_code.value.startswith('FS1'):  # General errors
        log_level = 'error'
    elif error.error_code.value.startswith('FS2'):  # Data errors
        log_level = 'warning'
    elif error.error_code.value.startswith('FS3'):  # Model errors
        log_level = 'error'
    elif error.error_code.value.startswith('FS4'):  # API errors
        log_level = 'warning'
    elif error.error_code.value.startswith('FS5'):  # GUI errors
        log_level = 'info'
    else:
        log_level = 'error'
    
    # Log with appropriate level
    log_method = getattr(logger, log_level)
    log_method(
        f"{error.error_code.value}: {error.message}",
        extra={
            'error_code': error.error_code.value,
            'user_message': error.user_message,
            'details': error.details,
            'suggestions': error.suggestions,
            'cause': str(error.cause) if error.cause else None,
        },
        exc_info=error.cause if error.cause else None
    )