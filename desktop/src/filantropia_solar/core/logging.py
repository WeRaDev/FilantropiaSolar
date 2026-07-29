"""
Comprehensive logging framework for FilantropiaSolar application.

This module provides structured logging, multiple formatters, handlers,
and performance tracking capabilities.
"""

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import functools
import json
import logging
import logging.handlers
from pathlib import Path
import sys
import threading
import time
import traceback
from typing import Any, ClassVar, Optional

from .config import get_settings


class LogFormat(StrEnum):
    """Log format types."""

    SIMPLE = "simple"
    DETAILED = "detailed"
    JSON = "json"
    COLORED = "colored"


@dataclass
class LogContext:
    """Logging context for structured logging."""

    user_id: str | None = None
    request_id: str | None = None
    session_id: str | None = None
    operation: str | None = None
    component: str | None = None
    extra_data: dict[str, Any] = field(default_factory=dict)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for better readability."""

    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        log_color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
            ]:
                log_entry[key] = value

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class PerformanceLogger:
    """Performance monitoring and logging."""

    def __init__(self, logger: logging.Logger):
        """Initialize performance logger."""
        self.logger = logger
        self._timers: dict[str, float] = {}
        self._counters: dict[str, int] = {}
        self._lock = threading.Lock()

    def start_timer(self, name: str) -> None:
        """Start a performance timer."""
        with self._lock:
            self._timers[name] = time.perf_counter()

    def stop_timer(self, name: str) -> float:
        """Stop a performance timer and log the duration."""
        with self._lock:
            start_time = self._timers.pop(name, None)
            if start_time is None:
                self.logger.warning(f"Timer '{name}' was not started")
                return 0.0

            duration = time.perf_counter() - start_time
            self.logger.info(
                f"Performance: {name} took {duration:.4f} seconds",
                extra={"duration": duration, "operation": name, "metric_type": "timer"},
            )
            return duration

    def increment_counter(self, name: str, value: int = 1) -> None:
        """Increment a counter metric."""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value
            self.logger.debug(
                f"Counter: {name} = {self._counters[name]}",
                extra={
                    "counter": name,
                    "value": self._counters[name],
                    "metric_type": "counter",
                },
            )

    def get_counter(self, name: str) -> int:
        """Get current counter value."""
        return self._counters.get(name, 0)

    def reset_counter(self, name: str) -> None:
        """Reset a counter to zero."""
        with self._lock:
            self._counters[name] = 0

    @contextmanager
    def timer(self, name: str):
        """Context manager for timing operations."""
        self.start_timer(name)
        try:
            yield
        finally:
            self.stop_timer(name)


class LoggingManager:
    """Centralized logging management."""

    _instance: Optional["LoggingManager"] = None
    _initialized: bool = False
    _local: threading.local

    def __new__(cls) -> "LoggingManager":
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize logging manager."""
        if not self._initialized:
            self._local = threading.local()
            self.setup_logging()
            self._initialized = True

    def setup_logging(self) -> None:
        """Setup application logging configuration."""
        settings = get_settings()

        # Clear existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Set root logger level
        root_logger.setLevel(getattr(logging, settings.log_level.value))

        # Setup handlers
        handlers: list[logging.Handler] = []

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        if settings.debug:
            console_handler.setFormatter(
                ColoredFormatter(
                    fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                ),
            )
        else:
            console_handler.setFormatter(logging.Formatter(settings.log_format))
        handlers.append(console_handler)

        # File handler
        if settings.log_file:
            log_file_path = Path(settings.log_file)
            if not log_file_path.is_absolute():
                log_file_path = settings.logs_dir / log_file_path

            log_file_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler: logging.Handler
            if settings.log_rotation:
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file_path,
                    maxBytes=10 * 1024 * 1024,  # 10MB
                    backupCount=settings.log_retention,
                    encoding="utf-8",
                )
            else:
                file_handler = logging.FileHandler(log_file_path, encoding="utf-8")

            file_handler.setFormatter(JSONFormatter())
            handlers.append(file_handler)

        # Add handlers to root logger
        for handler in handlers:
            root_logger.addHandler(handler)

        # Setup application logger
        self.app_logger = logging.getLogger("filantropia_solar")
        self.performance_logger = PerformanceLogger(self.app_logger)

        # Log startup
        self.app_logger.info(
            f"Logging initialized - Level: {settings.log_level.value}, "
            f"Environment: {settings.environment.value}",
        )

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance."""
        return logging.getLogger(f"filantropia_solar.{name}")

    def get_performance_logger(self) -> PerformanceLogger:
        """Get performance logger instance."""
        return self.performance_logger

    def set_context(self, context: LogContext) -> None:
        """Set logging context for structured logging."""
        # Store context in thread-local storage
        self._local.context = context

    def get_context(self) -> LogContext | None:
        """Get current logging context."""
        if hasattr(self, "_local") and hasattr(self._local, "context"):
            return self._local.context
        return None

    def clear_context(self) -> None:
        """Clear current logging context."""
        if hasattr(self, "_local"):
            self._local.context = None


# Global logging manager instance
logging_manager = LoggingManager()


def get_logger(name: str = __name__) -> logging.Logger:
    """Get a logger instance."""
    return logging_manager.get_logger(name)


def get_performance_logger() -> PerformanceLogger:
    """Get performance logger instance."""
    return logging_manager.get_performance_logger()


def setup_logging() -> None:
    """Setup application logging."""
    logging_manager.setup_logging()


def log_performance(operation_name: str | None = None) -> Callable:
    """Decorator for logging function performance.

    If `operation_name` is provided, it will be used as the metric name; otherwise
    the fully qualified function name is used.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            perf_logger = get_performance_logger()
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            with perf_logger.timer(op_name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def log_exceptions(logger: logging.Logger | None = None) -> Callable:
    """Decorator for logging function exceptions."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"Exception in {func.__module__}.{func.__name__}: {e!s}",
                    extra={
                        "function": func.__name__,
                        "module": func.__module__,
                        "args": str(args)[:200] if args else None,
                        "kwargs": str(kwargs)[:200] if kwargs else None,
                        "exception_type": type(e).__name__,
                    },
                )
                raise

        return wrapper

    return decorator


@contextmanager
def log_context(context: LogContext):
    """Context manager for structured logging."""
    logging_manager.set_context(context)
    try:
        yield
    finally:
        logging_manager.clear_context()


class ContextFilter(logging.Filter):
    """Filter to add context information to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context information to log record."""
        context = logging_manager.get_context()
        if context:
            for field, value in context.__dict__.items():
                if value is not None:
                    setattr(record, field, value)
        return True


# Add context filter to all loggers
context_filter = ContextFilter()
logging.getLogger().addFilter(context_filter)


# Convenience functions for common logging patterns
def log_startup(component: str, version: str, config_summary: dict[str, Any]) -> None:
    """Log application startup information."""
    logger = get_logger("startup")
    logger.info(
        f"{component} v{version} starting",
        extra={
            "component": component,
            "version": version,
            "config": config_summary,
            "event_type": "startup",
        },
    )


def log_shutdown(component: str) -> None:
    """Log application shutdown."""
    logger = get_logger("shutdown")
    logger.info(
        f"{component} shutting down",
        extra={"component": component, "event_type": "shutdown"},
    )


def log_user_action(user_id: str, action: str, details: dict[str, Any]) -> None:
    """Log user actions for audit trail."""
    logger = get_logger("audit")
    logger.info(
        f"User action: {action}",
        extra={
            "user_id": user_id,
            "action": action,
            "details": details,
            "event_type": "user_action",
        },
    )


def log_model_operation(
    operation: str,
    model_name: str,
    performance: dict[str, Any],
) -> None:
    """Log ML model operations."""
    logger = get_logger("ml")
    logger.info(
        f"Model operation: {operation}",
        extra={
            "operation": operation,
            "model_name": model_name,
            "performance": performance,
            "event_type": "model_operation",
        },
    )


def log_api_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration: float,
    user_id: str | None = None,
) -> None:
    """Log API requests."""
    logger = get_logger("api")
    logger.info(
        f"{method} {endpoint} - {status_code}",
        extra={
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration": duration,
            "user_id": user_id,
            "event_type": "api_request",
        },
    )


def log_data_processing(
    operation: str,
    dataset: str,
    record_count: int,
    duration: float,
    success: bool,
) -> None:
    """Log data processing operations."""
    logger = get_logger("data")
    logger.info(
        f"Data processing: {operation}",
        extra={
            "operation": operation,
            "dataset": dataset,
            "record_count": record_count,
            "duration": duration,
            "success": success,
            "event_type": "data_processing",
        },
    )
