# Windows Installer for FilantropiaSolar

Professional NSIS-based Windows installer with system validation, data preservation, and automated build tooling.

## Quick Start (Windows)

```powershell
# Prerequisites: Python 3.11+, PyInstaller, NSIS 3.08+

# Build the installer (one command)
.\windows_installer\make_installer.ps1

# Output: windows_installer\\FilantropiaSolar-setup-1.2.3-x64.exe
```

## Build Requirements

### For Building (Developers)
- **Windows 10/11** (64-bit)
- **Python 3.11+** with project dependencies
- **PyInstaller 5.0+**: `pip install pyinstaller`
- **NSIS 3.08+**: https://nsis.sourceforge.io/
- **Git** for version control

### For End Users (Runtime)
- **Windows 10 1909+** or Windows 11 (64-bit only)
- **4GB RAM** recommended (warning below 4GB)
- **2GB disk space** free
- **Internet access** (outbound for weather API)
- **No other prerequisites** - PyInstaller bundles all dependencies

## Project Structure

```
windows_installer/
├── README.md                 # This file
├── BUILD_INSTRUCTIONS.md     # Detailed build guide (legacy)
├── installer_v2.nsi          # NSIS installer script (active)
├── installer.nsi             # Legacy installer (deprecated)
├── make_installer.ps1        # Automated build script
├── main.spec                 # PyInstaller spec (deprecated)
└── resources/
    ├── icon.ico              # Application icon (required)
    └── uninstall.ico         # Uninstaller icon (optional)
```

## Build Process

### Automated Build (Recommended)

```powershell
# From project root
.\windows_installer\make_installer.ps1

# With custom venv path
.\windows_installer\make_installer.ps1 -VenvPath .venv

# Skip PyInstaller if dist/ already exists
.\windows_installer\make_installer.ps1 -SkipPyInstaller

# Show help
.\windows_installer\make_installer.ps1 -Help
```

The script automates:
1. ✓ Prerequisites validation (NSIS, Python, PyInstaller)
2. ✓ Version extraction from `pyproject.toml`
3. ✓ Build artifacts cleanup
4. ✓ PyInstaller one-folder build (`dist/FilantropiaSolar/`)
5. ✓ NSIS installer compilation with version injection
6. ✓ Output verification and size reporting

### Manual Build

```powershell
# Step 1: Build PyInstaller executable
pyinstaller --clean --noconfirm filantropia_solar.spec

# Step 2: Verify output
dir dist\FilantropiaSolar\FilantropiaSolar.exe

# Step 3: Extract version
python scripts\extract_version.py

# Step 4: Build NSIS installer
cd windows_installer
makensis /DPRODUCT_VERSION=1.2.3 /DDIST_DIR=..\\dist\\FilantropiaSolar installer_v2.nsi
```

## Installer Features

### System Validation
- **OS Check**: Requires Windows 10 (build 1909+) or later
- **Architecture**: 64-bit only (32-bit blocked)
- **RAM Warning**: Alerts if <4GB available (allows continue)
- **Disk Space**: Requires 2GB free (hard block)
- **Silent Install Block**: Interactive installation enforced

### Installation
- **Location**: `C:\Program Files\FilantropiaSolar\`
- **Components**:
  - PyInstaller executable bundle (`FilantropiaSolar.exe`)
  - Application dependencies (`_internal/`, `models/`)
  - Data files (`data/`, `weather_files/`)
  - Documentation (`README.md`, `CHANGELOG.md`, `LICENSE.txt`)
- **Registry**:
  - App Paths registration (`Win+R` → `FilantropiaSolar.exe`)
  - Uninstall entry in Add/Remove Programs
  - No file associations or shell extensions

### Shortcuts
- **Desktop**: `FilantropiaSolar.lnk`
- **Start Menu**: `Start > FilantropiaSolar > FilantropiaSolar.lnk`
- **Start Menu**: `Start > FilantropiaSolar > Uninstall.lnk`
- **No Quick Launch** (deprecated on Windows 10+)

### Upgrade Behavior
- Detects existing installation via registry
- Prompts to uninstall previous version
- **Preserves** `data/` and `weather_files/` folders during upgrade
- Installs new version to same location

### Uninstall Behavior
- Removes application files and executables
- Removes shortcuts and registry keys
- **Preserves** `data/` and `weather_files/` folders
- User notified that data is preserved

## Installer Command-Line Options

```powershell
# Standard installation (GUI)
FilantropiaSolar-setup-1.2.3-x64.exe

# With installation logging
FilantropiaSolar-setup-1.2.2-x64.exe /LOG=C:\Temp\install.log

# Silent install (blocked - will show error and abort)
FilantropiaSolar-setup-1.2.2-x64.exe /S  # ❌ Not supported
```

## Version Management

Version is sourced from `pyproject.toml` automatically:

```toml
[project]
version = "1.2.3"
```

The build script extracts this using `scripts/extract_version.py` and injects it into:
- NSIS installer metadata (VIProductVersion, DisplayVersion)
- Installer filename (`FilantropiaSolar-setup-1.2.2-x64.exe`)
- Windows Properties dialog

## Troubleshooting

### Build Errors

**Error: NSIS not found**
```powershell
# Solution: Install NSIS and add to PATH
# Download: https://nsis.sourceforge.io/
# Add to PATH: C:\Program Files (x86)\NSIS
```

**Error: PyInstaller dist not found**
```powershell
# Solution: Run PyInstaller first
pyinstaller --clean --noconfirm filantropia_solar.spec

# Verify output
dir dist\FilantropiaSolar\FilantropiaSolar.exe
```

**Error: Icon not found**
```powershell
# Solution: Icon is optional but recommended
# Place icon at: windows_installer\resources\icon.ico
# Installer will use default Windows icon if missing
```

### Runtime Issues

**Installation fails with permission error**
- Run installer as Administrator
- Ensure target directory is writable

**App doesn't launch after installation**
- Check Windows Defender exclusions
- Verify `data/` and `weather_files/` folders exist
- Check logs in `%LOCALAPPDATA%\FilantropiaSolar\logs\`

**Upgrade doesn't preserve data**
- Verify you allowed uninstall of previous version
- Check `C:\Program Files\FilantropiaSolar\data\` manually

## Technical Details

### NSIS Script Configuration

```nsis
; Core settings
Unicode True
SetCompressor /SOLID lzma
RequestExecutionLevel admin
SetRegView 64

; Version (injected via /DPRODUCT_VERSION)
VIProductVersion "${PRODUCT_VERSION}.0"

; Directories
InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"

; Logging
LogSet on  ; Enables /LOG=path switch
```

### PyInstaller Spec

```python
# filantropia_solar.spec
name='FilantropiaSolar'
console=False  # Windowed app
upx=True       # Compression
datas=[
    ('data', 'data'),
    ('weather_files', 'weather_files'),
]
```

## QA Test Plan

Before release, verify on clean Windows 10/11:

**Fresh Install**
- [ ] OS and x64 checks work
- [ ] RAM/disk prompts appear correctly
- [ ] Installs to `C:\Program Files\FilantropiaSolar\`
- [ ] Desktop and Start Menu shortcuts created
- [ ] App launches from shortcuts
- [ ] `Win+R` → `FilantropiaSolar.exe` works
- [ ] Finish page launch option works

**Data Validation**
- [ ] `data/` folder exists with files
- [ ] `weather_files/` folder exists with files
- [ ] Warning appears if folders are empty

**Upgrade**
- [ ] Prompts to uninstall previous version
- [ ] Data folders preserved after upgrade
- [ ] New version functions correctly

**Uninstall**
- [ ] Application files removed
- [ ] `data/` and `weather_files/` preserved
- [ ] Shortcuts removed
- [ ] Registry keys cleaned
- [ ] Add/Remove Programs entry removed

## CI/CD Integration

For automated builds (future):

```yaml
# .github/workflows/build-windows-installer.yml
- name: Build Windows Installer
  run: |
    python -m pip install pyinstaller
    pyinstaller --clean --noconfirm filantropia_solar.spec
    .\windows_installer\make_installer.ps1
```

## Resources

- **NSIS Documentation**: https://nsis.sourceforge.io/Docs/
- **PyInstaller Manual**: https://pyinstaller.readthedocs.io/
- **Project Repository**: https://github.com/WeRaDev/FilantropiaSolar

## Support

For build issues:
1. Check this README
2. Review `make_installer.ps1` output
3. Check `BUILD_INSTRUCTIONS.md` for detailed steps
4. Verify all prerequisites installed
5. Test on clean Windows environment

---

**Note**: This installer is for FilantropiaSolar v1.2.2+. Legacy installers (`installer.nsi`, `main.spec`) are deprecated and should not be used for new builds.
