"""
Base classes and interfaces for data processing in FilantropiaSolar.

This module defines abstract base classes and interfaces following SOLID principles
for data loading, processing, validation, and transformation operations.
"""

import abc
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar

import numpy as np
import pandas as pd

from ..core import (
    DataError,
    DataLoadingError,
    DataValidationError,
    ValidationError,
    get_logger,
    log_exceptions,
    log_performance,
)

# Type variables for generic interfaces
T = TypeVar('T')
DataFrameType = TypeVar('DataFrameType', bound=pd.DataFrame)


@dataclass
class DataQualityReport:
    """Report containing data quality metrics and validation results."""

    total_records: int
    valid_records: int
    invalid_records: int
    missing_values: dict[str, int]
    duplicate_records: int
    outliers: dict[str, int]
    quality_score: float
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_valid(self) -> bool:
        """Check if data meets quality thresholds."""
        return self.quality_score >= 0.8 and len(self.validation_errors) == 0

    @property
    def completion_rate(self) -> float:
        """Calculate data completion rate."""
        if self.total_records == 0:
            return 0.0
        return self.valid_records / self.total_records

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return {
            'total_records': self.total_records,
            'valid_records': self.valid_records,
            'invalid_records': self.invalid_records,
            'missing_values': self.missing_values,
            'duplicate_records': self.duplicate_records,
            'outliers': self.outliers,
            'quality_score': self.quality_score,
            'completion_rate': self.completion_rate,
            'is_valid': self.is_valid,
            'validation_errors': self.validation_errors,
            'warnings': self.warnings,
            'timestamp': self.timestamp.isoformat(),
        }


class DataLoader(Protocol[T]):
    """Protocol for data loading operations."""

    def load(self, source: str | Path, **kwargs) -> T:
        """Load data from source."""
        ...

    def validate_source(self, source: str | Path) -> bool:
        """Validate data source accessibility."""
        ...


class DataValidator(Protocol[T]):
    """Protocol for data validation operations."""

    def validate(self, data: T) -> DataQualityReport:
        """Validate data quality and return report."""
        ...

    def get_validation_rules(self) -> list[str]:
        """Get list of validation rules."""
        ...


class DataTransformer(Protocol[T]):
    """Protocol for data transformation operations."""

    def transform(self, data: T, **kwargs) -> T:
        """Transform data according to business rules."""
        ...

    def get_transformation_info(self) -> dict[str, Any]:
        """Get information about applied transformations."""
        ...


class DataExporter(Protocol[T]):
    """Protocol for data export operations."""

    def export(self, data: T, destination: str | Path, format: str = "csv", **kwargs) -> bool:
        """Export data to destination."""
        ...

    def get_supported_formats(self) -> list[str]:
        """Get list of supported export formats."""
        ...


class BaseDataProcessor(abc.ABC, Generic[T]):
    """
    Abstract base class for data processors.
    
    Implements common functionality and defines the interface for data processing
    operations following the Template Method pattern.
    """

    def __init__(self, name: str):
        """
        Initialize data processor.
        
        Args:
            name: Processor identifier name
        """
        self.name = name
        self.logger = get_logger(f"data.{name}")
        self._processing_stats: dict[str, Any] = {}
        self._last_quality_report: DataQualityReport | None = None

    @abc.abstractmethod
    def _load_data(self, source: str | Path, **kwargs) -> T:
        """Load data from source (implementation specific)."""
        pass

    @abc.abstractmethod
    def _validate_data(self, data: T) -> DataQualityReport:
        """Validate loaded data (implementation specific)."""
        pass

    @abc.abstractmethod
    def _transform_data(self, data: T, **kwargs) -> T:
        """Transform data (implementation specific)."""
        pass

    def _preprocess_source(self, source: str | Path) -> str | Path:
        """Preprocess source path/URL (hook for subclasses)."""
        return source

    def _postprocess_data(self, data: T) -> T:
        """Postprocess loaded data (hook for subclasses)."""
        return data

    @log_performance("data_processing")
    @log_exceptions()
    def process(
        self,
        source: str | Path,
        validate: bool = True,
        transform: bool = True,
        **kwargs
    ) -> T:
        """
        Process data from source to final format.
        
        This is the main template method that orchestrates the data processing pipeline.
        
        Args:
            source: Data source path or URL
            validate: Whether to perform data validation
            transform: Whether to apply transformations
            **kwargs: Additional processing parameters
            
        Returns:
            Processed data
            
        Raises:
            DataLoadingError: If data loading fails
            DataValidationError: If data validation fails
        """
        self.logger.info(f"Starting data processing for {source}")
        start_time = datetime.utcnow()

        try:
            # Step 1: Preprocess source
            processed_source = self._preprocess_source(source)

            # Step 2: Load data
            self.logger.debug(f"Loading data from {processed_source}")
            data = self._load_data(processed_source, **kwargs)

            # Step 3: Postprocess loaded data
            data = self._postprocess_data(data)

            # Step 4: Validate data (if requested)
            if validate:
                self.logger.debug("Validating data quality")
                quality_report = self._validate_data(data)
                self._last_quality_report = quality_report

                if not quality_report.is_valid:
                    raise DataValidationError(
                        f"Data validation failed: {quality_report.validation_errors}",
                        validation_rules=self.get_validation_rules(),
                        failed_records=quality_report.invalid_records,
                        details={'quality_report': quality_report.to_dict()}
                    )

            # Step 5: Transform data (if requested)
            if transform:
                self.logger.debug("Applying data transformations")
                data = self._transform_data(data, **kwargs)

            # Update processing stats
            duration = (datetime.utcnow() - start_time).total_seconds()
            self._processing_stats = {
                'last_processed': datetime.utcnow().isoformat(),
                'processing_duration': duration,
                'source': str(source),
                'record_count': self._get_record_count(data),
            }

            self.logger.info(
                f"Data processing completed successfully in {duration:.2f}s",
                extra={'processing_stats': self._processing_stats}
            )

            return data

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.logger.error(f"Data processing failed after {duration:.2f}s: {e!s}")

            if isinstance(e, (DataError, ValidationError)):
                raise
            else:
                raise DataLoadingError(
                    f"Failed to process data from {source}",
                    file_path=str(source),
                    cause=e
                ) from e

    @abc.abstractmethod
    def _get_record_count(self, data: T) -> int:
        """Get number of records in data (implementation specific)."""
        pass

    def get_validation_rules(self) -> list[str]:
        """Get list of validation rules applied by this processor."""
        return ["basic_validation", "completeness_check", "type_validation"]

    def get_processing_stats(self) -> dict[str, Any]:
        """Get processing statistics."""
        return self._processing_stats.copy()

    def get_last_quality_report(self) -> DataQualityReport | None:
        """Get the last data quality report."""
        return self._last_quality_report

    def reset_stats(self) -> None:
        """Reset processing statistics."""
        self._processing_stats = {}
        self._last_quality_report = None


class PandasDataProcessor(BaseDataProcessor[pd.DataFrame]):
    """
    Base implementation for pandas DataFrame processing.
    
    Provides common functionality for CSV, Excel, and other structured data formats.
    """

    def __init__(self, name: str, encoding: str = "utf-8"):
        """
        Initialize pandas data processor.
        
        Args:
            name: Processor identifier name
            encoding: Default file encoding
        """
        super().__init__(name)
        self.encoding = encoding
        self.required_columns: list[str] = []
        self.column_types: dict[str, type] = {}
        self.value_ranges: dict[str, tuple] = {}

    def _load_data(self, source: str | Path, **kwargs) -> pd.DataFrame:
        """Load data from CSV or Excel file."""
        source_path = Path(source)

        if not source_path.exists():
            raise DataLoadingError(
                f"Data file not found: {source}",
                file_path=str(source),
                data_source="file"
            )

        try:
            if source_path.suffix.lower() == '.csv':
                df = pd.read_csv(
                    source_path,
                    encoding=kwargs.get('encoding', self.encoding),
                    **{k: v for k, v in kwargs.items() if k != 'encoding'}
                )
            elif source_path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(source_path, **kwargs)
            else:
                raise DataLoadingError(
                    f"Unsupported file format: {source_path.suffix}",
                    file_path=str(source),
                    data_source="file"
                )

            if df.empty:
                raise DataLoadingError(
                    f"Data file is empty: {source}",
                    file_path=str(source),
                    data_source="file"
                )

            return df

        except Exception as e:
            if isinstance(e, DataLoadingError):
                raise
            raise DataLoadingError(
                f"Failed to load data from {source}: {e!s}",
                file_path=str(source),
                data_source="file",
                cause=e
            ) from e

    def _validate_data(self, data: pd.DataFrame) -> DataQualityReport:
        """Validate DataFrame data quality."""
        total_records = len(data)

        # Check required columns
        missing_columns = [col for col in self.required_columns if col not in data.columns]
        validation_errors = []
        warnings = []

        if missing_columns:
            validation_errors.append(f"Missing required columns: {missing_columns}")

        # Calculate missing values per column
        missing_values = data.isnull().sum().to_dict()
        total_missing = sum(missing_values.values())

        # Check duplicate records
        duplicate_records = data.duplicated().sum()

        # Validate column types
        type_errors = 0
        for col, expected_type in self.column_types.items():
            if col in data.columns:
                try:
                    if expected_type == float:
                        pd.to_numeric(data[col], errors='raise')
                    elif expected_type == int:
                        pd.to_numeric(data[col], errors='raise', downcast='integer')
                    elif expected_type == datetime:
                        pd.to_datetime(data[col], errors='raise')
                except:
                    type_errors += 1
                    warnings.append(f"Column {col} has invalid {expected_type.__name__} values")

        # Check value ranges
        outliers = {}
        for col, (min_val, max_val) in self.value_ranges.items():
            if col in data.columns and pd.api.types.is_numeric_dtype(data[col]):
                col_outliers = ((data[col] < min_val) | (data[col] > max_val)).sum()
                outliers[col] = col_outliers

        # Calculate quality score
        completeness = 1 - (total_missing / (total_records * len(data.columns))) if total_records > 0 else 0
        uniqueness = 1 - (duplicate_records / total_records) if total_records > 0 else 1
        validity = 1 - (type_errors / len(self.column_types)) if self.column_types else 1

        quality_score = (completeness * 0.4 + uniqueness * 0.3 + validity * 0.3)

        valid_records = total_records - duplicate_records - sum(outliers.values())
        invalid_records = total_records - valid_records

        return DataQualityReport(
            total_records=total_records,
            valid_records=max(0, valid_records),
            invalid_records=invalid_records,
            missing_values=missing_values,
            duplicate_records=duplicate_records,
            outliers=outliers,
            quality_score=quality_score,
            validation_errors=validation_errors,
            warnings=warnings,
        )

    def _transform_data(self, data: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """Apply basic transformations to DataFrame."""
        transformed_data = data.copy()

        # Remove duplicates
        if kwargs.get('remove_duplicates', True):
            transformed_data = transformed_data.drop_duplicates()

        # Handle missing values
        fill_strategy = kwargs.get('fill_missing', 'drop')
        if fill_strategy == 'drop':
            transformed_data = transformed_data.dropna()
        elif fill_strategy == 'forward_fill':
            transformed_data = transformed_data.fillna(method='ffill')
        elif fill_strategy == 'mean':
            numeric_columns = transformed_data.select_dtypes(include=[np.number]).columns
            transformed_data[numeric_columns] = transformed_data[numeric_columns].fillna(
                transformed_data[numeric_columns].mean()
            )

        # Apply column type conversions
        for col, expected_type in self.column_types.items():
            if col in transformed_data.columns:
                try:
                    if expected_type == float:
                        transformed_data[col] = pd.to_numeric(transformed_data[col], errors='coerce')
                    elif expected_type == int:
                        transformed_data[col] = pd.to_numeric(
                            transformed_data[col], errors='coerce', downcast='integer'
                        )
                    elif expected_type == datetime:
                        transformed_data[col] = pd.to_datetime(transformed_data[col], errors='coerce')
                except Exception as e:
                    self.logger.warning(f"Failed to convert column {col} to {expected_type}: {e}")

        return transformed_data

    def _get_record_count(self, data: pd.DataFrame) -> int:
        """Get number of records in DataFrame."""
        return len(data)

    def set_required_columns(self, columns: list[str]) -> None:
        """Set list of required columns."""
        self.required_columns = columns

    def set_column_types(self, types: dict[str, type]) -> None:
        """Set expected column types."""
        self.column_types = types

    def set_value_ranges(self, ranges: dict[str, tuple]) -> None:
        """Set valid value ranges for numeric columns."""
        self.value_ranges = ranges

    def export_data(
        self,
        data: pd.DataFrame,
        destination: str | Path,
        format: str = "csv",
        **kwargs
    ) -> bool:
        """Export DataFrame to file."""
        try:
            destination_path = Path(destination)
            destination_path.parent.mkdir(parents=True, exist_ok=True)

            if format.lower() == 'csv':
                data.to_csv(destination_path, index=False, encoding=self.encoding, **kwargs)
            elif format.lower() in ['xlsx', 'excel']:
                data.to_excel(destination_path, index=False, **kwargs)
            elif format.lower() == 'json':
                data.to_json(destination_path, orient='records', **kwargs)
            elif format.lower() == 'parquet':
                data.to_parquet(destination_path, **kwargs)
            else:
                raise ValueError(f"Unsupported export format: {format}")

            self.logger.info(f"Data exported to {destination} in {format} format")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export data to {destination}: {e}")
            raise DataLoadingError(
                f"Failed to export data to {destination}",
                file_path=str(destination),
                data_source="export",
                cause=e
            ) from e


class DataProcessorFactory:
    """Factory for creating data processors based on data type and source."""

    _processors: dict[str, type] = {}

    @classmethod
    def register_processor(cls, data_type: str, processor_class: type) -> None:
        """Register a data processor class."""
        cls._processors[data_type] = processor_class

    @classmethod
    def create_processor(cls, data_type: str, **kwargs) -> BaseDataProcessor:
        """Create a data processor instance."""
        if data_type not in cls._processors:
            raise ValueError(f"Unknown data type: {data_type}")

        processor_class = cls._processors[data_type]
        return processor_class(**kwargs)

    @classmethod
    def get_supported_types(cls) -> list[str]:
        """Get list of supported data types."""
        return list(cls._processors.keys())


# Register default processors
DataProcessorFactory.register_processor("pandas", PandasDataProcessor)
DataProcessorFactory.register_processor("csv", PandasDataProcessor)
DataProcessorFactory.register_processor("excel", PandasDataProcessor)
