# FilantropiaSolar - Development Guide

> **Complete guide for setting up and working with the FilantropiaSolar development environment**

## 🚀 Quick Start

### Automated Setup (Recommended)

For the fastest setup, use our automated development script:

```bash
# Run the automated setup script
./scripts/dev-setup.sh
```

This will:
- Check Python version compatibility
- Set up virtual environment
- Install all dependencies
- Configure pre-commit hooks
- Run initial tests
- Create development scripts

### Manual Setup

If you prefer manual setup or need more control:

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install development dependencies
pip install -r requirements-dev.txt
pip install -e .

# 3. Setup pre-commit hooks
pre-commit install --install-hooks

# 4. Copy environment template
cp .env.template .env
# Edit .env with your configuration

# 5. Run tests to verify setup
pytest tests/ -v
```

## 📋 Prerequisites

### System Requirements

- **Python 3.11+** (3.14 recommended)
- **Git** for version control
- **Docker & Docker Compose** (optional, for containerized development)
- **Make** (optional, for using Makefile commands)

### macOS Installation

```bash
# Install Python via Homebrew
brew install python@3.11

# Install Docker Desktop
brew install --cask docker

# Install additional tools
brew install git make
```

### Linux Installation

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
sudo apt install git make docker.io docker-compose

# Enable Docker for current user
sudo usermod -aG docker $USER
```

## 🛠️ Development Environment

### Project Structure

```
FilantropiaSolar/
├── src/                          # Source code
│   └── filantropia_solar/        # Main package
├── tests/                        # Test suite
├── docs/                         # Documentation
├── scripts/                      # Development scripts
├── config/                       # Configuration files
├── .github/                      # GitHub workflows
├── pyproject.toml                # Project configuration
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Development dependencies
├── Dockerfile                    # Container definition
├── docker-compose.yml            # Multi-service orchestration
├── Makefile                      # Development commands
└── .pre-commit-config.yaml       # Code quality hooks
```

### Virtual Environment Management

```bash
# Activate virtual environment
source venv/bin/activate

# Deactivate when done
deactivate

# Recreate virtual environment if needed
rm -rf venv
make venv
make install
```

### Dependency Management

```bash
# Install production dependencies only
make install-prod

# Install all development dependencies
make install

# Update dependencies
make update-deps

# Check for outdated packages
make deps-check
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov

# Run specific test categories
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-ml           # ML model tests
make test-performance  # Performance benchmarks
```

### Test Categories

- **Unit Tests**: Fast, isolated component tests
- **Integration Tests**: Component interaction tests
- **ML Tests**: Machine learning model validation
- **Performance Tests**: Benchmarking and profiling

### Writing Tests

```python
# Example test structure
import pytest
from filantropia_solar.prediction import EnergyPredictor

class TestEnergyPredictor:
    @pytest.fixture
    def predictor(self):
        return EnergyPredictor(mock_data_processor)
    
    def test_prediction_basic(self, predictor):
        result = predictor.predict(installation_id="test", date="2023-06-15")
        assert result.energy_kwh > 0
    
    @pytest.mark.slow
    def test_model_training(self, predictor):
        # Slow test that trains actual models
        pass
    
    @pytest.mark.ml
    def test_model_accuracy(self, predictor):
        # ML-specific test
        pass
```

## 🔧 Code Quality

### Linting and Formatting

```bash
# Format code
make format

# Run linting
make lint

# Type checking
make typecheck

# Security scanning
make security

# Run all quality checks
make quality
```

### Pre-commit Hooks

Pre-commit hooks automatically run on every commit:

```bash
# Install hooks (done by dev-setup.sh)
pre-commit install

# Run hooks manually
pre-commit run --all-files

# Update hooks
pre-commit autoupdate
```

### Code Style Guidelines

- **Line length**: 88 characters (Black default)
- **Import sorting**: Use ruff/isort configuration
- **Type hints**: Required for all public APIs
- **Docstrings**: Google-style for all public functions
- **Variable naming**: `snake_case` for variables, `UPPER_CASE` for constants

## 📚 Documentation

### Building Documentation

```bash
# Build documentation
make docs

# Serve documentation locally
make docs-serve

# Deploy to GitHub Pages
make docs-deploy
```

### Documentation Structure

- **API Reference**: Auto-generated from docstrings
- **User Guide**: Step-by-step usage instructions
- **Developer Guide**: Architecture and development info
- **Examples**: Jupyter notebooks and code samples

### Writing Documentation

```python
def predict_energy(installation_id: str, date: datetime) -> PredictionResult:
    """Predict energy production for a specific installation and date.
    
    Args:
        installation_id: Unique identifier for the PV installation
        date: Date for which to predict energy production
        
    Returns:
        PredictionResult containing energy predictions and metadata
        
    Raises:
        ValueError: If installation_id is not found
        ModelNotTrainedError: If no trained model exists
        
    Example:
        >>> predictor = EnergyPredictor(data_processor)
        >>> result = predictor.predict_energy("Lisbon_1", datetime(2023, 6, 15))
        >>> print(f"Predicted energy: {result.energy_kwh:.2f} kWh")
    """
```

## 🐳 Docker Development

### Building Images

```bash
# Build production image
make docker-build

# Build development image
make docker-build-dev

# Run container
make docker-run
```

### Using Docker Compose

```bash
# Start all services
make docker-up

# Start with monitoring
docker-compose up --profile monitoring

# Start with GUI support
docker-compose up --profile gui

# View logs
make docker-logs

# Stop all services
make docker-down
```

### Development Container

```bash
# Run development container with code mounting
docker-compose up development

# Execute commands inside container
docker-compose exec filantropia-api bash
```

## ⚡ Performance Optimization

### Profiling

```bash
# CPU profiling
make profile

# Memory profiling
make memory-profile

# Benchmark performance
make benchmark
```

### Optimization Guidelines

- Use `polars` instead of `pandas` for large datasets
- Implement async/await for I/O operations
- Use `lru_cache` for expensive computations
- Profile before optimizing

### Memory Management

```python
# Good: Use context managers
with data_processor.load_data(installation_id) as data:
    result = process_data(data)

# Good: Use generators for large datasets
def process_records():
    for record in data_stream:
        yield process_record(record)

# Good: Explicit cleanup
del large_dataframe
gc.collect()
```

## 🔐 Security Best Practices

### Environment Variables

```bash
# Never commit secrets to version control
echo "SECRET_KEY=your-secret-here" >> .env

# Use environment-specific files
cp .env.template .env.development
cp .env.template .env.production
```

### Security Scanning

```bash
# Run security scan
make security

# Check for secrets in commits
git secrets --scan

# Update dependencies for security patches
make update-deps
```

## 📊 Monitoring and Debugging

### Logging

```python
import logging
from loguru import logger

# Use structured logging
logger.info("Processing installation", 
           installation_id=installation_id,
           date=date.isoformat())

# Different log levels
logger.debug("Detailed debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred", exc_info=True)
```

### Debugging Tools

```bash
# Interactive debugging with ipdb
pip install ipdb
import ipdb; ipdb.set_trace()

# Memory profiling
from memory_profiler import profile
@profile
def my_function():
    # Function to profile
    pass

# Performance profiling
import cProfile
cProfile.run('my_function()', 'profile_stats')
```

## 🚢 Release Process

### Version Management

```bash
# Update version in pyproject.toml
# Create git tag
git tag -a v2.0.0 -m "Release version 2.0.0"
git push origin v2.0.0

# Build and check package
make build
make build-check

# Release to test PyPI
make release-test

# Release to PyPI
make release
```

### CI/CD Pipeline

The GitHub Actions workflow automatically:
- Runs tests on multiple Python versions
- Performs code quality checks
- Builds documentation
- Creates Docker images
- Releases to PyPI on tags

## 🔄 Common Development Workflows

### Adding a New Feature

1. **Create feature branch**
   ```bash
   git checkout -b feature/new-awesome-feature
   ```

2. **Write tests first** (TDD approach)
   ```bash
   # Create test file
   touch tests/test_new_feature.py
   # Write failing tests
   make test
   ```

3. **Implement feature**
   ```python
   # Add implementation
   # Run tests to verify
   make test
   ```

4. **Check code quality**
   ```bash
   make quality
   make test-cov
   ```

5. **Commit with conventional commits**
   ```bash
   git add .
   git commit -m "feat: add awesome new feature"
   ```

6. **Push and create PR**
   ```bash
   git push origin feature/new-awesome-feature
   # Create Pull Request on GitHub
   ```

### Debugging Issues

1. **Reproduce the issue**
   ```bash
   # Create minimal reproduction case
   make test-integration  # Run relevant tests
   ```

2. **Add logging**
   ```python
   logger.debug("Debug info", data=data)
   ```

3. **Use debugger**
   ```python
   import ipdb; ipdb.set_trace()
   ```

4. **Profile if performance-related**
   ```bash
   make profile
   make memory-profile
   ```

### Performance Optimization

1. **Measure first**
   ```bash
   make benchmark  # Get baseline
   ```

2. **Profile bottlenecks**
   ```bash
   make profile
   # Identify slow functions
   ```

3. **Optimize critical paths**
   ```python
   # Use appropriate data structures
   # Implement caching
   # Use vectorized operations
   ```

4. **Measure again**
   ```bash
   make benchmark  # Compare results
   ```

## 📞 Getting Help

### Development Issues

1. **Check logs**: `logs/application.log`
2. **Run diagnostics**: `make env-info`
3. **Check dependencies**: `make deps-check`
4. **Search issues**: GitHub Issues tab
5. **Ask questions**: Create new GitHub Issue

### Performance Issues

1. **Profile the application**: `make profile`
2. **Check resource usage**: `htop`, `docker stats`
3. **Review logs**: Look for warning messages
4. **Check database**: Monitor query performance

### Common Problems

| Problem | Solution |
|---------|----------|
| Import errors | `pip install -e .` |
| Test failures | `make clean && make test` |
| Pre-commit issues | `pre-commit clean` |
| Docker issues | `docker system prune` |
| Memory issues | Check model sizes, use pagination |

---

## 📝 Development Checklist

### Before Starting Development

- [ ] Virtual environment activated
- [ ] Dependencies installed (`make install`)
- [ ] Pre-commit hooks working (`pre-commit run`)
- [ ] Tests passing (`make test`)
- [ ] Environment configured (`.env` file)

### Before Committing Code

- [ ] All tests pass (`make test-cov`)
- [ ] Code formatted (`make format`)
- [ ] No linting errors (`make lint`)
- [ ] Type checking passes (`make typecheck`)
- [ ] Documentation updated
- [ ] Commit message follows conventions

### Before Releasing

- [ ] Version updated in `pyproject.toml`
- [ ] CHANGELOG.md updated
- [ ] Documentation built (`make docs`)
- [ ] All tests pass in CI
- [ ] Docker image builds successfully
- [ ] Security scan clean (`make security`)

---

**Happy coding!** 🚀

For additional help, see the main [README.md](README.md) or create an issue on GitHub.