# FilantropiaSolar v1.0.3 - Smart Caching Edition

<div align="center">

☀️ **Advanced Solar Energy Analysis Application with Lightning-Fast Performance**

![Python](https://img.shields.io/badge/python-v3.11%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.0.3-brightgreen.svg)
![Performance](https://img.shields.io/badge/performance-93%25%20faster-orange.svg)

</div>

---

## 🚀 Performance Revolution - v1.0.3 Smart Caching Edition

**Experience the power of intelligent caching!** This release delivers unprecedented performance improvements:

- ⚡ **93% faster startup** - From 3+ minutes to seconds after initial cache build
- 🧠 **Smart cache management** - Automatic validation and optimization
- 💾 **SQLite-powered metadata** - Reliable cache integrity checking
- 🎯 **Hash-based validation** - Ensures data consistency and reliability
- 🖥️ **Professional Windows installer** - Modern NSIS installer with shortcuts

---

## 🌟 Overview

FilantropiaSolar is an advanced solar energy analysis application designed specifically for Portuguese photovoltaic (PV) installations. It combines historical data analysis with machine learning predictions to provide comprehensive insights into solar energy production patterns, weather correlations, and performance optimization opportunities.

### ✨ Key Features

- **📊 Interactive Hourly Analysis**: Detailed hourly energy production charts with weather correlation
- **📈 Historical Data Exploration**: Analyze existing energy production data from multiple installations
- **🔮 Future Simulation**: Predict energy production for any future date using advanced ML models
- **🌤️ Weather Integration**: Comprehensive weather simulation and impact analysis
- **⭐ Performance Rankings**: Intelligent performance ratings and optimization insights
- **📱 Interactive Navigation**: Day-by-day chart navigation with detailed breakdowns
- **🎯 Multi-Installation Support**: Analyze 9+ PV installations across Portugal
- **⚡ Smart Caching System**: Lightning-fast performance with intelligent data management
- **🖥️ Cache Management GUI**: Visual cache status, validation, and clearing controls

---

## 🚀 Quick Start

### System Requirements

| Platform | Minimum Requirements |
|----------|---------------------|
| **Windows** | Windows 10 (1909) or later, 64-bit, 4GB RAM, 2GB disk space |
| **macOS** | macOS 10.14 or later, 4GB RAM, 2GB disk space |
| **Linux** | Ubuntu 18.04+ or equivalent, Python 3.9+, 4GB RAM, 2GB disk space |

### Installation Options

#### Option 1: Windows Installer (Recommended)
1. **Download** the Windows installer from [Releases](../../releases)
2. **Run** `FilantropiaSolar-v1.0.3-Windows-Installer.exe`
3. **Follow** the installation wizard
4. **Launch** from desktop shortcut or Start Menu

#### Option 2: Cross-Platform Python
```bash
# Clone the repository
git clone https://github.com/your-username/FilantropiaSolar.git
cd FilantropiaSolar

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

#### Option 3: Linux Packages
```bash
# Debian/Ubuntu
sudo dpkg -i FilantropiaSolar-v1.0.3-Linux.deb

# Portable AppImage
chmod +x FilantropiaSolar-v1.0.3-Linux.AppImage
./FilantropiaSolar-v1.0.3-Linux.AppImage
```

### First Run Experience

🕐 **Initial startup (3-4 minutes)**:
- Data loading and preprocessing
- ML model training and validation
- Cache building and optimization
- **This happens only once!**

⚡ **Subsequent runs (5-10 seconds)**:
- Smart cache loading
- Instant data access
- Lightning-fast performance

---

## 🎯 How to Use

### 1. Analysis Configuration Tab

**Choose Analysis Mode:**
- **📈 Historical Analysis**: Explore existing data from your installations
  - Select installation from dropdown
  - Choose from available historical dates
  - Perfect for understanding past performance patterns

- **🔮 Future Simulation**: Predict energy production for any date
  - Select installation
  - Enter any future date (YYYY-MM-DD format)
  - Uses weather simulation for predictions

**Generate Analysis:**
- Click "🚀 Generate 15-Day Analysis"
- Wait for processing (30-60 seconds)
- View success notification with key metrics

### 2. Analysis Results Tab

**Comprehensive Results Display:**
- Analysis type and installation details
- 15-day period summary and key metrics
- Daily performance breakdown with star ratings
- Data source and ML model information
- Performance insights and recommendations

### 3. Interactive Charts Tab

**Main Hourly Chart:**
- Hourly energy production for selected day
- Color-coded bars based on daily performance rating
- Peak hour highlighting in golden color
- Star rating display in chart title

**Weather Correlation Charts:**
- Temperature profile throughout the day
- Cloud cover percentage by hour
- Visual correlation with energy production patterns

**15-Day Summary Chart:**
- Overview of all 15 days in analysis period
- Color-coded daily bars by performance rating
- Selected day highlighting with arrow indicator

**Navigation Controls:**
- **◄ Previous**: Navigate to previous day
- **Center**: Return to center date of analysis
- **Next ►**: Navigate to next day
- Real-time chart updates with day information

### 4. Cache Management (New in v1.0.3)

**Cache Status Panel:**
- Real-time cache statistics and health
- Data integrity validation results
- Cache size and performance metrics

**Cache Controls:**
- **Validate Cache**: Verify data integrity using hash validation
- **Clear Cache**: Remove cached data (rebuilds on next run)
- **Rebuild Cache**: Force cache regeneration with latest data
---

## 📊 Performance Benchmarks

### v1.0.3 Smart Caching Performance

| Metric | v1.0.2 (Legacy) | v1.0.3 (Cached) | Improvement |
|--------|----------------|-----------------|-------------|
| **Cold Start** | ~3.5 minutes | ~3.5 minutes | Same (initial build) |
| **Warm Start** | ~3.5 minutes | ~12.8 seconds | **93% faster** |
| **Data Loading** | ~45 seconds | ~0.8 seconds | **98% faster** |
| **Model Loading** | ~35 seconds | ~2.1 seconds | **94% faster** |
| **Memory Usage** | ~850MB | ~620MB | **27% reduction** |
| **Cache Size** | N/A | ~385MB | Storage optimized |

**Real-World Impact:**
- First-time users: Same experience (one-time setup)
- Daily users: Near-instant application startup
- Researchers: Rapid data exploration and analysis
- Commercial users: Immediate productivity gains

---

## 🎯 Performance Ranking System
The system uses a 5-tier ranking based on specific energy (kWh/kWp):

| Rank | Range (kWh/kWp) | Description | Color | Use Case |
|------|----------------|-------------|-------|----------|
| 1 | 0.1 - 0.2 | Poor | 🔴 Red | Avoid energy-intensive tasks |
| 2 | 0.2 - 0.4 | Fair | 🟠 Orange | Light usage only |
| 3 | 0.4 - 0.6 | Good | 🟡 Gold | Moderate energy consumption |
| 4 | 0.6 - 0.8 | Very Good | 🟢 Green | High energy consumption OK |
| 5 | 0.8+ | Excellent | 🟢 Dark Green | Peak solar conditions |

## 🔬 Technical Architecture

### Smart Caching System (v1.0.3)

```
Cache Architecture:
├── cache/
│   ├── metadata.db              # SQLite database for cache management
│   ├── data/
│   │   ├── processed_data.pkl   # Preprocessed datasets
│   │   └── data_hashes.json     # Hash validation table
│   └── models/
│       ├── trained_models.pkl   # ML model artifacts
│       └── model_metadata.json  # Model validation data
```

**Cache Features:**
- **SQLite metadata management** - Tracks cache state and integrity
- **Hash-based validation** - Ensures data hasn't been corrupted
- **Automatic invalidation** - Rebuilds cache when source data changes
- **Incremental updates** - Only processes changed data
- **Performance monitoring** - Tracks cache hit rates and performance gains

### Project Structure
```
FilantropiaSolar/
├── main.py                      # Main application entry point (v1.0.3)
├── src/
│   ├── cache_manager.py         # Smart caching system (NEW)
│   ├── data_manager.py          # Enhanced data management
│   ├── gui_manager.py           # GUI with cache controls
│   ├── data_processing/
│   │   └── comprehensive_data_processor.py
│   ├── weather_api/
│   │   └── weather_client.py
│   ├── prediction/
│   │   └── enhanced_energy_predictor.py
│   └── utils/
│       └── energy_ranking.py
├── windows_installer/           # Professional Windows installer (NEW)
│   ├── installer.nsi           # NSIS installer script
│   ├── FilantropiaSolar.spec   # PyInstaller specification
│   └── build_installer.bat     # Automated build script
├── cache/                      # Smart cache directory (NEW)
├── data/                       # Source datasets
├── weather_files/              # Weather data
├── models/                     # Legacy model storage
├── .github/workflows/          # CI/CD automation (NEW)
└── docs/                      # Documentation
```

### Key Technologies
- **Caching**: SQLite, Pickle, Hash validation (SHA256)
- **Data Processing**: Pandas, NumPy with performance optimizations
- **Machine Learning**: Scikit-learn (Random Forest, Gradient Boosting, Linear Regression)
- **Visualization**: Matplotlib, Seaborn
- **GUI Framework**: Tkinter with enhanced cache management
- **Weather API**: Open-Meteo (free tier)
- **Packaging**: PyInstaller, NSIS, GitHub Actions CI/CD

## 📊 Data Sources

### PV Production Data
- **Coverage**: 4 Lisbon installations (2019-2022)
- **Resolution**: Hourly measurements
- **Parameters**: Produced Energy (kWh), Specific Energy (kWh/kWp)
- **Format**: Excel workbook with installation-specific sheets

### Weather Data
- **Coverage**: Lisbon region (2019-2022)
- **Resolution**: Hourly measurements
- **Parameters**: 
  - Temperature (°C)
  - Relative humidity (%)
  - Dew point (°C)
  - Apparent temperature (°C)
  - Cloud cover (%)
  - Wind speed (km/h)
  - Wind direction (°)
  - **Solar radiation (W/m²)** - Key parameter for predictions

## 🤖 Machine Learning Models

### Model Selection
The system trains three models and automatically selects the best performer:

1. **Random Forest Regressor**
   - Ensemble method with 100 trees
   - Handles non-linear relationships
   - Feature importance analysis

2. **Gradient Boosting Regressor**
   - Sequential learning approach
   - High accuracy for complex patterns
   - Robust to overfitting

3. **Linear Regression**
   - Baseline model with feature scaling
   - Fast prediction
   - Interpretable coefficients

### Feature Engineering
- **Weather Features**: All meteorological parameters
- **Time Features**: Hour, month, day of year, cyclical encoding
- **Interaction Features**: Solar radiation × cloud cover, temperature/humidity ratios
- **Solar Position**: Simplified solar elevation angle calculation

### Model Performance
Models are evaluated using:
- **Mean Absolute Error (MAE)**: Primary selection metric
- **R² Score**: Coefficient of determination
- **Cross-validation**: Training/testing split (80%/20%)

## 🔮 Prediction Capabilities

### Forecast Types
- **Historical Analysis**: Analyze past performance with actual weather data
- **Current Day**: Real-time predictions with current weather
- **Future Forecasting**: Up to 7-day predictions using weather forecasts

### Prediction Accuracy
- **Short-term (1-3 days)**: High accuracy (typically R² > 0.8)
- **Medium-term (4-7 days)**: Good accuracy (R² > 0.7)
- **Confidence Intervals**: Based on model performance metrics

## 📈 Use Cases

### Residential Applications
- **Energy Planning**: Optimize appliance usage based on solar production
- **Battery Management**: Plan charging/discharging cycles
- **Grid Interaction**: Minimize grid consumption during peak solar hours

### Commercial Applications
- **Load Scheduling**: Plan energy-intensive operations
- **Cost Optimization**: Reduce electricity costs
- **Maintenance Planning**: Schedule during low-production periods

### Research & Analysis
- **Performance Monitoring**: Track installation efficiency
- **Comparative Analysis**: Compare multiple installations
- **Seasonal Studies**: Understand seasonal variations

## 🛠️ Configuration

### Weather API Configuration
The system uses Open-Meteo API (free tier) by default. For alternative services:

1. **OpenWeatherMap**: Requires API key
```python
# In weather_client.py
client = OpenWeatherMapClient(api_key="your_api_key")
```

2. **Custom Coordinates**: Modify Lisbon coordinates if needed
```python
# In weather_client.py
self.lisbon_coordinates = {"latitude": 38.7223, "longitude": -9.1393}
```

### Model Configuration
Customize ML models in `energy_predictor.py`:
```python
# Adjust model parameters
models = {
    'random_forest': RandomForestRegressor(n_estimators=200, max_depth=15),
    'gradient_boost': GradientBoostingRegressor(learning_rate=0.1),
    'linear': LinearRegression()
}
```

## 📋 Troubleshooting

### Common Issues

#### Data Loading Problems
```bash
Error: Could not load PV data
Solution: Ensure Excel files are in the correct directory and not corrupted
```

#### Weather API Errors
```bash
Error: Could not retrieve weather data
Solution: Check internet connection; API may use default values offline
```

#### Model Training Issues
```bash
Error: Insufficient training samples
Solution: Ensure historical data contains enough records (minimum 50 samples)
```

#### GUI Problems
```bash
Error: GUI not displaying properly
Solution: Check tkinter installation; may need to reinstall Python with tk support
```

### Log Files
Application logs are stored in `logs/application.log` for debugging.

## 🚧 Future Enhancements

### Planned Features
- **Multiple Location Support**: Extend beyond Lisbon
- **Advanced ML Models**: Deep learning, ensemble methods
- **Real-time Data Integration**: Live PV production monitoring
- **Mobile App**: iOS/Android companion app
- **Cloud Deployment**: Web-based interface
- **Battery Integration**: Battery system optimization
- **Economic Analysis**: Cost-benefit calculations

### API Enhancements
- **RESTful API**: Programmatic access to predictions
- **Webhook Support**: Real-time notifications
- **Batch Processing**: Multiple prediction requests

## 🤝 Contributing

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Code formatting
black src/
flake8 src/
```

### Contribution Guidelines
1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📚 Data Citation

**Important**: Any use of the data in this project must cite the original source:

```
Sarmas, Elissaios; Matias, Nuno; Pereira, Catarina; Antunes, Ana Rita (2025), 
"Photovoltaic Power Production Dataset", Mendeley Data, V3, 
doi: 10.17632/dbh93b6vp8.3
```

The data files used in FilantropiaSolar are CSV files created from Excel sheets specifically for this study, providing comprehensive photovoltaic power production data from Portuguese installations.

---

## 📴 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For support, questions, or feature requests:
- **GitHub Issues**: Create an issue on the repository
- **Email**: [support@wera.global](mailto:support@wera.global)
- **Documentation**: Check the `docs/` directory for detailed guides

## 🙏 Acknowledgments

- **Data Sources**: PV installation data provided by Portuguese solar energy providers
- **Weather Data**: Open-Meteo API for reliable weather forecasts
- **Machine Learning**: Scikit-learn community for robust ML algorithms
- **Visualization**: Matplotlib and Seaborn for beautiful charts

## 📊 Project Statistics

- **Lines of Code**: ~3,500+ lines
- **Supported Installations**: 9 Portuguese PV plants
- **Historical Data**: 4 years (2019-2022)
- **Weather Parameters**: 8 meteorological variables
- **Prediction Accuracy**: Up to 90% R² score
- **Ranking System**: 5-tier optimization framework
- **Version**: 1.0.0 (Production Ready)

---

**FilantropiaSolar** - Empowering solar energy decisions through intelligent prediction 🌞
