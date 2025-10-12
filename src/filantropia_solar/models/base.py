"""
Base classes and interfaces for machine learning models in FilantropiaSolar.

This module defines abstract base classes and protocols for ML model operations,
following SOLID principles and providing comprehensive type safety.
"""

import abc
import joblib
from typing import (
    Any, Dict, List, Optional, Protocol, Tuple, Union, TypeVar, Generic,
    runtime_checkable, Callable
)
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_val_score, GridSearchCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ..core import (
    get_logger,
    log_performance,
    log_exceptions,
    log_model_operation,
    ModelError,
    ModelTrainingError,
    ModelPredictionError,
    ValidationError,
    get_models_dir,
)

# Type variables
ModelType = TypeVar('ModelType', bound=BaseEstimator)
PredictionType = TypeVar('PredictionType')
FeatureType = TypeVar('FeatureType')


class ModelStatus(str, Enum):
    """Model status enumeration."""
    
    UNTRAINED = "untrained"
    TRAINING = "training"
    TRAINED = "trained"
    EVALUATING = "evaluating"
    READY = "ready"
    ERROR = "error"
    DEPRECATED = "deprecated"


@dataclass
class ModelMetrics:
    """Model performance metrics container."""
    
    mae: float  # Mean Absolute Error
    mse: float  # Mean Squared Error
    rmse: float  # Root Mean Squared Error
    r2: float   # R-squared
    mape: Optional[float] = None  # Mean Absolute Percentage Error
    cross_val_scores: Optional[List[float]] = None
    feature_importance: Optional[Dict[str, float]] = None
    validation_date: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_acceptable(self) -> bool:
        """Check if model performance meets acceptance criteria."""
        return self.r2 >= 0.7 and self.mae <= 1.0  # Configurable thresholds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'mae': self.mae,
            'mse': self.mse,
            'rmse': self.rmse,
            'r2': self.r2,
            'mape': self.mape,
            'cross_val_scores': self.cross_val_scores,
            'feature_importance': self.feature_importance,
            'is_acceptable': self.is_acceptable,
            'validation_date': self.validation_date.isoformat(),
        }


@dataclass
class PredictionResult:
    """Container for model predictions with metadata."""
    
    predictions: np.ndarray
    confidence_intervals: Optional[np.ndarray] = None
    feature_importance: Optional[Dict[str, float]] = None
    model_version: Optional[str] = None
    prediction_timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert prediction result to dictionary."""
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'confidence_intervals': self.confidence_intervals.tolist() if isinstance(self.confidence_intervals, np.ndarray) else self.confidence_intervals,
            'feature_importance': self.feature_importance,
            'model_version': self.model_version,
            'prediction_timestamp': self.prediction_timestamp.isoformat(),
            'metadata': self.metadata,
        }


@runtime_checkable
class ModelPredictor(Protocol[FeatureType, PredictionType]):
    """Protocol for model prediction operations."""
    
    def predict(self, features: FeatureType) -> PredictionType:
        """Make predictions on features."""
        ...
    
    def predict_proba(self, features: FeatureType) -> np.ndarray:
        """Get prediction probabilities (for classification models)."""
        ...
    
    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """Get feature importance scores."""
        ...


@runtime_checkable
class ModelTrainer(Protocol[ModelType, FeatureType]):
    """Protocol for model training operations."""
    
    def fit(self, X: FeatureType, y: np.ndarray, **kwargs) -> ModelType:
        """Train the model on features and targets."""
        ...
    
    def partial_fit(self, X: FeatureType, y: np.ndarray, **kwargs) -> ModelType:
        """Incrementally train the model."""
        ...
    
    def get_params(self) -> Dict[str, Any]:
        """Get model parameters."""
        ...
    
    def set_params(self, **params) -> ModelType:
        """Set model parameters."""
        ...


@runtime_checkable
class ModelEvaluator(Protocol[ModelType, FeatureType]):
    """Protocol for model evaluation operations."""
    
    def evaluate(self, model: ModelType, X_test: FeatureType, y_test: np.ndarray) -> ModelMetrics:
        """Evaluate model performance."""
        ...
    
    def cross_validate(self, model: ModelType, X: FeatureType, y: np.ndarray, cv: int = 5) -> List[float]:
        """Perform cross-validation."""
        ...


class BaseMLModel(abc.ABC, Generic[ModelType, FeatureType, PredictionType]):
    """
    Abstract base class for machine learning models.
    
    Provides common functionality and defines interfaces for model operations
    following SOLID principles and clean architecture patterns.
    """
    
    def __init__(
        self,
        name: str,
        model_type: str = "regression",
        version: str = "1.0.0",
        hyperparameters: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ML model.
        
        Args:
            name: Model identifier name
            model_type: Type of model (regression, classification)
            version: Model version
            hyperparameters: Model hyperparameters
        """
        self.name = name
        self.model_type = model_type
        self.version = version
        self.hyperparameters = hyperparameters or {}
        self.logger = get_logger(f"models.{name}")
        
        self._model: Optional[ModelType] = None
        self._feature_names: List[str] = []
        self._status = ModelStatus.UNTRAINED
        self._metrics: Optional[ModelMetrics] = None
        self._training_history: List[Dict[str, Any]] = []
        self._created_at = datetime.utcnow()
        self._last_trained: Optional[datetime] = None
    
    @property
    def status(self) -> ModelStatus:
        """Get current model status."""
        return self._status
    
    @property
    def is_trained(self) -> bool:
        """Check if model is trained and ready."""
        return self._status in [ModelStatus.TRAINED, ModelStatus.READY]
    
    @property
    def metrics(self) -> Optional[ModelMetrics]:
        """Get latest model metrics."""
        return self._metrics
    
    @property
    def feature_names(self) -> List[str]:
        """Get list of feature names."""
        return self._feature_names.copy()
    
    @abc.abstractmethod
    def _create_model(self) -> ModelType:
        """Create the underlying model instance."""
        pass
    
    @abc.abstractmethod
    def _prepare_features(self, X: FeatureType) -> np.ndarray:
        """Prepare features for model input."""
        pass
    
    @abc.abstractmethod
    def _prepare_targets(self, y: Union[np.ndarray, pd.Series]) -> np.ndarray:
        """Prepare target values for model training."""
        pass
    
    @abc.abstractmethod
    def _validate_features(self, X: FeatureType) -> None:
        """Validate feature data."""
        pass
    
    def _set_status(self, status: ModelStatus) -> None:
        """Set model status with logging."""
        old_status = self._status
        self._status = status
        self.logger.info(f"Model status changed: {old_status} -> {status}")
    
    @log_performance("model_training")
    @log_exceptions()
    def train(
        self,
        X: FeatureType,
        y: Union[np.ndarray, pd.Series],
        validation_split: float = 0.2,
        hyperparameter_tuning: bool = False,
        **kwargs
    ) -> ModelMetrics:
        """
        Train the model with given features and targets.
        
        Args:
            X: Training features
            y: Training targets
            validation_split: Fraction of data for validation
            hyperparameter_tuning: Whether to perform hyperparameter optimization
            **kwargs: Additional training parameters
            
        Returns:
            Model performance metrics
            
        Raises:
            ModelTrainingError: If training fails
        """
        self.logger.info(f"Starting model training for {self.name}")
        self._set_status(ModelStatus.TRAINING)
        
        try:
            # Validate input data
            self._validate_features(X)
            
            # Prepare data
            X_prepared = self._prepare_features(X)
            y_prepared = self._prepare_targets(y)
            
            if hasattr(X, 'columns'):
                self._feature_names = list(X.columns)
            else:
                self._feature_names = [f"feature_{i}" for i in range(X_prepared.shape[1])]
            
            # Split data for validation
            from sklearn.model_selection import train_test_split
            X_train, X_val, y_train, y_val = train_test_split(
                X_prepared, y_prepared, test_size=validation_split, random_state=42
            )
            
            # Create model if not exists
            if self._model is None:
                self._model = self._create_model()
            
            # Hyperparameter tuning if requested
            if hyperparameter_tuning:
                self.logger.info("Performing hyperparameter tuning")
                self._model = self._tune_hyperparameters(X_train, y_train, **kwargs)
            
            # Train model
            self.logger.debug(f"Training with {len(X_train)} samples")
            self._model.fit(X_train, y_train)
            
            # Evaluate on validation set
            self._set_status(ModelStatus.EVALUATING)
            metrics = self._evaluate_model(X_val, y_val)
            self._metrics = metrics
            
            # Update training history
            training_record = {
                'timestamp': datetime.utcnow().isoformat(),
                'samples': len(X_train),
                'validation_samples': len(X_val),
                'hyperparameters': self.hyperparameters.copy(),
                'metrics': metrics.to_dict(),
            }
            self._training_history.append(training_record)
            
            # Set final status
            if metrics.is_acceptable:
                self._set_status(ModelStatus.READY)
                self._last_trained = datetime.utcnow()
            else:
                self._set_status(ModelStatus.TRAINED)
                self.logger.warning(f"Model performance below acceptance criteria: R² = {metrics.r2:.3f}")
            
            # Log training completion
            log_model_operation(
                operation="training",
                model_name=self.name,
                performance=metrics.to_dict()
            )
            
            self.logger.info(
                f"Model training completed - R²: {metrics.r2:.3f}, MAE: {metrics.mae:.3f}"
            )
            
            return metrics
            
        except Exception as e:
            self._set_status(ModelStatus.ERROR)
            error_msg = f"Model training failed: {str(e)}"
            self.logger.error(error_msg)
            
            if isinstance(e, ModelError):
                raise
            else:
                raise ModelTrainingError(
                    error_msg,
                    model_type=self.model_type,
                    training_samples=len(X) if hasattr(X, '__len__') else None,
                    cause=e
                ) from e
    
    @log_performance("model_prediction")
    @log_exceptions()
    def predict(
        self,
        X: FeatureType,
        return_confidence: bool = False,
        **kwargs
    ) -> PredictionResult:
        """
        Make predictions on input features.
        
        Args:
            X: Input features
            return_confidence: Whether to return confidence intervals
            **kwargs: Additional prediction parameters
            
        Returns:
            Prediction results with metadata
            
        Raises:
            ModelPredictionError: If prediction fails
        """
        if not self.is_trained:
            raise ModelPredictionError(
                f"Model {self.name} is not trained. Current status: {self._status}",
                model_name=self.name
            )
        
        try:
            # Validate and prepare features
            self._validate_features(X)
            X_prepared = self._prepare_features(X)
            
            # Make predictions
            predictions = self._model.predict(X_prepared)
            
            # Calculate confidence intervals if requested
            confidence_intervals = None
            if return_confidence:
                confidence_intervals = self._calculate_confidence_intervals(X_prepared, **kwargs)
            
            # Get feature importance
            feature_importance = self._get_feature_importance()
            
            result = PredictionResult(
                predictions=predictions,
                confidence_intervals=confidence_intervals,
                feature_importance=feature_importance,
                model_version=self.version,
                metadata={
                    'model_name': self.name,
                    'model_type': self.model_type,
                    'feature_count': X_prepared.shape[1],
                    'sample_count': X_prepared.shape[0],
                }
            )
            
            self.logger.debug(f"Generated {len(predictions)} predictions")
            return result
            
        except Exception as e:
            error_msg = f"Prediction failed: {str(e)}"
            self.logger.error(error_msg)
            
            if isinstance(e, ModelError):
                raise
            else:
                raise ModelPredictionError(
                    error_msg,
                    model_name=self.name,
                    input_features=X_prepared.shape[1] if 'X_prepared' in locals() else None,
                    cause=e
                ) from e
    
    def _tune_hyperparameters(
        self,
        X: np.ndarray,
        y: np.ndarray,
        param_grid: Optional[Dict[str, List[Any]]] = None,
        cv: int = 5,
        **kwargs
    ) -> ModelType:
        """Perform hyperparameter tuning using grid search."""
        if param_grid is None:
            param_grid = self._get_default_param_grid()
        
        if not param_grid:
            self.logger.warning("No parameter grid provided for hyperparameter tuning")
            return self._model
        
        grid_search = GridSearchCV(
            self._model,
            param_grid,
            cv=cv,
            scoring='r2' if self.model_type == 'regression' else 'accuracy',
            n_jobs=-1,
            **kwargs
        )
        
        grid_search.fit(X, y)
        
        # Update hyperparameters with best found parameters
        self.hyperparameters.update(grid_search.best_params_)
        self.logger.info(f"Best parameters found: {grid_search.best_params_}")
        
        return grid_search.best_estimator_
    
    def _get_default_param_grid(self) -> Dict[str, List[Any]]:
        """Get default parameter grid for hyperparameter tuning."""
        return {}  # Override in subclasses
    
    def _evaluate_model(self, X_val: np.ndarray, y_val: np.ndarray) -> ModelMetrics:
        """Evaluate model performance on validation data."""
        predictions = self._model.predict(X_val)
        
        mae = mean_absolute_error(y_val, predictions)
        mse = mean_squared_error(y_val, predictions)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_val, predictions)
        
        # Calculate MAPE if no zero values in actual
        mape = None
        if not np.any(y_val == 0):
            mape = np.mean(np.abs((y_val - predictions) / y_val)) * 100
        
        # Perform cross-validation
        cv_scores = cross_val_score(
            self._model,
            np.vstack([X_val]),  # Ensure proper shape
            y_val,
            cv=min(5, len(y_val) // 2),
            scoring='r2' if self.model_type == 'regression' else 'accuracy'
        )
        
        feature_importance = self._get_feature_importance()
        
        return ModelMetrics(
            mae=mae,
            mse=mse,
            rmse=rmse,
            r2=r2,
            mape=mape,
            cross_val_scores=cv_scores.tolist(),
            feature_importance=feature_importance,
        )
    
    def _get_feature_importance(self) -> Optional[Dict[str, float]]:
        """Get feature importance scores."""
        if not hasattr(self._model, 'feature_importances_'):
            return None
        
        importances = self._model.feature_importances_
        if len(importances) != len(self._feature_names):
            return None
        
        return {
            name: float(importance)
            for name, importance in zip(self._feature_names, importances)
        }
    
    def _calculate_confidence_intervals(
        self,
        X: np.ndarray,
        confidence_level: float = 0.95,
        **kwargs
    ) -> Optional[np.ndarray]:
        """Calculate prediction confidence intervals."""
        # Default implementation - override in subclasses for more sophisticated methods
        if hasattr(self._model, 'predict_std'):
            std = self._model.predict_std(X)
            from scipy.stats import norm
            z_score = norm.ppf((1 + confidence_level) / 2)
            return np.column_stack([-z_score * std, z_score * std])
        
        return None
    
    def save_model(self, file_path: Optional[Union[str, Path]] = None) -> Path:
        """
        Save trained model to file.
        
        Args:
            file_path: Path to save model. If None, uses default path.
            
        Returns:
            Path where model was saved
            
        Raises:
            ModelError: If saving fails
        """
        if not self.is_trained:
            raise ModelError(
                f"Cannot save untrained model {self.name}",
                error_code="FS3003"  # MODEL_SAVING_ERROR
            )
        
        if file_path is None:
            models_dir = get_models_dir()
            file_path = models_dir / f"{self.name}_v{self.version}.pkl"
        else:
            file_path = Path(file_path)
        
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            model_data = {
                'model': self._model,
                'metadata': {
                    'name': self.name,
                    'type': self.model_type,
                    'version': self.version,
                    'feature_names': self._feature_names,
                    'hyperparameters': self.hyperparameters,
                    'metrics': self._metrics.to_dict() if self._metrics else None,
                    'training_history': self._training_history,
                    'created_at': self._created_at.isoformat(),
                    'last_trained': self._last_trained.isoformat() if self._last_trained else None,
                }
            }
            
            joblib.dump(model_data, file_path)
            self.logger.info(f"Model saved to {file_path}")
            
            return file_path
            
        except Exception as e:
            raise ModelError(
                f"Failed to save model to {file_path}: {str(e)}",
                error_code="FS3003",  # MODEL_SAVING_ERROR
                cause=e
            ) from e
    
    @classmethod
    def load_model(cls, file_path: Union[str, Path]) -> "BaseMLModel":
        """
        Load trained model from file.
        
        Args:
            file_path: Path to saved model file
            
        Returns:
            Loaded model instance
            
        Raises:
            ModelError: If loading fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise ModelError(
                f"Model file not found: {file_path}",
                error_code="FS3002"  # MODEL_LOADING_ERROR
            )
        
        try:
            model_data = joblib.load(file_path)
            metadata = model_data['metadata']
            
            # Create instance
            instance = cls(
                name=metadata['name'],
                model_type=metadata['type'],
                version=metadata['version'],
                hyperparameters=metadata['hyperparameters']
            )
            
            # Restore state
            instance._model = model_data['model']
            instance._feature_names = metadata['feature_names']
            instance._training_history = metadata['training_history']
            instance._created_at = datetime.fromisoformat(metadata['created_at'])
            
            if metadata['last_trained']:
                instance._last_trained = datetime.fromisoformat(metadata['last_trained'])
            
            if metadata['metrics']:
                # Reconstruct metrics object
                metrics_data = metadata['metrics']
                instance._metrics = ModelMetrics(
                    mae=metrics_data['mae'],
                    mse=metrics_data['mse'],
                    rmse=metrics_data['rmse'],
                    r2=metrics_data['r2'],
                    mape=metrics_data.get('mape'),
                    cross_val_scores=metrics_data.get('cross_val_scores'),
                    feature_importance=metrics_data.get('feature_importance'),
                )
            
            instance._set_status(ModelStatus.READY)
            instance.logger.info(f"Model loaded from {file_path}")
            
            return instance
            
        except Exception as e:
            raise ModelError(
                f"Failed to load model from {file_path}: {str(e)}",
                error_code="FS3002",  # MODEL_LOADING_ERROR
                cause=e
            ) from e
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get comprehensive model information."""
        return {
            'name': self.name,
            'type': self.model_type,
            'version': self.version,
            'status': self._status.value,
            'is_trained': self.is_trained,
            'feature_names': self._feature_names,
            'feature_count': len(self._feature_names),
            'hyperparameters': self.hyperparameters,
            'metrics': self._metrics.to_dict() if self._metrics else None,
            'training_history_count': len(self._training_history),
            'created_at': self._created_at.isoformat(),
            'last_trained': self._last_trained.isoformat() if self._last_trained else None,
        }