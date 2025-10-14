# Installation Guide

This guide will help you install and set up FilantropiaSolar on your system.

## Prerequisites

- **Python 3.8+** installed on your system
- **10GB+** free disk space for data and models
- **Internet connection** for initial setup and weather data

### System Requirements

#### Minimum Requirements
- Python 3.8 or higher
- 4GB RAM
- 1GB free disk space
- Internet connection (for weather data)

#### Recommended
- Python 3.9+
- 8GB RAM
- SSD storage
- Stable broadband connection

## Installation Methods

### Method 1: Clone from GitHub

1. **Clone the repository**:
   ```bash
   git clone https://github.com/WeRaDev/FilantropiaSolar.git
   cd FilantropiaSolar
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Method 2: Using pip (when available on PyPI)

```bash
pip install filantropia-solar
```

## Verification

After installation, verify everything is working:

1. **Check Python version**:
   ```bash
   python --version
   ```

2. **Verify data directories**:
   ```bash
   ls -la data/ weather_files/
   ```

3. **Test import**:
   ```python
   python -c "import src.data_processing; print('Installation successful!')"
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project root (use `.env.template` as reference):

```bash
cp .env.template .env
```

Edit `.env` with your specific configuration:

```bash
# Weather API Configuration
WEATHER_API_KEY=your_api_key_here
WEATHER_API_BASE_URL=https://api.open-meteo.com/v1

# Data Paths
DATA_PATH=./data
WEATHER_FILES_PATH=./weather_files
MODELS_PATH=./models

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/application.log
```

### Initial Setup

Run the initial setup script:

```bash
python main.py --setup
```

This will:
- Create necessary directories
- Download sample data (if available)
- Initialize configuration files
- Test API connections

## Troubleshooting

### Common Issues

#### Import Errors
```bash
ModuleNotFoundError: No module named 'src'
```
**Solution**: Ensure you're in the project root directory and virtual environment is activated.

#### Permission Errors
```bash
PermissionError: [Errno 13] Permission denied
```
**Solution**: Check file permissions and ensure you have write access to the project directory.

#### Memory Issues
```bash
MemoryError during model training
```
**Solution**: Ensure you have sufficient RAM (8GB+ recommended) or reduce data batch sizes.

### Getting Help

If you encounter issues:

1. Check the [GitHub Issues](https://github.com/WeRaDev/FilantropiaSolar/issues)
2. Create a new issue with:
   - Your operating system
   - Python version
   - Error messages
   - Steps to reproduce

## Next Steps

After successful installation:

1. Run the application: `python main.py`
2. Explore the interface and features
3. Check the main README.md for detailed usage instructions
