#!/bin/bash
# FilantropiaSolar Release Management Script
# Usage: ./scripts/release.sh [major|minor|patch] [--dry-run]

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PACKAGE_NAME="filantropia-solar"
VERSION_FILE="src/filantropia_solar/__init__.py"
PYPROJECT_FILE="pyproject.toml"

# Function to print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to get current version
get_current_version() {
    grep '__version__ = ' "$VERSION_FILE" | cut -d'"' -f2
}

# Function to increment version
increment_version() {
    local version=$1
    local type=$2
    
    IFS='.' read -ra VERSION_PARTS <<< "$version"
    local major=${VERSION_PARTS[0]}
    local minor=${VERSION_PARTS[1]}
    local patch=${VERSION_PARTS[2]}
    
    case $type in
        "major")
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        "minor")
            minor=$((minor + 1))
            patch=0
            ;;
        "patch")
            patch=$((patch + 1))
            ;;
        *)
            print_color $RED "Error: Invalid version type. Use major, minor, or patch."
            exit 1
            ;;
    esac
    
    echo "${major}.${minor}.${patch}"
}

# Function to update version in files
update_version() {
    local new_version=$1
    
    # Update __init__.py
    sed -i.bak "s/__version__ = \".*\"/__version__ = \"$new_version\"/" "$VERSION_FILE"
    
    # Update pyproject.toml
    sed -i.bak "s/version = \".*\"/version = \"$new_version\"/" "$PYPROJECT_FILE"
    
    # Remove backup files
    rm -f "${VERSION_FILE}.bak" "${PYPROJECT_FILE}.bak"
}

# Function to run pre-release checks
run_pre_release_checks() {
    print_color $BLUE "Running pre-release checks..."
    
    # Check if we're on main branch
    current_branch=$(git branch --show-current)
    if [ "$current_branch" != "main" ]; then
        print_color $YELLOW "Warning: You're not on the main branch (current: $current_branch)"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Check for uncommitted changes
    if [ -n "$(git status --porcelain)" ]; then
        print_color $RED "Error: There are uncommitted changes. Please commit or stash them first."
        git status --short
        exit 1
    fi
    
    # Pull latest changes
    print_color $BLUE "Pulling latest changes..."
    git pull origin main
    
    # Run tests
    print_color $BLUE "Running tests..."
    if command -v pytest &> /dev/null; then
        pytest tests/unit/ -v --tb=short
    else
        print_color $YELLOW "Warning: pytest not found. Skipping tests."
    fi
    
    # Check if package can be built
    print_color $BLUE "Testing package build..."
    if command -v python &> /dev/null; then
        python -m pip install --upgrade build twine --quiet
        python -m build --quiet
        twine check dist/* --strict
        rm -rf dist/ build/ *.egg-info
    fi
    
    print_color $GREEN "✅ All pre-release checks passed!"
}

# Function to create release
create_release() {
    local new_version=$1
    local dry_run=$2
    
    if [ "$dry_run" = true ]; then
        print_color $YELLOW "DRY RUN: Would create release v$new_version"
        print_color $YELLOW "DRY RUN: Would update files:"
        print_color $YELLOW "  - $VERSION_FILE"
        print_color $YELLOW "  - $PYPROJECT_FILE"
        print_color $YELLOW "DRY RUN: Would create git tag: v$new_version"
        return
    fi
    
    print_color $BLUE "Creating release v$new_version..."
    
    # Update version files
    update_version "$new_version"
    
    # Create commit
    git add "$VERSION_FILE" "$PYPROJECT_FILE"
    git commit -m "Release v$new_version"
    
    # Create and push tag
    git tag -a "v$new_version" -m "Release v$new_version"
    git push origin main
    git push origin "v$new_version"
    
    print_color $GREEN "✅ Release v$new_version created successfully!"
    print_color $BLUE "GitHub Actions will handle the rest:"
    print_color $BLUE "  - Create GitHub release"
    print_color $BLUE "  - Publish to PyPI"
    print_color $BLUE "  - Update documentation"
    print_color $BLUE ""
    print_color $BLUE "Monitor the progress at:"
    print_color $BLUE "  https://github.com/WeRaDev/FilantropiaSolar/actions"
}

# Main function
main() {
    local version_type=${1:-"patch"}
    local dry_run=false
    
    # Check for dry-run flag
    if [ "$2" = "--dry-run" ] || [ "$1" = "--dry-run" ]; then
        dry_run=true
        if [ "$1" = "--dry-run" ]; then
            version_type="patch"
        fi
    fi
    
    print_color $BLUE "🚀 FilantropiaSolar Release Manager"
    print_color $BLUE "=================================="
    
    # Get current version
    current_version=$(get_current_version)
    print_color $BLUE "Current version: $current_version"
    
    # Calculate new version
    new_version=$(increment_version "$current_version" "$version_type")
    print_color $BLUE "New version: $new_version ($version_type bump)"
    
    if [ "$dry_run" = false ]; then
        # Confirmation
        print_color $YELLOW "This will:"
        print_color $YELLOW "  1. Update version in source files"
        print_color $YELLOW "  2. Create a git commit and tag"
        print_color $YELLOW "  3. Push to GitHub (triggering automated release)"
        print_color $YELLOW ""
        read -p "Continue with release? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_color $YELLOW "Release cancelled."
            exit 0
        fi
        
        # Run checks
        run_pre_release_checks
    fi
    
    # Create release
    create_release "$new_version" "$dry_run"
}

# Help function
show_help() {
    echo "FilantropiaSolar Release Manager"
    echo ""
    echo "Usage: $0 [VERSION_TYPE] [--dry-run]"
    echo ""
    echo "VERSION_TYPE:"
    echo "  major    Increment major version (X.0.0)"
    echo "  minor    Increment minor version (X.Y.0)"
    echo "  patch    Increment patch version (X.Y.Z) [default]"
    echo ""
    echo "Options:"
    echo "  --dry-run    Show what would be done without making changes"
    echo "  --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 patch           # Release 1.0.0 -> 1.0.1"
    echo "  $0 minor           # Release 1.0.1 -> 1.1.0"
    echo "  $0 major           # Release 1.1.0 -> 2.0.0"
    echo "  $0 patch --dry-run # Preview patch release"
    echo ""
}

# Parse arguments
case ${1:-""} in
    -h|--help)
        show_help
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac