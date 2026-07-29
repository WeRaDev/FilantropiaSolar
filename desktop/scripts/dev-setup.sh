#!/bin/bash
# ===========================================
# FilantropiaSolar Development Setup Script
# ===========================================
# Automated setup for development environment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on macOS
check_macos() {
    if [[ "$OSTYPE" != "darwin"* ]]; then
        print_warning "This script is optimized for macOS. Some steps may need adjustment for other systems."
    fi
}

# Check Python version
check_python() {
    print_status "Checking Python installation..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3.11 or later."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
    REQUIRED_VERSION="3.11"
    
    if [[ $(echo -e "$PYTHON_VERSION\n$REQUIRED_VERSION" | sort -V | head -n1) != "$REQUIRED_VERSION" ]]; then
        print_error "Python $REQUIRED_VERSION or later is required. Found: $PYTHON_VERSION"
        print_status "On macOS, install with: brew install python@3.11"
        exit 1
    fi
    
    print_success "Python $PYTHON_VERSION is installed"
}

# Create and activate virtual environment
setup_venv() {
    print_status "Setting up virtual environment..."
    
    # Remove existing venv if it exists
    if [ -d "venv" ]; then
        print_warning "Removing existing virtual environment..."
        rm -rf venv
    fi
    
    # Create new virtual environment
    python3 -m venv venv
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    python -m pip install --upgrade pip setuptools wheel
    
    print_success "Virtual environment created and activated"
}

# Install dependencies
install_dependencies() {
    print_status "Installing dependencies..."
    
    # Ensure venv is activated
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        source venv/bin/activate
    fi
    
    # Install development dependencies
    pip install -r requirements-dev.txt
    
    # Install the package in development mode
    pip install -e .
    
    print_success "Dependencies installed"
}

# Setup pre-commit hooks
setup_pre_commit() {
    print_status "Setting up pre-commit hooks..."
    
    # Ensure venv is activated
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        source venv/bin/activate
    fi
    
    # Install pre-commit hooks
    pre-commit install --install-hooks
    pre-commit install --hook-type commit-msg
    
    print_success "Pre-commit hooks installed"
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p exports
    mkdir -p tests/fixtures
    mkdir -p docs/api
    mkdir -p monitoring
    mkdir -p nginx/conf.d
    mkdir -p scripts
    
    print_success "Directories created"
}

# Setup environment file
setup_env_file() {
    print_status "Setting up environment file..."
    
    if [ ! -f ".env" ]; then
        cp .env.template .env
        print_success "Created .env file from template"
        print_warning "Please update .env file with your specific configuration"
    else
        print_warning ".env file already exists, skipping..."
    fi
}

# Initialize git hooks (if git repo)
setup_git_hooks() {
    if [ -d ".git" ]; then
        print_status "Setting up additional git hooks..."
        
        # Create commit message template
        cat > .gitmessage << 'EOF'
# <type>(<scope>): <subject>
#
# <body>
#
# <footer>
#
# Type should be one of:
# - feat: A new feature
# - fix: A bug fix
# - docs: Documentation only changes
# - style: Changes that do not affect the meaning of the code
# - refactor: A code change that neither fixes a bug nor adds a feature
# - perf: A code change that improves performance
# - test: Adding missing tests or correcting existing tests
# - build: Changes that affect the build system or external dependencies
# - ci: Changes to our CI configuration files and scripts
# - chore: Other changes that don't modify src or test files
# - revert: Reverts a previous commit
EOF
        
        git config commit.template .gitmessage
        print_success "Git commit template configured"
    fi
}

# Run initial tests
run_initial_tests() {
    print_status "Running initial tests..."
    
    # Ensure venv is activated
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        source venv/bin/activate
    fi
    
    # Run code quality checks
    if command -v ruff &> /dev/null; then
        print_status "Running code quality checks..."
        ruff check --select=E9,F63,F7,F82 . || print_warning "Code quality issues found"
        ruff format --check . || print_warning "Code formatting issues found"
    fi
    
    # Run type checking
    if command -v mypy &> /dev/null; then
        print_status "Running type checking..."
        mypy --install-types --non-interactive src/ || print_warning "Type checking issues found"
    fi
    
    # Run basic tests if test directory exists
    if [ -d "tests" ] && [ "$(ls -A tests)" ]; then
        print_status "Running basic tests..."
        pytest tests/ -x -v || print_warning "Some tests failed"
    else
        print_warning "No tests found, skipping test execution"
    fi
    
    print_success "Initial tests completed"
}

# Create development scripts
create_dev_scripts() {
    print_status "Creating development scripts..."
    
    # Create run script
    cat > scripts/run.sh << 'EOF'
#!/bin/bash
# Quick run script for development
source venv/bin/activate
python -m filantropia_solar.cli "$@"
EOF
    
    # Create test script
    cat > scripts/test.sh << 'EOF'
#!/bin/bash
# Run tests with coverage
source venv/bin/activate
pytest tests/ -v --cov=src/filantropia_solar --cov-report=html --cov-report=term-missing "$@"
EOF
    
    # Create format script
    cat > scripts/format.sh << 'EOF'
#!/bin/bash
# Format code using ruff
source venv/bin/activate
ruff format .
ruff check --fix .
EOF
    
    # Create type check script
    cat > scripts/typecheck.sh << 'EOF'
#!/bin/bash
# Run type checking
source venv/bin/activate
mypy src/
EOF
    
    # Make scripts executable
    chmod +x scripts/*.sh
    
    print_success "Development scripts created in scripts/ directory"
}

# Print final instructions
print_final_instructions() {
    print_success "Development environment setup completed!"
    echo ""
    print_status "Next steps:"
    echo "  1. Activate virtual environment: source venv/bin/activate"
    echo "  2. Update .env file with your configuration"
    echo "  3. Run the application: python -m filantropia_solar.cli"
    echo "  4. Run tests: ./scripts/test.sh"
    echo "  5. Format code: ./scripts/format.sh"
    echo ""
    print_status "Available development commands:"
    echo "  - ./scripts/run.sh          # Run the application"
    echo "  - ./scripts/test.sh         # Run tests with coverage"
    echo "  - ./scripts/format.sh       # Format and lint code"
    echo "  - ./scripts/typecheck.sh    # Run type checking"
    echo ""
    print_status "Docker commands:"
    echo "  - docker-compose up -d      # Start all services"
    echo "  - docker-compose up --profile monitoring  # Start with monitoring"
    echo ""
    print_warning "Remember to:"
    echo "  - Update .env with real API keys and passwords"
    echo "  - Configure your IDE to use the virtual environment"
    echo "  - Review and customize pre-commit hooks if needed"
}

# Main execution
main() {
    echo "========================================"
    echo "FilantropiaSolar Development Setup"
    echo "========================================"
    echo ""
    
    check_macos
    check_python
    setup_venv
    install_dependencies
    setup_pre_commit
    create_directories
    setup_env_file
    setup_git_hooks
    create_dev_scripts
    run_initial_tests
    
    echo ""
    print_final_instructions
}

# Run main function
main "$@"