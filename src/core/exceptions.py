"""
Enhanced exception handling for FilantropiaSolar
Provides custom exceptions, retry mechanisms, and error recovery strategies
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import functools
import logging
import random
import time
from typing import Any, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

# Type variables for decorators
F = TypeVar("F", bound=Callable[..., Any])
P = ParamSpec("P")
R = TypeVar("R")


# Custom Exception Hierarchy
class FilantropiaSolarError(Exception):
    """Base exception for all FilantropiaSolar errors"""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = time.time()


class DataProcessingError(FilantropiaSolarError):
    """Raised when data processing operations fail"""

    pass


class WeatherAPIError(FilantropiaSolarError):
    """Raised when weather API operations fail"""

    pass


class ModelTrainingError(FilantropiaSolarError):
    """Raised when ML model training fails"""

    def __init__(self, message: str, model_name: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.model_name = model_name


class PredictionError(FilantropiaSolarError):
    """Raised when energy prediction fails"""

    def __init__(self, message: str, installation_id: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.installation_id = installation_id


class ValidationError(FilantropiaSolarError):
    """Raised when data validation fails"""

    def __init__(self, message: str, field_name: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.field_name = field_name


class ConfigurationError(FilantropiaSolarError):
    """Raised when configuration is invalid"""

    pass


class InsufficientDataError(FilantropiaSolarError):
    """Raised when insufficient data is available for operations"""

    def __init__(
        self,
        message: str,
        required_samples: int | None = None,
        available_samples: int | None = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.required_samples = required_samples
        self.available_samples = available_samples


class ResourceExhaustionError(FilantropiaSolarError):
    """Raised when system resources are exhausted"""

    pass


# Error Context Management
@dataclass(slots=True)
class ErrorContext:
    """Context information for error handling"""

    operation: str
    component: str
    installation_id: str | None = None
    timestamp: float | None = None
    additional_info: dict[str, Any] | None = None


# Retry Configuration
@dataclass(slots=True)
class RetryConfig:
    """Configuration for retry mechanisms"""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        WeatherAPIError,
        DataProcessingError,
    )


class RetryExhaustedError(FilantropiaSolarError):
    """Raised when all retry attempts are exhausted"""

    def __init__(self, message: str, attempts: int, last_exception: Exception):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


# Synchronous Retry Decorator
def retry_sync(
    config: RetryConfig | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Synchronous retry decorator with exponential backoff

    Args:
        config: Retry configuration

    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)

                except config.retry_on_exceptions as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = min(
                            config.base_delay * (config.exponential_base**attempt),
                            config.max_delay,
                        )

                        if config.jitter:
                            delay *= 0.5 + random.random() * 0.5  # Add 0-50% jitter

                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {func.__name__}"
                        )

                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise

            raise RetryExhaustedError(
                f"Failed after {config.max_attempts} attempts",
                config.max_attempts,
                last_exception,
            )

        return wrapper

    return decorator


# Asynchronous Retry Decorator
def retry_async(
    config: RetryConfig | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Asynchronous retry decorator with exponential backoff

    Args:
        config: Retry configuration

    Returns:
        Decorated async function with retry logic
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)

                except config.retry_on_exceptions as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = min(
                            config.base_delay * (config.exponential_base**attempt),
                            config.max_delay,
                        )

                        if config.jitter:
                            delay *= 0.5 + random.random() * 0.5  # Add 0-50% jitter

                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {func.__name__}"
                        )

                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise

            raise RetryExhaustedError(
                f"Failed after {config.max_attempts} attempts",
                config.max_attempts,
                last_exception,
            )

        return wrapper

    return decorator


# Circuit Breaker Pattern
class CircuitBreakerState:
    """Enum for circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass(slots=True)
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: type[Exception] = Exception


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance"""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, func: Callable[[], R]) -> R:
        """Execute function with circuit breaker protection"""
        match self.state:
            case CircuitBreakerState.OPEN:
                if time.time() - self.last_failure_time >= self.config.recovery_timeout:
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise ResourceExhaustionError("Circuit breaker is OPEN")

            case CircuitBreakerState.HALF_OPEN:
                try:
                    result = func()
                    self._on_success()
                    return result
                except self.config.expected_exception:
                    self._on_failure()
                    raise

            case CircuitBreakerState.CLOSED:
                try:
                    result = func()
                    self._reset()
                    return result
                except self.config.expected_exception:
                    self._on_failure()
                    raise

    def _on_success(self):
        """Handle successful operation"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        logger.info("Circuit breaker reset to CLOSED")

    def _on_failure(self):
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )

    def _reset(self):
        """Reset failure count on successful operation"""
        self.failure_count = min(self.failure_count, 0)


# Error Recovery Strategies
class ErrorRecoveryStrategy:
    """Base class for error recovery strategies"""

    def can_recover(self, error: Exception, context: ErrorContext) -> bool:
        """Check if error can be recovered"""
        return False

    def recover(self, error: Exception, context: ErrorContext) -> Any:
        """Attempt to recover from error"""
        raise NotImplementedError


class DataRecoveryStrategy(ErrorRecoveryStrategy):
    """Recovery strategy for data-related errors"""

    def can_recover(self, error: Exception, context: ErrorContext) -> bool:
        """Check if data error can be recovered"""
        return isinstance(error, (DataProcessingError, InsufficientDataError))

    def recover(self, error: Exception, context: ErrorContext) -> Any:
        """Attempt to recover from data error"""
        match error:
            case InsufficientDataError():
                logger.warning(f"Using synthetic data for {context.installation_id}")
                return self._generate_synthetic_data(context)
            case DataProcessingError():
                logger.warning(f"Using cached data for {context.operation}")
                return self._get_cached_data(context)
            case _:
                raise error

    def _generate_synthetic_data(self, context: ErrorContext) -> Any:
        """Generate synthetic data as fallback"""
        # Implementation would generate realistic synthetic data
        return None

    def _get_cached_data(self, context: ErrorContext) -> Any:
        """Retrieve cached data as fallback"""
        # Implementation would retrieve from cache
        return None


class WeatherRecoveryStrategy(ErrorRecoveryStrategy):
    """Recovery strategy for weather API errors"""

    def can_recover(self, error: Exception, context: ErrorContext) -> bool:
        """Check if weather error can be recovered"""
        return isinstance(error, WeatherAPIError)

    def recover(self, error: Exception, context: ErrorContext) -> Any:
        """Attempt to recover from weather API error"""
        logger.warning(f"Using fallback weather data for {context.operation}")
        return self._get_fallback_weather_data(context)

    def _get_fallback_weather_data(self, context: ErrorContext) -> Any:
        """Get fallback weather data"""
        # Implementation would return historical averages or cached data
        return None


# Error Handler with Recovery
class ErrorHandler:
    """Centralized error handler with recovery strategies"""

    def __init__(self):
        self.recovery_strategies: list[ErrorRecoveryStrategy] = [
            DataRecoveryStrategy(),
            WeatherRecoveryStrategy(),
        ]

    def handle_error(self, error: Exception, context: ErrorContext) -> Any:
        """
        Handle error with appropriate recovery strategy

        Args:
            error: The exception that occurred
            context: Error context information

        Returns:
            Recovery result or re-raises the exception
        """
        logger.error(f"Error in {context.component}.{context.operation}: {error}")

        # Try recovery strategies
        for strategy in self.recovery_strategies:
            if strategy.can_recover(error, context):
                try:
                    logger.info(
                        f"Attempting recovery using {strategy.__class__.__name__}"
                    )
                    return strategy.recover(error, context)
                except Exception as recovery_error:
                    logger.error(f"Recovery failed: {recovery_error}")

        # No recovery possible, re-raise
        raise error


# Global error handler instance
error_handler = ErrorHandler()


# Context manager for error handling
class error_context:
    """Context manager for enhanced error handling"""

    def __init__(self, operation: str, component: str, **kwargs):
        self.context = ErrorContext(
            operation=operation, component=component, timestamp=time.time(), **kwargs
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            try:
                error_handler.handle_error(exc_val, self.context)
                # If recovery succeeded, suppress the exception
                return True
            except Exception:
                # Recovery failed, let exception propagate
                return False
        return False


# Utility functions
def validate_data_requirements(data, min_samples: int, operation: str):
    """Validate data meets minimum requirements"""
    if data is None or len(data) < min_samples:
        available = len(data) if data is not None else 0
        raise InsufficientDataError(
            f"Insufficient data for {operation}: need {min_samples}, got {available}",
            required_samples=min_samples,
            available_samples=available,
        )


def validate_model_performance(metrics: dict[str, float], min_r2: float = 0.5):
    """Validate model performance meets requirements"""
    r2_score = metrics.get("r2", 0.0)
    if r2_score < min_r2:
        raise ModelTrainingError(
            f"Model performance below threshold: R² = {r2_score:.3f} < {min_r2}",
            details=metrics,
        )


# Example usage decorators with default configs
retry_weather_api = retry_async(
    RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        retry_on_exceptions=(WeatherAPIError, ConnectionError, TimeoutError),
    )
)

retry_data_processing = retry_sync(
    RetryConfig(
        max_attempts=2, base_delay=1.0, retry_on_exceptions=(DataProcessingError,)
    )
)


if __name__ == "__main__":
    # Test configuration constants
    TEST_FAILURE_PROBABILITY = 0.7  # Probability of failure in example test functions

    # Example usage
    @retry_sync()
    def example_sync_function():
        """Example sync function with retry"""

        if random.random() < TEST_FAILURE_PROBABILITY:
            raise DataProcessingError("Random failure for testing")
        return "Success!"

    @retry_async()
    async def example_async_function():
        """Example async function with retry"""

        if random.random() < TEST_FAILURE_PROBABILITY:
            raise WeatherAPIError("Random API failure for testing")
        return "Async Success!"

    # Test synchronous retry
    try:
        result = example_sync_function()
        print(f"Sync result: {result}")
    except RetryExhaustedError as e:
        print(f"Sync function failed after all retries: {e}")

    # Test asynchronous retry
    async def test_async():
        try:
            result = await example_async_function()
            print(f"Async result: {result}")
        except RetryExhaustedError as e:
            print(f"Async function failed after all retries: {e}")

    import asyncio

    asyncio.run(test_async())
