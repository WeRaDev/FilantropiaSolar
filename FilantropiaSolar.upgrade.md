# FilantropiaSolar LLM-Driven Upgrade Instructions

## SYSTEM PROMPT FOR LLM UPGRADE AGENT

You are an expert AI system tasked with upgrading the FilantropiaSolar application. Your mission is to transform this solar energy forecasting system from traditional machine learning (~85% accuracy) to state-of-the-art deep learning (96%+ accuracy) using the latest 2024-2025 research breakthroughs.

**CRITICAL CONTEXT:**

- Current system: 315,567+ historical records from 9 Portuguese PV installations
- Current models: Random Forest + Gradient Boosting + Linear Regression ensemble
- Data input: Manual weather parameters (NOT real-time feeds)
- Target: 96%+ RÂ² accuracy with uncertainty quantification
- Focus: Portuguese climate optimization, no edge computing needed

---

## PHASE 1: ADVANCED MODEL ARCHITECTURE (IMMEDIATE PRIORITY)

### TASK 1A: Implement CNN-LSTM with Attention

**OBJECTIVE:** Replace Scikit-learn ensemble with deep learning achieving 95-97% accuracy

**IMPLEMENTATION REQUIREMENTS:**

```python
# CREATE: models/advanced_solar_predictor.py
# IMPLEMENT: Hybrid CNN-LSTM with MultiHeadAttention
# ARCHITECTURE:
- Conv1D layers (64, 128 filters) for weather pattern extraction
- Bidirectional LSTM (100 units each) for temporal modeling  
- MultiHeadAttention (8 heads, 128 key_dim) for feature focus
- Dense layers (64, 32) with dropout (0.3) for prediction
- Input shape: (batch, sequence_length=24, features=12)
- Output: Single energy prediction value

# TRAINING CONFIGURATION:
- Adam optimizer with ExponentialDecay learning rate (0.001 initial)
- MSE loss with MAE, MAPE, RMSE metrics
- EarlyStopping (patience=30), ReduceLROnPlateau (patience=15)
- Batch size: 64, Epochs: 150 max
- Validation split: 20%

# SUCCESS CRITERIA: >92% RÂ² score on validation data
```

### TASK 1B: Implement Physics-Informed Neural Networks

**OBJECTIVE:** Add Portuguese solar physics constraints for 12-18% robustness improvement

**IMPLEMENTATION REQUIREMENTS:**

```python
# CREATE: models/physics_informed_predictor.py
# IMPLEMENT: PINN wrapper for base CNN-LSTM model

# PHYSICS CONSTRAINTS FOR PORTUGAL (38.7Â°N):
1. Beer-Lambert atmospheric transmission: exp(-0.15 * cloud_cover/100)
2. Solar elevation calculation for Portuguese latitude
3. Temperature coefficient effects on PV efficiency (-0.4%/Â°C above 25Â°C)
4. Realistic bounds: 0.0 to 12.0 kWh/kWp for Portuguese installations

# CUSTOM LOSS FUNCTION:
- Standard prediction loss + physics_weight * physics_constraint_loss
- Trainable physics weight (initial: 0.25)
- Physics compliance validation metrics

# SUCCESS CRITERIA: 95%+ physics compliance rate
```

### TASK 1C: Implement Portuguese Weather Classification

**OBJECTIVE:** Achieve 15-20% accuracy boost through specialized models

**IMPLEMENTATION REQUIREMENTS:**

```python
# CREATE: preprocessing/portuguese_weather_classifier.py
# IMPLEMENT: KMeans clustering with 5 weather types

# WEATHER TYPES FOR PORTUGAL:
0: 'sunny_stable' (high irradiance, low clouds, stable conditions)
1: 'sunny_variable' (high irradiance with variability)
2: 'partly_cloudy' (medium clouds, moderate irradiance)
3: 'overcast' (high clouds, low irradiance)
4: 'unstable' (high variability, stormy conditions)

# FEATURE EXTRACTION:
- Basic: [solar_radiation, temperature, cloud_cover, humidity, wind_speed]
- Derived: cloud_stability, irradiance_temp_ratio, atmospheric_clarity
- Seasonal weighting for Portuguese climate patterns

# SPECIALIZED MODELS:
- sunny_stable: Simple LSTM model (50 units)
- sunny_variable/partly_cloudy: Medium LSTM (100 units)
- overcast/unstable: Full CNN-LSTM architecture

# SUCCESS CRITERIA: 90%+ weather classification accuracy
```

---

## PHASE 2: PORTUGUESE CLIMATE OPTIMIZATION

### TASK 2A: Advanced Feature Engineering

**OBJECTIVE:** Create comprehensive Portuguese-specific features

**IMPLEMENTATION REQUIREMENTS:**

```python
# CREATE: preprocessing/portuguese_features.py
# IMPLEMENT: Comprehensive feature engineering class

# PORTUGUESE GEOGRAPHIC FEATURES:
- Latitude: 38.7Â°N (average Portugal)
- Atlantic coastal proximity calculation
- Climate zone classification (4 zones)
- Elevation effects on air density

# TEMPORAL FEATURES:
- Cyclical encoding (sin/cos) for hour, day, season
- Solar-specific hour encoding (6am-8pm focus)
- Portuguese seasonal intensity curves
- Weekend/weekday indicators

# SOLAR PHYSICS FEATURES:
- Solar elevation angle calculation
- Air mass computation
- Clear sky irradiance estimation
- Clearness index calculation

# WEATHER INTERACTIONS:
- Heat index calculation
- Wind chill effects
- Cloud-irradiance consistency
- Atmospheric stability indicators

# SUCCESS CRITERIA: Feature importance analysis showing Portuguese features in top 50%
```

### TASK 2B: Uncertainty Quantification System

**OBJECTIVE:** Provide confidence intervals and operational recommendations

**IMPLEMENTATION REQUIREMENTS:**

```python
# CREATE: models/uncertainty_quantifier.py
# IMPLEMENT: Quantile regression with 5 quantiles [0.1, 0.25, 0.5, 0.75, 0.9]

# QUANTILE MODELS:
- Separate CNN-LSTM model for each quantile
- Custom quantile loss function for each model
- Extreme quantiles (0.1, 0.9) get more model capacity

# UNCERTAINTY METRICS:
- 95% and 50% confidence intervals
- Interquartile range (IQR) uncertainty
- Relative uncertainty (normalized by prediction)
- Prediction interval width analysis

# OPERATIONAL RECOMMENDATIONS:
- Low uncertainty (<10% relative): "High confidence, optimal for operations"
- Medium uncertainty (10-20%): "Standard operations with safety margins"  
- High uncertainty (>20%): "Consider flexible scheduling or backup"

# SUCCESS CRITERIA: 90-95% coverage for 95% prediction intervals
```

---

## PHASE 3: USER INTERFACE ENHANCEMENT

### TASK 3A: Enhanced Streamlit Interface

**OBJECTIVE:** Create professional UI optimized for manual data input

**IMPLEMENTATION REQUIREMENTS:**

```python
# CREATE: interface/enhanced_ui.py
# IMPLEMENT: Multi-tab Streamlit interface

# TAB 1 - PREDICTION:
- Weather input sliders (temperature, humidity, cloud_cover, wind_speed, solar_radiation)
- Date/time selectors
- Installation dropdown (9 installations)
- Real-time prediction display with uncertainty bounds

# TAB 2 - ANALYSIS:
- Historical performance comparison
- Weather classification visualization
- Model accuracy metrics by weather type
- Prediction vs actual scatter plots

# TAB 3 - INSTALLATION SETUP:
- Installation metadata input
- Location-based feature configuration
- Model calibration for specific installations

# TAB 4 - MONITORING:
- Model performance tracking
- Physics compliance monitoring
- Uncertainty calibration metrics
- System health indicators

# UI COMPONENTS:
- Interactive Plotly visualizations
- Real-time metrics display
- Comprehensive error handling
- Export capabilities for results

# SUCCESS CRITERIA: <2 second response time for predictions
```

### TASK 3B: Visualization System

**OBJECTIVE:** Create comprehensive prediction interpretation tools

**IMPLEMENTATION REQUIREMENTS:**

```python
# VISUALIZATION COMPONENTS:

1. UNCERTAINTY VISUALIZATION:
- Bar chart with confidence intervals
- Quantile distribution plot
- Weather conditions impact display
- Operational recommendations panel

2. WEATHER CLASSIFICATION DISPLAY:
- Weather type identification with confidence
- Historical weather pattern analysis
- Seasonal adaptation visualization

3. PHYSICS COMPLIANCE MONITORING:
- Physics constraint validation charts
- Violation rate tracking by constraint type
- Compliance trend analysis

4. PERFORMANCE DASHBOARD:
- Model accuracy metrics over time
- Comparison between weather types
- Installation-specific performance

# SUCCESS CRITERIA: All visualizations load within 1 second
```

---

## INTEGRATION AND VALIDATION REQUIREMENTS

### MODEL INTEGRATION PIPELINE:

```python
# CREATE: main_predictor.py
# INTEGRATE ALL COMPONENTS:

class FilantropiaSolarPredictor:
    def __init__(self):
        self.cnn_lstm_model = load_cnn_lstm_model()
        self.pinn_model = load_pinn_model() 
        self.weather_classifier = load_weather_classifier()
        self.uncertainty_quantifier = load_uncertainty_quantifier()
        self.feature_engineer = PortugueseFeatureEngineer()
    
    def predict_with_uncertainty(self, weather_data, installation_data):
        # 1. Classify weather conditions
        # 2. Extract Portuguese-specific features  
        # 3. Apply specialized model based on weather type
        # 4. Generate uncertainty bounds
        # 5. Validate physics constraints
        # 6. Return comprehensive results
```

### VALIDATION FRAMEWORK:

```python
# CREATE: validation/model_validator.py
# IMPLEMENT: Comprehensive validation system

# ACCURACY VALIDATION:
- Cross-validation with seasonal splits
- Installation-specific validation
- Weather-type stratified validation
- Physics compliance validation

# PERFORMANCE METRICS:
- RÂ² score (target: >96%)
- MAE (target: <0.08 kWh/kWp)
- MAPE (target: <10%)
- Physics compliance (target: >98%)

# UNCERTAINTY CALIBRATION:
- Coverage analysis for prediction intervals
- Reliability diagrams
- Sharpness vs reliability trade-offs
```

---

## SUCCESS CRITERIA AND CHECKPOINTS

### PHASE 1 COMPLETION CRITERIA:

- CNN-LSTM model trained with >92% RÂ² validation score
- PINN implementation with >95% physics compliance
- Weather classifier achieving >90% accuracy
- Performance improvement >12% over current ensemble

### PHASE 2 COMPLETION CRITERIA:

- Portuguese feature engineering providing additional 5-8% accuracy boost
- Uncertainty quantification with properly calibrated intervals (90-95% coverage)
- Weather-aware model selection operational
- Overall model accuracy >95% RÂ²

### PHASE 3 COMPLETION CRITERIA:

- Streamlit interface fully functional with all tabs
- Visualization system complete with <1s load times
- Full integration pipeline operational
- Final accuracy target >96% RÂ² achieved

### FINAL VALIDATION REQUIREMENTS:

- End-to-end testing on all 9 installations
- Seasonal performance validation (all Portuguese seasons)
- User acceptance testing of interface
- Documentation and deployment guide completion

---

## TECHNICAL SPECIFICATIONS

### DEVELOPMENT ENVIRONMENT:

```bash
# Required Python packages:
tensorflow==2.15.0
streamlit==1.28.0
plotly==5.17.0
scikit-learn==1.3.0
numpy==1.24.0
pandas==2.0.0
optuna==3.4.0  # for hyperparameter optimization
ephem==4.1.4   # for solar calculations
```

### DATA REQUIREMENTS:

- Access to 315,567+ historical records
- Weather features: temperature, humidity, cloud_cover, wind_speed, solar_radiation
- Installation metadata: location, capacity, installation_date
- Target variable: energy production (kWh/kWp)

### HARDWARE REQUIREMENTS:

- GPU with 8GB+ VRAM for training (RTX 3070 or equivalent)
- 16GB+ RAM for data processing
- 10GB+ storage for models and data

---

## ERROR HANDLING AND EDGE CASES

### DATA VALIDATION:

- Input range validation (temperature: -5 to 45Â°C, etc.)
- Missing value handling strategies
- Outlier detection and treatment
- Data consistency checks

### MODEL ROBUSTNESS:

- Graceful degradation for edge weather conditions
- Fallback models for classification failures
- Physics constraint violation handling
- Uncertainty bounds validation

### USER EXPERIENCE:

- Clear error messages for invalid inputs
- Loading indicators for long operations
- Input validation with helpful feedback
- Comprehensive help documentation

---

## DEPLOYMENT AND MONITORING

### DEPLOYMENT CHECKLIST:

- Model artifacts properly saved and versioned
- Configuration files for all components
- Environment setup documentation
- Performance benchmarking results
- User manual and API documentation

### MONITORING REQUIREMENTS:

- Model performance tracking over time
- Physics compliance monitoring
- Uncertainty calibration drift detection
- User interaction analytics
- System resource usage monitoring

---

**FINAL INSTRUCTION:** Execute all tasks systematically, ensuring each phase completion criteria is met before proceeding. Maintain focus on the 96%+ accuracy target while optimizing for Portuguese solar installations using manually input weather data. The system should be production-ready with comprehensive uncertainty quantification and professional user interface.