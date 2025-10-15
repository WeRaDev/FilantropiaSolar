# Warp Agent Setup for FilantropiaSolar Development

## Overview
This document describes the Warp Agent configuration for the FilantropiaSolar project development environment.

## Installation Status
- ✅ **Warp CLI**: Installed at `/usr/local/bin/warp`
- ✅ **Agent Commands**: Available and tested
- ✅ **Project Analysis**: Successfully completed

## Agent Profile Configuration

### Recommended Profile Settings
```
Profile Name: FilantropiaSolar Development
Description: Dedicated agent profile for FilantropiaSolar solar energy analysis application
```

### Permissions
```
Allowed Directories:
  - /Users/mikhailananyin/Documents/FilantropiaSolar
  - /Users/mikhailananyin/Documents/FilantropiaSolar/src
  - /Users/mikhailananyin/Documents/FilantropiaSolar/tests
  - /Users/mikhailananyin/Documents/FilantropiaSolar/config
  - /Users/mikhailananyin/Documents/FilantropiaSolar/scripts

Allowed Commands:
  - python (Python execution)
  - pip (Package management)
  - git (Version control)
  - docker (Containerization)
  - pytest (Testing)
  - black (Code formatting)
  - ruff (Linting)
  - make (Build automation)
  - tree (Directory listing)
  - ls, cat, find (File operations)

File Operations:
  - Read: All project files
  - Write: Source code, tests, documentation, configuration
  - Execute: Scripts, Python files, build commands
```

## Usage Examples

### Development Tasks
```bash
# Code analysis and refactoring
warp agent run --profile <profile-id> --prompt "Analyze the data processing module and suggest performance optimizations"

# Testing assistance
warp agent run --profile <profile-id> --prompt "Run the test suite and fix any failing tests"

# Documentation updates
warp agent run --profile <profile-id> --prompt "Update the README with the latest features and usage examples"

# Docker management
warp agent run --profile <profile-id> --prompt "Build and test the Docker container, then optimize the Dockerfile"

# Code quality improvements
warp agent run --profile <profile-id> --prompt "Run linting tools and fix code style issues"
```

### Data Analysis Tasks
```bash
# Data exploration
warp agent run --profile <profile-id> --prompt "Analyze the solar production data and generate summary statistics"

# ML model improvements
warp agent run --profile <profile-id> --prompt "Optimize the machine learning models for better prediction accuracy"

# Performance analysis
warp agent run --profile <profile-id> --prompt "Profile the application performance and identify bottlenecks"
```

### Deployment Tasks
```bash
# Release preparation
warp agent run --profile <profile-id> --prompt "Prepare a new release by updating version numbers and generating release notes"

# Security audit
warp agent run --profile <profile-id> --prompt "Run security scans and update vulnerable dependencies"

# Environment setup
warp agent run --profile <profile-id> --prompt "Set up a fresh development environment and verify all components work"
```

## Project-Specific Context

### Key Components the Agent Can Work With
- **Data Processing**: `src/data_processing/` - Excel data processing, caching, optimization
- **ML Prediction**: `src/prediction/` - Energy prediction models, weather ranking
- **Weather Integration**: `src/weather_api/` - API clients, weather simulation
- **GUI Application**: `main.py` - Tkinter interface, chart generation
- **Configuration**: `config/settings.py` - Application settings and installation mappings
- **Testing**: `tests/` - Unit, integration, and performance tests
- **Documentation**: Multiple MD files with comprehensive project documentation

### Data Context
- **PV Installations**: 9 Portuguese solar installations (315K+ records)
- **Time Period**: 2019-2022 historical data
- **Analysis Windows**: 15-day periods with weather simulation
- **ML Models**: Random Forest, Gradient Boosting, Linear Regression
- **Output**: Energy production predictions with 5-tier ranking system

## Advanced Features

### MCP Servers (Future Enhancement)
```bash
# List available MCP servers
warp mcp list

# Use MCP server with agent
warp agent run --mcp-server <server-uuid> --prompt "your task"
```

### GUI Integration
```bash
# Run agent with GUI feedback
warp agent run --gui --profile <profile-id> --prompt "your task"
```

### Output Formatting
```bash
# JSON output for automation
warp agent run --output-format json --profile <profile-id> --prompt "your task"
```

## Troubleshooting

### Common Issues
1. **Permission Denied**: Ensure the profile allows the required directories and commands
2. **Command Not Found**: Verify the agent profile includes necessary command permissions
3. **File Access Errors**: Check that the working directory is included in allowed directories

### Debug Mode
```bash
warp agent run --debug --profile <profile-id> --prompt "your task"
```

## Security Considerations

### Best Practices
- Use dedicated profiles for different projects
- Limit allowed directories to project-specific paths
- Regularly review and update allowed commands
- Monitor agent actions in sensitive environments

### FilantropiaSolar Specific
- The agent has access to solar energy data (public dataset)
- No sensitive personal or financial data in the project
- Safe to allow full read/write access within project directory

## Integration with Development Workflow

### Pre-commit Hooks
The agent can help maintain code quality by working with existing pre-commit hooks:
- Code formatting with Black and Ruff
- Import sorting with isort
- Security scanning with Bandit

### CI/CD Pipeline
Agent can assist with GitHub Actions workflows:
- Running tests and generating reports
- Building and pushing Docker images
- Updating documentation and releases

---

**Note**: Remember to create the agent profile through the Warp GUI and update this document with the actual profile ID once created.