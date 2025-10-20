"""
Performance optimization utilities for FilantropiaSolar.

This module provides performance monitoring, optimization helpers,
and caching mechanisms to improve application performance.
"""

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import functools
import gc
import threading
import time
from typing import Any, Optional, TypeVar

from ..core import get_logger

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])

logger = get_logger("performance")


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""

    function_name: str
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    avg_time: float = 0.0
    last_called: datetime | None = None

    def update(self, execution_time: float) -> None:
        """Update metrics with new execution time."""
        self.call_count += 1
        self.total_time += execution_time
        self.min_time = min(self.min_time, execution_time)
        self.max_time = max(self.max_time, execution_time)
        self.avg_time = self.total_time / self.call_count
        self.last_called = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "function_name": self.function_name,
            "call_count": self.call_count,
            "total_time": self.total_time,
            "min_time": self.min_time if self.min_time != float("inf") else 0.0,
            "max_time": self.max_time,
            "avg_time": self.avg_time,
            "last_called": self.last_called.isoformat() if self.last_called else None,
        }


class PerformanceMonitor:
    """Global performance monitoring system."""

    _instance: Optional["PerformanceMonitor"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "PerformanceMonitor":
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize performance monitor."""
        if not hasattr(self, "_initialized"):
            self._metrics: dict[str, PerformanceMetrics] = {}
            self._lock = threading.Lock()
            self._initialized = True

    def record_execution(self, function_name: str, execution_time: float) -> None:
        """Record function execution time."""
        with self._lock:
            if function_name not in self._metrics:
                self._metrics[function_name] = PerformanceMetrics(function_name)
            self._metrics[function_name].update(execution_time)

    def get_metrics(
        self, function_name: str | None = None
    ) -> dict[str, Any] | dict[str, dict[str, Any]]:
        """Get performance metrics."""
        with self._lock:
            if function_name:
                metrics = self._metrics.get(function_name)
                return metrics.to_dict() if metrics else {}
            else:
                return {
                    name: metrics.to_dict() for name, metrics in self._metrics.items()
                }

    def reset_metrics(self, function_name: str | None = None) -> None:
        """Reset performance metrics."""
        with self._lock:
            if function_name and function_name in self._metrics:
                del self._metrics[function_name]
            elif function_name is None:
                self._metrics.clear()

    def get_slowest_functions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get slowest functions by average execution time."""
        with self._lock:
            sorted_metrics = sorted(
                self._metrics.values(), key=lambda m: m.avg_time, reverse=True
            )
            return [m.to_dict() for m in sorted_metrics[:limit]]


# Global performance monitor instance
perf_monitor = PerformanceMonitor()


def performance_monitor(func: F) -> F:
    """
    Decorator to monitor function performance.

    Args:
        func: Function to monitor

    Returns:
        Wrapped function with performance monitoring
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            execution_time = time.perf_counter() - start_time
            function_name = f"{func.__module__}.{func.__name__}"
            perf_monitor.record_execution(function_name, execution_time)

    return wrapper


class LRUCache:
    """Thread-safe Least Recently Used cache implementation."""

    def __init__(self, max_size: int = 128, ttl: float | None = None):
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum number of items to cache
            ttl: Time-to-live in seconds (optional)
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: dict[Any, float] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: Any) -> Any | None:
        """Get item from cache."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            # Check TTL if enabled
            if self.ttl is not None:
                timestamp = self._timestamps.get(key, 0)
                if time.time() - timestamp > self.ttl:
                    del self._cache[key]
                    del self._timestamps[key]
                    self._misses += 1
                    return None

            # Move to end (mark as recently used)
            value = self._cache[key]
            self._cache.move_to_end(key)
            self._hits += 1
            return value

    def put(self, key: Any, value: Any) -> None:
        """Put item in cache."""
        with self._lock:
            if key in self._cache:
                # Update existing item
                self._cache[key] = value
                self._cache.move_to_end(key)
            else:
                # Add new item
                self._cache[key] = value

                # Remove oldest item if cache is full
                if len(self._cache) > self.max_size:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                    if oldest_key in self._timestamps:
                        del self._timestamps[oldest_key]

            # Update timestamp if TTL is enabled
            if self.ttl is not None:
                self._timestamps[key] = time.time()

    def clear(self) -> None:
        """Clear all cached items."""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "ttl": self.ttl,
            }


def lru_cache(max_size: int = 128, ttl: float | None = None):
    """
    LRU cache decorator with optional TTL.

    Args:
        max_size: Maximum number of cached results
        ttl: Time-to-live in seconds (optional)

    Returns:
        Decorator function
    """

    def decorator(func: F) -> F:
        cache = LRUCache(max_size=max_size, ttl=ttl)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from arguments
            key = str(args) + str(sorted(kwargs.items()))

            # Try to get from cache
            result = cache.get(key)
            if result is not None:
                return result

            # Compute result and cache it
            result = func(*args, **kwargs)
            cache.put(key, result)

            return result

        # Add cache management methods
        wrapper.cache_info = cache.stats
        wrapper.cache_clear = cache.clear

        return wrapper

    return decorator


class BatchProcessor:
    """Batch processing utility for improved performance."""

    def __init__(
        self,
        batch_size: int = 100,
        max_wait_time: float = 1.0,
        processor_func: Callable | None = None,
    ):
        """
        Initialize batch processor.

        Args:
            batch_size: Maximum items per batch
            max_wait_time: Maximum time to wait before processing batch
            processor_func: Function to process batches
        """
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.processor_func = processor_func

        self._batch: list[Any] = []
        self._batch_lock = threading.Lock()
        self._last_process_time = time.time()
        self._processing_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def add_item(self, item: Any) -> None:
        """Add item to batch for processing."""
        with self._batch_lock:
            self._batch.append(item)

            # Process if batch is full or max wait time exceeded
            should_process = (
                len(self._batch) >= self.batch_size
                or time.time() - self._last_process_time >= self.max_wait_time
            )

            if should_process and self.processor_func:
                self._process_batch()

    def _process_batch(self) -> None:
        """Process current batch."""
        if not self._batch:
            return

        batch_to_process = self._batch.copy()
        self._batch.clear()
        self._last_process_time = time.time()

        try:
            self.processor_func(batch_to_process)
        except Exception as e:
            logger.error(f"Error processing batch: {e}")

    def flush(self) -> None:
        """Process any remaining items in batch."""
        with self._batch_lock:
            if self._batch and self.processor_func:
                self._process_batch()

    def start_background_processing(self) -> None:
        """Start background thread for processing batches."""
        if self._processing_thread and self._processing_thread.is_alive():
            return

        self._stop_event.clear()
        self._processing_thread = threading.Thread(
            target=self._background_processor, daemon=True
        )
        self._processing_thread.start()

    def stop_background_processing(self) -> None:
        """Stop background processing thread."""
        self._stop_event.set()
        if self._processing_thread:
            self._processing_thread.join()
        self.flush()  # Process any remaining items

    def _background_processor(self) -> None:
        """Background thread for processing batches."""
        while not self._stop_event.is_set():
            time.sleep(0.1)  # Small delay to avoid busy waiting

            with self._batch_lock:
                if (
                    self._batch
                    and time.time() - self._last_process_time >= self.max_wait_time
                    and self.processor_func
                ):
                    self._process_batch()


class MemoryOptimizer:
    """Memory optimization utilities."""

    @staticmethod
    def force_garbage_collection() -> dict[str, int]:
        """Force garbage collection and return statistics."""
        before_objects = len(gc.get_objects())
        collected = gc.collect()
        after_objects = len(gc.get_objects())

        stats = {
            "objects_before": before_objects,
            "objects_after": after_objects,
            "objects_collected": collected,
            "objects_freed": before_objects - after_objects,
        }

        logger.debug(f"Garbage collection completed: {stats}")
        return stats

    @staticmethod
    def get_memory_usage() -> dict[str, Any]:
        """Get current memory usage information."""
        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()

            return {
                "rss": memory_info.rss,  # Resident Set Size
                "vms": memory_info.vms,  # Virtual Memory Size
                "percent": process.memory_percent(),
                "available": psutil.virtual_memory().available,
                "unit": "bytes",
            }
        except ImportError:
            # Fallback without psutil
            import sys

            return {
                "objects_count": len(gc.get_objects()),
                "gc_counts": gc.get_counts(),
                "sys_getsizeof_limit": sys.getsizeof({}),
                "unit": "objects/bytes",
            }

    @staticmethod
    def optimize_dataframe_memory(df) -> Any:
        """Optimize pandas DataFrame memory usage."""
        try:
            import pandas as pd

            if not isinstance(df, pd.DataFrame):
                return df

            original_memory = df.memory_usage(deep=True).sum()

            # Optimize numeric columns
            for col in df.columns:
                col_type = df[col].dtype

                if pd.api.types.is_integer_dtype(col_type):
                    # Downcast integers
                    df[col] = pd.to_numeric(df[col], downcast="integer")

                elif pd.api.types.is_float_dtype(col_type):
                    # Downcast floats
                    df[col] = pd.to_numeric(df[col], downcast="float")

                elif pd.api.types.is_object_dtype(col_type):
                    # Try to convert to category if low cardinality
                    unique_count = df[col].nunique()
                    total_count = len(df[col])

                    if unique_count / total_count < 0.5:  # Less than 50% unique
                        df[col] = df[col].astype("category")

            optimized_memory = df.memory_usage(deep=True).sum()
            reduction_ratio = 1 - optimized_memory / original_memory

            logger.info(
                f"DataFrame memory optimized: {original_memory:,} -> {optimized_memory:,} bytes "
                f"({reduction_ratio:.1%} reduction)"
            )

            return df

        except ImportError:
            logger.warning("pandas not available for DataFrame memory optimization")
            return df


def profile_memory_usage(func: F) -> F:
    """
    Decorator to profile memory usage of a function.

    Args:
        func: Function to profile

    Returns:
        Wrapped function with memory profiling
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        optimizer = MemoryOptimizer()

        # Get memory usage before function execution
        before_memory = optimizer.get_memory_usage()

        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Get memory usage after function execution
            after_memory = optimizer.get_memory_usage()

            # Calculate memory difference
            if "rss" in before_memory and "rss" in after_memory:
                memory_diff = after_memory["rss"] - before_memory["rss"]
                logger.debug(
                    f"Memory usage for {func.__name__}: {memory_diff:+,} bytes"
                )

    return wrapper


def chunked_processing(
    items: list[T],
    chunk_size: int = 1000,
    processor_func: Callable[[list[T]], Any] | None = None,
) -> list[Any]:
    """
    Process large lists in chunks for better memory performance.

    Args:
        items: List of items to process
        chunk_size: Number of items per chunk
        processor_func: Function to process each chunk

    Returns:
        List of processed results
    """
    results = []

    for i in range(0, len(items), chunk_size):
        chunk = items[i : i + chunk_size]

        if processor_func:
            result = processor_func(chunk)
            results.append(result)
        else:
            results.extend(chunk)

        # Force garbage collection after each chunk
        if i % (chunk_size * 10) == 0:  # Every 10 chunks
            gc.collect()

    return results


@performance_monitor
def benchmark_function(
    func: Callable, *args, iterations: int = 100, warmup_iterations: int = 10, **kwargs
) -> dict[str, float]:
    """
    Benchmark a function's performance.

    Args:
        func: Function to benchmark
        *args: Arguments to pass to function
        iterations: Number of benchmark iterations
        warmup_iterations: Number of warmup iterations
        **kwargs: Keyword arguments to pass to function

    Returns:
        Dictionary with benchmark results
    """
    # Warmup runs
    for _ in range(warmup_iterations):
        func(*args, **kwargs)

    # Benchmark runs
    times = []
    for _ in range(iterations):
        start_time = time.perf_counter()
        func(*args, **kwargs)
        end_time = time.perf_counter()
        times.append(end_time - start_time)

    # Calculate statistics
    total_time = sum(times)
    avg_time = total_time / len(times)
    min_time = min(times)
    max_time = max(times)

    # Calculate standard deviation
    variance = sum((t - avg_time) ** 2 for t in times) / len(times)
    std_dev = variance**0.5

    return {
        "iterations": iterations,
        "total_time": total_time,
        "avg_time": avg_time,
        "min_time": min_time,
        "max_time": max_time,
        "std_dev": std_dev,
        "ops_per_second": 1 / avg_time if avg_time > 0 else float("inf"),
    }
