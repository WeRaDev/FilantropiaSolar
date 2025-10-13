"""
Comprehensive input validation utilities for FilantropiaSolar.

This module provides robust input validation, sanitization, and type checking
with detailed error reporting and security considerations.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import InvalidOperation
from enum import Enum
import math
from pathlib import Path
import re
from typing import (
    Any,
    TypeVar,
)

import pandas as pd

from ..core import (
    ValidationError,
    get_logger,
)

T = TypeVar("T")
logger = get_logger("validation")


class ValidationType(str, Enum):
    """Types of validation rules."""

    TYPE_CHECK = "type_check"
    RANGE_CHECK = "range_check"
    FORMAT_CHECK = "format_check"
    LENGTH_CHECK = "length_check"
    PATTERN_CHECK = "pattern_check"
    CUSTOM_CHECK = "custom_check"
    REQUIRED_CHECK = "required_check"
    ENUM_CHECK = "enum_check"


@dataclass
class ValidationRule:
    """Single validation rule definition."""

    rule_type: ValidationType
    parameters: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    required: bool = True

    def __post_init__(self):
        """Generate default error message if not provided."""
        if self.error_message is None:
            self.error_message = self._generate_default_message()

    def _generate_default_message(self) -> str:
        """Generate default error message based on rule type."""
        messages = {
            ValidationType.TYPE_CHECK: f"Expected type {self.parameters.get('expected_type', 'unknown')}",
            ValidationType.RANGE_CHECK: f"Value must be between {self.parameters.get('min_value', 'N/A')} and {self.parameters.get('max_value', 'N/A')}",
            ValidationType.FORMAT_CHECK: f"Invalid format, expected {self.parameters.get('format_name', 'specific format')}",
            ValidationType.LENGTH_CHECK: f"Length must be between {self.parameters.get('min_length', 0)} and {self.parameters.get('max_length', 'unlimited')}",
            ValidationType.PATTERN_CHECK: f"Must match pattern: {self.parameters.get('pattern', 'N/A')}",
            ValidationType.REQUIRED_CHECK: "This field is required",
            ValidationType.ENUM_CHECK: f"Must be one of: {self.parameters.get('allowed_values', [])}",
            ValidationType.CUSTOM_CHECK: "Custom validation failed",
        }
        return messages.get(self.rule_type, "Validation failed")


@dataclass
class ValidationResult:
    """Result of validation operation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_value: Any = None

    def add_error(self, message: str) -> None:
        """Add validation error."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add validation warning."""
        self.warnings.append(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "sanitized_value": self.sanitized_value,
        }


class ValidationSchema:
    """Schema-based validation for complex data structures."""

    def __init__(self, name: str):
        """
        Initialize validation schema.

        Args:
            name: Schema identifier name
        """
        self.name = name
        self.fields: dict[str, list[ValidationRule]] = {}
        self.global_rules: list[ValidationRule] = []

    def add_field(self, field_name: str, *rules: ValidationRule) -> "ValidationSchema":
        """
        Add validation rules for a field.

        Args:
            field_name: Name of the field
            *rules: Validation rules to apply

        Returns:
            Self for method chaining
        """
        if field_name not in self.fields:
            self.fields[field_name] = []
        self.fields[field_name].extend(rules)
        return self

    def add_global_rule(self, rule: ValidationRule) -> "ValidationSchema":
        """Add global validation rule."""
        self.global_rules.append(rule)
        return self

    def validate(self, data: dict[str, Any]) -> dict[str, ValidationResult]:
        """
        Validate data against schema.

        Args:
            data: Data dictionary to validate

        Returns:
            Dictionary of field names to validation results
        """
        results = {}

        # Validate individual fields
        for field_name, rules in self.fields.items():
            value = data.get(field_name)
            result = ValidationResult(is_valid=True, sanitized_value=value)

            for rule in rules:
                field_result = self._apply_rule(value, rule, field_name)
                if not field_result.is_valid:
                    result.errors.extend(field_result.errors)
                    result.is_valid = False
                result.warnings.extend(field_result.warnings)
                if field_result.sanitized_value is not None:
                    result.sanitized_value = field_result.sanitized_value

            results[field_name] = result

        # Apply global rules
        for rule in self.global_rules:
            # Global rules apply to entire data dictionary
            global_result = self._apply_rule(data, rule, "_global_")
            if not global_result.is_valid:
                if "_global_" not in results:
                    results["_global_"] = ValidationResult(is_valid=True)
                results["_global_"].errors.extend(global_result.errors)
                results["_global_"].is_valid = False

        return results

    def _apply_rule(
        self, value: Any, rule: ValidationRule, field_name: str
    ) -> ValidationResult:
        """Apply single validation rule."""
        result = ValidationResult(is_valid=True, sanitized_value=value)

        # Check if field is required
        if rule.required and (value is None or value == ""):
            if rule.rule_type == ValidationType.REQUIRED_CHECK:
                result.add_error(rule.error_message)
            return result

        # Skip validation for optional empty values
        if not rule.required and (value is None or value == ""):
            return result

        try:
            if rule.rule_type == ValidationType.TYPE_CHECK:
                result = self._validate_type(value, rule, field_name)
            elif rule.rule_type == ValidationType.RANGE_CHECK:
                result = self._validate_range(value, rule, field_name)
            elif rule.rule_type == ValidationType.FORMAT_CHECK:
                result = self._validate_format(value, rule, field_name)
            elif rule.rule_type == ValidationType.LENGTH_CHECK:
                result = self._validate_length(value, rule, field_name)
            elif rule.rule_type == ValidationType.PATTERN_CHECK:
                result = self._validate_pattern(value, rule, field_name)
            elif rule.rule_type == ValidationType.ENUM_CHECK:
                result = self._validate_enum(value, rule, field_name)
            elif rule.rule_type == ValidationType.CUSTOM_CHECK:
                result = self._validate_custom(value, rule, field_name)

        except Exception as e:
            result.add_error(f"Validation error in {field_name}: {e!s}")
            logger.warning(f"Validation exception in {field_name}: {e}")

        return result

    def _validate_type(
        self, value: Any, rule: ValidationRule, field_name: str
    ) -> ValidationResult:
        """Validate value type."""
        result = ValidationResult(is_valid=True, sanitized_value=value)
        expected_type = rule.parameters.get("expected_type")

        if expected_type is None:
            result.add_error("No expected type specified")
            return result

        # Handle special type conversions
        if expected_type == float and isinstance(value, (int, str)):
            try:
                result.sanitized_value = float(value)
                return result
            except (ValueError, TypeError):
                pass

        if expected_type == int and isinstance(value, (float, str)):
            try:
                result.sanitized_value = int(value)
                return result
            except (ValueError, TypeError):
                pass

        if not isinstance(value, expected_type):
            result.add_error(rule.error_message)

        return result

    def _validate_range(
        self, value: Any, rule: ValidationRule, field_name: str
    ) -> ValidationResult:
        """Validate numeric range."""
        result = ValidationResult(is_valid=True, sanitized_value=value)

        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            result.add_error(
                f"Cannot validate range for non-numeric value in {field_name}"
            )
            return result

        min_value = rule.parameters.get("min_value")
        max_value = rule.parameters.get("max_value")

        if min_value is not None and numeric_value < min_value:
            result.add_error(rule.error_message)

        if max_value is not None and numeric_value > max_value:
            result.add_error(rule.error_message)

        return result

    def _validate_format(
        self, value: Any, rule: ValidationRule, field_name: str
    ) -> ValidationResult:
        """Validate specific formats."""
        result = ValidationResult(is_valid=True, sanitized_value=value)
        format_type = rule.parameters.get("format_type")

        str_value = str(value).strip()

        if format_type == "email":
            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_pattern, str_value):
                result.add_error(rule.error_message)

        elif format_type == "date":
            try:
                datetime.strptime(
                    str_value, rule.parameters.get("date_format", "%Y-%m-%d")
                )
            except ValueError:
                result.add_error(rule.error_message)

        elif format_type == "phone":
            # Simple phone number validation
            phone_pattern = r"^\+?[\d\s\-\(\)]{10,}$"
            if not re.match(phone_pattern, str_value):
                result.add_error(rule.error_message)

        elif format_type == "url":
            url_pattern = r"^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?$"
            if not re.match(url_pattern, str_value):
                result.add_error(rule.error_message)

        return result

    def _validate_length(
        self, value: Any, rule: ValidationRule, field_name: str
    ) -> ValidationResult:
        """Validate length constraints."""
        result = ValidationResult(is_valid=True, sanitized_value=value)

        try:
            length = len(value)
        except TypeError:
            result.add_error(f"Cannot validate length for value in {field_name}")
            return result

        min_length = rule.parameters.get("min_length", 0)
        max_length = rule.parameters.get("max_length")

        if length < min_length:
            result.add_error(rule.error_message)

        if max_length is not None and length > max_length:
            result.add_error(rule.error_message)

        return result

    def _validate_pattern(
        self, value: Any, rule: ValidationRule, field_name: str
    ) -> ValidationResult:
        """Validate against regex pattern."""
        result = ValidationResult(is_valid=True, sanitized_value=value)
        pattern = rule.parameters.get("pattern")

        if pattern is None:
            result.add_error("No pattern specified")
            return result

        str_value = str(value)
        if not re.match(pattern, str_value):
            result.add_error(rule.error_message)

        return result

    def _validate_enum(
        self, value: Any, rule: ValidationRule, field_name: str
    ) -> ValidationResult:
        """Validate against enumerated values."""
        result = ValidationResult(is_valid=True, sanitized_value=value)
        allowed_values = rule.parameters.get("allowed_values", [])

        if value not in allowed_values:
            result.add_error(rule.error_message)

        return result

    def _validate_custom(
        self, value: Any, rule: ValidationRule, field_name: str
    ) -> ValidationResult:
        """Apply custom validation function."""
        result = ValidationResult(is_valid=True, sanitized_value=value)
        custom_function = rule.parameters.get("function")

        if custom_function is None:
            result.add_error("No custom validation function specified")
            return result

        try:
            is_valid = custom_function(value)
            if not is_valid:
                result.add_error(rule.error_message)
        except Exception as e:
            result.add_error(f"Custom validation error: {e!s}")

        return result


class InputValidator:
    """High-level input validation and sanitization utilities."""

    @staticmethod
    def validate_and_sanitize_string(
        value: Any,
        min_length: int = 0,
        max_length: int | None = None,
        strip_whitespace: bool = True,
        allow_empty: bool = False,
        pattern: str | None = None,
        field_name: str = "input",
    ) -> str:
        """
        Validate and sanitize string input.

        Args:
            value: Input value to validate
            min_length: Minimum string length
            max_length: Maximum string length
            strip_whitespace: Whether to strip leading/trailing whitespace
            allow_empty: Whether to allow empty strings
            pattern: Optional regex pattern to match
            field_name: Field name for error reporting

        Returns:
            Sanitized string value

        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if not allow_empty:
                raise ValidationError(
                    f"{field_name} cannot be None", field=field_name, value=value
                )
            return ""

        # Convert to string and sanitize
        str_value = str(value)
        if strip_whitespace:
            str_value = str_value.strip()

        # Check empty constraint
        if not allow_empty and not str_value:
            raise ValidationError(
                f"{field_name} cannot be empty", field=field_name, value=str_value
            )

        # Check length constraints
        if len(str_value) < min_length:
            raise ValidationError(
                f"{field_name} must be at least {min_length} characters long",
                field=field_name,
                value=str_value,
            )

        if max_length is not None and len(str_value) > max_length:
            raise ValidationError(
                f"{field_name} must be at most {max_length} characters long",
                field=field_name,
                value=str_value,
            )

        # Check pattern constraint
        if pattern is not None and not re.match(pattern, str_value):
            raise ValidationError(
                f"{field_name} does not match required pattern",
                field=field_name,
                value=str_value,
            )

        return str_value

    @staticmethod
    def validate_numeric(
        value: Any,
        min_value: int | float | None = None,
        max_value: int | float | None = None,
        allow_none: bool = False,
        convert_to_type: type | None = None,
        field_name: str = "input",
    ) -> int | float | None:
        """
        Validate numeric input.

        Args:
            value: Input value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            allow_none: Whether to allow None values
            convert_to_type: Type to convert to (int or float)
            field_name: Field name for error reporting

        Returns:
            Validated numeric value

        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if allow_none:
                return None
            raise ValidationError(
                f"{field_name} cannot be None", field=field_name, value=value
            )

        # Try to convert to numeric
        try:
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    if allow_none:
                        return None
                    raise ValidationError(
                        f"{field_name} cannot be empty", field=field_name, value=value
                    )

                # Try to detect if it should be int or float
                if "." in value or "e" in value.lower():
                    numeric_value = float(value)
                else:
                    numeric_value = int(value)
            else:
                numeric_value = (
                    float(value) if not isinstance(value, (int, float)) else value
                )

        except (ValueError, TypeError, InvalidOperation) as e:
            raise ValidationError(
                f"{field_name} must be a valid number",
                field=field_name,
                value=value,
                expected_type=float,
            ) from e

        # Check for special float values
        if isinstance(numeric_value, float) and not math.isfinite(numeric_value):
            raise ValidationError(
                f"{field_name} must be a finite number",
                field=field_name,
                value=numeric_value,
            )

        # Check range constraints
        if min_value is not None and numeric_value < min_value:
            raise ValidationError(
                f"{field_name} must be at least {min_value}",
                field=field_name,
                value=numeric_value,
            )

        if max_value is not None and numeric_value > max_value:
            raise ValidationError(
                f"{field_name} must be at most {max_value}",
                field=field_name,
                value=numeric_value,
            )

        # Convert to requested type
        if convert_to_type is not None:
            try:
                numeric_value = convert_to_type(numeric_value)
            except (ValueError, OverflowError) as e:
                raise ValidationError(
                    f"{field_name} cannot be converted to {convert_to_type.__name__}",
                    field=field_name,
                    value=numeric_value,
                    expected_type=convert_to_type,
                ) from e

        return numeric_value

    @staticmethod
    def validate_date(
        value: Any,
        date_format: str = "%Y-%m-%d",
        min_date: date | None = None,
        max_date: date | None = None,
        allow_none: bool = False,
        field_name: str = "date",
    ) -> date | None:
        """
        Validate date input.

        Args:
            value: Input value to validate
            date_format: Expected date format
            min_date: Minimum allowed date
            max_date: Maximum allowed date
            allow_none: Whether to allow None values
            field_name: Field name for error reporting

        Returns:
            Validated date object

        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if allow_none:
                return None
            raise ValidationError(
                f"{field_name} cannot be None", field=field_name, value=value
            )

        # Handle different input types
        if isinstance(value, date):
            date_value = value
        elif isinstance(value, datetime):
            date_value = value.date()
        elif isinstance(value, str):
            try:
                date_value = datetime.strptime(value.strip(), date_format).date()
            except ValueError as e:
                raise ValidationError(
                    f"{field_name} must be in format {date_format}",
                    field=field_name,
                    value=value,
                ) from e
        else:
            raise ValidationError(
                f"{field_name} must be a date string, date, or datetime object",
                field=field_name,
                value=value,
                expected_type=date,
            )

        # Check range constraints
        if min_date is not None and date_value < min_date:
            raise ValidationError(
                f"{field_name} must be on or after {min_date}",
                field=field_name,
                value=date_value,
            )

        if max_date is not None and date_value > max_date:
            raise ValidationError(
                f"{field_name} must be on or before {max_date}",
                field=field_name,
                value=date_value,
            )

        return date_value

    @staticmethod
    def validate_file_path(
        value: Any,
        must_exist: bool = False,
        allowed_extensions: list[str] | None = None,
        max_size_mb: float | None = None,
        field_name: str = "file_path",
    ) -> Path:
        """
        Validate file path input.

        Args:
            value: Input value to validate
            must_exist: Whether file must exist
            allowed_extensions: List of allowed file extensions
            max_size_mb: Maximum file size in MB
            field_name: Field name for error reporting

        Returns:
            Validated Path object

        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            raise ValidationError(
                f"{field_name} cannot be None", field=field_name, value=value
            )

        # Convert to Path object
        try:
            path_value = Path(value)
        except Exception as e:
            raise ValidationError(
                f"{field_name} must be a valid file path", field=field_name, value=value
            ) from e

        # Check if file exists
        if must_exist and not path_value.exists():
            raise ValidationError(
                f"{field_name} file does not exist: {path_value}",
                field=field_name,
                value=str(path_value),
            )

        # Check file extension
        if allowed_extensions and path_value.suffix.lower() not in [
            ext.lower() for ext in allowed_extensions
        ]:
            raise ValidationError(
                f"{field_name} must have one of these extensions: {allowed_extensions}",
                field=field_name,
                value=str(path_value),
            )

        # Check file size
        if max_size_mb is not None and path_value.exists():
            file_size_mb = path_value.stat().st_size / (1024 * 1024)
            if file_size_mb > max_size_mb:
                raise ValidationError(
                    f"{field_name} file size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({max_size_mb} MB)",
                    field=field_name,
                    value=str(path_value),
                )

        return path_value

    @staticmethod
    def validate_dataframe(
        df: Any,
        required_columns: list[str] | None = None,
        min_rows: int = 1,
        max_rows: int | None = None,
        field_name: str = "dataframe",
    ) -> pd.DataFrame:
        """
        Validate pandas DataFrame input.

        Args:
            df: DataFrame to validate
            required_columns: List of required column names
            min_rows: Minimum number of rows
            max_rows: Maximum number of rows
            field_name: Field name for error reporting

        Returns:
            Validated DataFrame

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(df, pd.DataFrame):
            raise ValidationError(
                f"{field_name} must be a pandas DataFrame",
                field=field_name,
                value=type(df).__name__,
                expected_type=pd.DataFrame,
            )

        # Check for empty DataFrame
        if df.empty and min_rows > 0:
            raise ValidationError(
                f"{field_name} cannot be empty",
                field=field_name,
                value="empty DataFrame",
            )

        # Check row count
        row_count = len(df)
        if row_count < min_rows:
            raise ValidationError(
                f"{field_name} must have at least {min_rows} rows, got {row_count}",
                field=field_name,
                value=row_count,
            )

        if max_rows is not None and row_count > max_rows:
            raise ValidationError(
                f"{field_name} must have at most {max_rows} rows, got {row_count}",
                field=field_name,
                value=row_count,
            )

        # Check required columns
        if required_columns:
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValidationError(
                    f"{field_name} missing required columns: {missing_columns}",
                    field=field_name,
                    value=list(df.columns),
                )

        return df


# Decorator for automatic input validation
def validate_input(**validation_rules) -> Callable:
    """
    Decorator to automatically validate function inputs.

    Args:
        **validation_rules: Validation rules for each parameter

    Example:
        @validate_input(
            value=ValidationRule(ValidationType.RANGE_CHECK, {'min_value': 0, 'max_value': 100}),
            name=ValidationRule(ValidationType.LENGTH_CHECK, {'min_length': 1, 'max_length': 50})
        )
        def my_function(value: float, name: str):
            pass
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Get function signature
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Validate each parameter
            for param_name, validation_rule in validation_rules.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]

                    # Create temporary schema for validation
                    schema = ValidationSchema(f"{func.__name__}_validation")
                    schema.add_field(param_name, validation_rule)

                    results = schema.validate({param_name: value})
                    result = results.get(param_name)

                    if result and not result.is_valid:
                        raise ValidationError(
                            f"Validation failed for parameter '{param_name}': {'; '.join(result.errors)}",
                            field=param_name,
                            value=value,
                        )

                    # Update with sanitized value if available
                    if result and result.sanitized_value is not None:
                        bound_args.arguments[param_name] = result.sanitized_value

            return func(*bound_args.args, **bound_args.kwargs)

        return wrapper

    return decorator
