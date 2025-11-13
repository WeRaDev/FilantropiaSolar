#!/usr/bin/env python3
"""
Extract version string from pyproject.toml for use in build scripts.

Usage:
    python scripts/extract_version.py
    
Output:
    1.2.2  (or current version as plain text)
"""

import sys
from pathlib import Path

def extract_version():
    """Extract version from pyproject.toml."""
    # Find pyproject.toml
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    pyproject_path = project_root / "pyproject.toml"
    
    if not pyproject_path.exists():
        print(f"ERROR: pyproject.toml not found at {pyproject_path}", file=sys.stderr)
        sys.exit(1)
    
    # Read and parse version
    try:
        content = pyproject_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("version"):
                # Handle formats: version = "1.2.2" or version="1.2.2"
                if "=" in line:
                    version_part = line.split("=", 1)[1].strip()
                    # Remove quotes
                    version = version_part.strip('"').strip("'")
                    # Normalize to X.Y.Z format (remove any -rc, -beta, etc.)
                    version = version.split("-")[0].split("+")[0]
                    print(version)
                    return 0
        
        print("ERROR: version field not found in pyproject.toml", file=sys.stderr)
        sys.exit(1)
        
    except Exception as e:
        print(f"ERROR: Failed to read pyproject.toml: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    sys.exit(extract_version() or 0)
