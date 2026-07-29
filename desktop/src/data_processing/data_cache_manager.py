#!/usr/bin/env python3
"""
Smart Data Cache Manager
Optimized caching system for FilantropiaSolar application that:
1. Loads data once and caches processed datasets
2. Stores trained ML models for instant reuse
3. Handles incremental updates when new data is added
4. Maintains database integrity with deduplication
"""

from datetime import datetime, timedelta
import hashlib
import json
import logging
from pathlib import Path
import pickle  # nosec B403 - local cache serialization only; loads restricted to app-written files
import sqlite3
from typing import Any

import joblib
import pandas as pd

logger = logging.getLogger(__name__)


try:
    from filantropia_solar.utils.paths import get_app_cache_dir
except Exception:
    try:
        from src.utils.paths import get_app_cache_dir
    except Exception:
        from utils.paths import get_app_cache_dir


class DataCacheManager:
    """
    Smart cache manager for solar energy data and ML models.

    Features:
    - SQLite database for metadata management
    - Pickle caching for fast data loading
    - ML model versioning and storage
    - Automatic data deduplication
    - Cache validation and integrity checks
    """

    def __init__(self, cache_dir: str = "cache", db_name: str = "filantropia_cache.db"):
        """Initialize the cache manager.

        On Windows, cache_dir is placed under %LOCALAPPDATA%/FilantropiaSolar by default for write access.
        """
        # Use user-writable cache directory
        try:
            base_cache = get_app_cache_dir()
            self.cache_dir = base_cache if cache_dir == "cache" else Path(cache_dir)
        except Exception:
            self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        self.db_path = self.cache_dir / db_name
        self.data_cache_dir = self.cache_dir / "data"
        self.model_cache_dir = self.cache_dir / "models"

        # Create cache directories
        self.data_cache_dir.mkdir(exist_ok=True)
        self.model_cache_dir.mkdir(exist_ok=True)

        # Initialize database
        self._init_database()

        logger.info(f"Data cache manager initialized with cache dir: {self.cache_dir}")

    def _init_database(self):
        """Initialize SQLite database for cache metadata."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS data_cache (
                    cache_key TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    data_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_type TEXT NOT NULL,
                    metadata TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_cache (
                    model_key TEXT PRIMARY KEY,
                    installation_id TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    performance_metrics TEXT,
                    training_data_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS installation_metadata (
                    installation_id TEXT PRIMARY KEY,
                    location TEXT NOT NULL,
                    capacity_kwp REAL NOT NULL,
                    data_start_date DATE,
                    data_end_date DATE,
                    record_count INTEGER,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    def _compute_data_hash(self, data: Any) -> str:
        """Compute hash for data integrity checking."""
        if isinstance(data, pd.DataFrame):
            # Hash based on shape, columns, and sample of data
            content = f"{data.shape}_{list(data.columns)}_{data.head().to_string()}"
        elif isinstance(data, dict):
            content = json.dumps(data, sort_keys=True, default=str)
        else:
            content = str(data)

        return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()

    def _get_cache_key(self, data_type: str, identifier: str) -> str:
        """Generate cache key for data."""
        return f"{data_type}_{identifier}"

    def is_cached(self, data_type: str, identifier: str) -> bool:
        """Check if data is cached and valid."""
        cache_key = self._get_cache_key(data_type, identifier)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT file_path FROM data_cache WHERE cache_key = ?",
                (cache_key,),
            )
            result = cursor.fetchone()

            if result:
                file_path = Path(result[0])
                return file_path.exists()

        return False

    def cache_data(
        self,
        data: Any,
        data_type: str,
        identifier: str,
        metadata: dict | None = None,
    ) -> bool:
        """Cache data with metadata."""
        try:
            cache_key = self._get_cache_key(data_type, identifier)
            data_hash = self._compute_data_hash(data)
            file_path = self.data_cache_dir / f"{cache_key}.pkl"

            # Save data
            with Path(file_path).open("wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            # Update database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO data_cache
                    (cache_key, file_path, data_hash, data_type, metadata, last_accessed)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (
                        cache_key,
                        str(file_path),
                        data_hash,
                        data_type,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
                conn.commit()

            logger.info(f"Cached data: {cache_key}")
            return True

        except Exception as e:
            logger.error(f"Error caching data {cache_key}: {e}")
            return False

    def load_cached_data(self, data_type: str, identifier: str) -> Any | None:
        """Load cached data."""
        try:
            cache_key = self._get_cache_key(data_type, identifier)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT file_path FROM data_cache WHERE cache_key = ?",
                    (cache_key,),
                )
                result = cursor.fetchone()

                if result:
                    file_path = Path(result[0])
                    if file_path.exists():
                        # Update last accessed time
                        conn.execute(
                            "UPDATE data_cache SET last_accessed = CURRENT_TIMESTAMP WHERE cache_key = ?",
                            (cache_key,),
                        )
                        conn.commit()

                        # Load data
                        with Path(file_path).open("rb") as f:
                            data = pickle.load(f)  # nosec B301 - loads only cache files written by this application

                        logger.info(f"Loaded cached data: {cache_key}")
                        return data

            return None

        except Exception as e:
            logger.error(f"Error loading cached data {cache_key}: {e}")
            # Auto-invalidate corrupt/stale cache entries
            import contextlib

            with contextlib.suppress(Exception):
                self.invalidate_cache(data_type, identifier)
            return None

    def get_data_cache_entry(
        self, data_type: str, identifier: str
    ) -> dict[str, Any] | None:
        """Return metadata row for a cached data entry if present."""
        try:
            cache_key = self._get_cache_key(data_type, identifier)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT cache_key, file_path, data_hash, created_at, last_accessed, data_type, metadata
                    FROM data_cache WHERE cache_key = ?
                    """,
                    (cache_key,),
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "cache_key": row[0],
                        "file_path": row[1],
                        "data_hash": row[2],
                        "created_at": row[3],
                        "last_accessed": row[4],
                        "data_type": row[5],
                        "metadata": row[6],
                    }
            return None
        except Exception as e:
            logger.error(f"Error reading cache metadata for {cache_key}: {e}")
            return None

    def get_cache_status(self) -> dict[str, Any]:
        """Get comprehensive cache status information."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get data cache stats
                cursor.execute("SELECT COUNT(*) FROM data_cache")
                data_cache_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM model_cache")
                model_cache_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM installation_metadata")
                installation_count = cursor.fetchone()[0]

                # Get disk usage
                data_cache_size = sum(
                    f.stat().st_size
                    for f in self.data_cache_dir.rglob("*")
                    if f.is_file()
                )
                model_cache_size = sum(
                    f.stat().st_size
                    for f in self.model_cache_dir.rglob("*")
                    if f.is_file()
                )
                total_size = data_cache_size + model_cache_size

                # Get recent activity
                cursor.execute(
                    "SELECT COUNT(*) FROM data_cache WHERE last_accessed > datetime('now', '-1 day')",
                )
                recent_data_access = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM model_cache WHERE last_used > datetime('now', '-1 day')",
                )
                recent_model_access = cursor.fetchone()[0]

                return {
                    "data_cache": {
                        "cached_items": data_cache_count,
                        "size_mb": data_cache_size / (1024 * 1024),
                        "recent_access": recent_data_access,
                    },
                    "model_cache": {
                        "cached_models": model_cache_count,
                        "size_mb": model_cache_size / (1024 * 1024),
                        "recent_access": recent_model_access,
                    },
                    "installations": {"count": installation_count},
                    "total_size_mb": total_size / (1024 * 1024),
                    "cache_directory": str(self.cache_dir),
                }

        except Exception as e:
            logger.error(f"Error getting cache status: {e}")
            return {"error": str(e)}

    def clear_cache(self, cache_type: str = "all") -> bool:
        """Clear cache data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if cache_type in {"all", "data"}:
                    # Clear data cache files
                    for file_path in self.data_cache_dir.rglob("*.pkl"):
                        file_path.unlink()

                    # Clear database entries
                    conn.execute("DELETE FROM data_cache")
                    logger.info("Cleared data cache")

                if cache_type in {"all", "models"}:
                    # Clear model cache files
                    for file_path in self.model_cache_dir.rglob("*"):
                        if file_path.is_file():
                            file_path.unlink()

                    # Clear database entries
                    conn.execute("DELETE FROM model_cache")
                    logger.info("Cleared model cache")

                if cache_type == "all":
                    conn.execute("DELETE FROM installation_metadata")
                    logger.info("Cleared installation metadata")

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False

    def validate_cache(self) -> dict[str, Any]:
        """Validate cache integrity."""
        validation_results: dict[str, Any] = {
            "valid_entries": 0,
            "invalid_entries": 0,
            "missing_files": 0,
            "orphaned_files": 0,
            "issues": [],
        }

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Check data cache integrity
                cursor.execute("SELECT cache_key, file_path FROM data_cache")
                for cache_key, file_path in cursor.fetchall():
                    if not Path(file_path).exists():
                        validation_results["missing_files"] += 1
                        validation_results["issues"].append(
                            f"Missing file for {cache_key}: {file_path}",
                        )
                    else:
                        validation_results["valid_entries"] += 1

                # Check model cache integrity
                cursor.execute("SELECT model_key, file_path FROM model_cache")
                for model_key, file_path in cursor.fetchall():
                    if not Path(file_path).exists():
                        validation_results["missing_files"] += 1
                        validation_results["issues"].append(
                            f"Missing model file for {model_key}: {file_path}",
                        )
                    else:
                        validation_results["valid_entries"] += 1

                logger.info(
                    f"Cache validation completed: {validation_results['valid_entries']} valid, {validation_results['invalid_entries'] + validation_results['missing_files']} issues",
                )

        except Exception as e:
            logger.error(f"Error validating cache: {e}")
            validation_results["issues"].append(f"Validation error: {e}")

        return validation_results

    def cache_model(
        self,
        model: Any,
        installation_id: str,
        model_type: str,
        performance_metrics: dict,
        training_data_hash: str,
    ) -> bool:
        """Cache trained ML model."""
        try:
            model_key = f"{installation_id}_{model_type}"
            file_path = self.model_cache_dir / f"{model_key}.joblib"

            # Save model
            joblib.dump(model, file_path, compress=3)

            # Update database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO model_cache
                    (model_key, installation_id, model_type, file_path,
                     performance_metrics, training_data_hash, last_used)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (
                        model_key,
                        installation_id,
                        model_type,
                        str(file_path),
                        json.dumps(performance_metrics),
                        training_data_hash,
                    ),
                )
                conn.commit()

            logger.info(f"Cached model: {model_key}")
            return True

        except Exception as e:
            logger.error(f"Error caching model {model_key}: {e}")
            return False

    def load_cached_model(self, installation_id: str, model_type: str) -> Any | None:
        """Load cached ML model."""
        try:
            model_key = f"{installation_id}_{model_type}"

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT file_path FROM model_cache WHERE model_key = ?",
                    (model_key,),
                )
                result = cursor.fetchone()

                if result:
                    file_path = Path(result[0])
                    if file_path.exists():
                        # Update last used time
                        conn.execute(
                            "UPDATE model_cache SET last_used = CURRENT_TIMESTAMP WHERE model_key = ?",
                            (model_key,),
                        )
                        conn.commit()

                        # Load model
                        model = joblib.load(file_path)
                        logger.info(f"Loaded cached model: {model_key}")
                        return model

            return None

        except Exception as e:
            logger.error(f"Error loading cached model {model_key}: {e}")
            return None

    # Orphaned code removed - was causing duplicate exception handler (B025)

    def cleanup_old_cache(self, days_old: int = 30) -> int:
        """Clean up old cache entries."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            removed_count = 0

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get old entries
                cursor.execute(
                    """
                    SELECT cache_key, file_path FROM data_cache
                    WHERE last_accessed < ?
                """,
                    (cutoff_date,),
                )

                old_entries = cursor.fetchall()

                for _cache_key, file_path in old_entries:
                    # Remove file
                    try:
                        Path(file_path).unlink(missing_ok=True)
                        removed_count += 1
                    except Exception as e:
                        logger.warning(f"Could not remove cache file {file_path}: {e}")

                # Remove database entries
                cursor.execute(
                    "DELETE FROM data_cache WHERE last_accessed < ?",
                    (cutoff_date,),
                )
                conn.commit()

            logger.info(f"Cleaned up {removed_count} old cache entries")
            return removed_count

        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")
            return 0

    def invalidate_cache(
        self,
        data_type: str | None = None,
        identifier: str | None = None,
    ):
        """Invalidate cache entries."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if data_type and identifier:
                    # Invalidate specific entry
                    cache_key = self._get_cache_key(data_type, identifier)
                    cursor.execute(
                        "SELECT file_path FROM data_cache WHERE cache_key = ?",
                        (cache_key,),
                    )
                    result = cursor.fetchone()
                    if result:
                        Path(result[0]).unlink(missing_ok=True)
                        cursor.execute(
                            "DELETE FROM data_cache WHERE cache_key = ?",
                            (cache_key,),
                        )
                        logger.info(f"Invalidated cache entry: {cache_key}")
                elif data_type:
                    # Invalidate all entries of specific type
                    cursor.execute(
                        "SELECT file_path FROM data_cache WHERE data_type = ?",
                        (data_type,),
                    )
                    files = cursor.fetchall()
                    for (file_path,) in files:
                        Path(file_path).unlink(missing_ok=True)
                    cursor.execute(
                        "DELETE FROM data_cache WHERE data_type = ?",
                        (data_type,),
                    )
                    logger.info(f"Invalidated all cache entries of type: {data_type}")
                else:
                    # Invalidate all cache
                    cursor.execute("SELECT file_path FROM data_cache")
                    files = cursor.fetchall()
                    for (file_path,) in files:
                        Path(file_path).unlink(missing_ok=True)
                    cursor.execute("DELETE FROM data_cache")
                    logger.info("Invalidated entire data cache")

                conn.commit()

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
