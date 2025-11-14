# Windows Installer Build Instructions - FilantropiaSolar v1.2.3

## Prerequisites

### Required Software (Windows Only)
1. **Python 3.11+** with all project dependencies
2. **PyInstaller 5.0+**: `pip install pyinstaller`
3. **NSIS 3.08+**: Download from https://nsis.sourceforge.io/
   - Add NSIS to PATH: `C:\Program Files (x86)\NSIS`

### Verify Installation
```powershell
# Check PyInstaller
pyinstaller --version

# Check NSIS
makensis /VERSION
```

## Build Process

### Step 1: Build PyInstaller Executable

You have two PyInstaller spec options:

#### Option A: Using `windows_installer/main.spec` (Recommended)
```powershell
# From project root
pyinstaller --noconfirm windows_installer/main.spec
```
**Output**: `dist/FilantropiaSolar/main.exe`

#### Option B: Using `filantropia_solar.spec`
```powershell
# From project root
pyinstaller --noconfirm filantropia_solar.spec
```
**Output**: `dist/FilantropiaSolar/FilantropiaSolar.exe`

### Step 2: Verify PyInstaller Build

Check that the executable was created:
```powershell
dir dist\FilantropiaSolar\*.exe
```

You should see one of:
- `main.exe` (from windows_installer/main.spec)
- `FilantropiaSolar.exe` (from filantropia_solar.spec)

### Step 3: Build NSIS Installer

```powershell
# From project root
makensis windows_installer\installer.nsi
```

**Output**: `windows_installer/wininstaller.exe`

### Step 4: Test the Installer

1. Run `windows_installer\wininstaller.exe`
2. Follow installation wizard
3. Test the installed application

## Troubleshooting

### Error: "PyInstaller dist not found"

**Cause**: PyInstaller hasn't been run or output is in wrong location

**Solution**:
```powershell
# Check current dist contents
dir dist

# If empty or only contains .whl/.tar.gz files, run PyInstaller:
pyinstaller --noconfirm windows_installer/main.spec

# Verify output
dir dist\FilantropiaSolar
```

### Error: "NSIS is not installed or not in PATH"

**Solution**:
1. Download NSIS from https://nsis.sourceforge.io/
2. Install to default location
3. Add to PATH manually or restart PowerShell
4. Verify: `makensis /VERSION`

### Error: Missing icon.ico or header.bmp

**Solution**: The NSIS script references optional graphics in `windows_installer/resources/`:
- `icon.ico` - Application icon (optional)
- `uninstall.ico` - Uninstaller icon (optional)
- `header.bmp` - Installer header 150x57px (optional)
- `wizard.bmp` - Welcome page 164x314px (optional)

These are optional; NSIS will use defaults if missing.

### PyInstaller Build Issues

**Problem**: Import errors or missing modules

**Solution**:
```powershell
# Ensure all dependencies installed
pip install -e .

# Clean build
rmdir /s /q build dist
pyinstaller --clean --noconfirm windows_installer/main.spec
```

**Problem**: Large executable size (>500MB)

**Solution**: Already optimized in spec files with:
- UPX compression enabled
- Unnecessary backends excluded
- Only required dependencies included

## Expected Results

### Build Artifacts
```
dist/
└── FilantropiaSolar/         # PyInstaller output (~150-200MB)
    ├── main.exe              # Main executable
    ├── _internal/            # Dependencies
    ├── data/                 # Application data
    └── weather_files/        # Weather data

windows_installer/
└── wininstaller.exe          # Final installer (~250-300MB compressed)
```

### Installation Size
- **Installer download**: ~250-300MB (LZMA compressed)
- **Installed size**: ~600MB (application + data)
- **After first run**: +385MB (cache directory)
- **Total disk usage**: ~985MB

### Performance
- **First launch**: 3-4 minutes (building cache)
- **Subsequent launches**: 5-10 seconds (from cache)
- **Installation time**: 2-3 minutes
- **Uninstall time**: 1-2 minutes

## Build Script Automation

For convenience, use the provided batch script:

```powershell
# From project root
.\windows_installer\build_installer.bat
```

This script:
1. Validates prerequisites (NSIS, PyInstaller dist)
2. Checks required files (LICENSE.txt, data/, weather_files/)
3. Creates resources directory if needed
4. Builds NSIS installer
5. Reports build status and file size

## Version Updates

When releasing a new version:

1. Update version in `windows_installer/installer.nsi`:
   ```nsis
   !define PRODUCT_VERSION "1.2.2"
   ```

2. Update version in spec files if using custom metadata

3. Rebuild both PyInstaller and NSIS:
   ```powershell
   pyinstaller --clean --noconfirm windows_installer/main.spec
   makensis windows_installer\installer.nsi
   ```

## CI/CD Integration

For automated builds, see `.github/workflows/` for GitHub Actions examples.

## Additional Resources

- [NSIS Documentation](https://nsis.sourceforge.io/Docs/)
- [PyInstaller Manual](https://pyinstaller.readthedocs.io/)
- [Project README](../README.md)
- [Deployment Guide](../DEPLOYMENT_GUIDE.md)

## Support

If you encounter build issues:
1. Check this guide's troubleshooting section
2. Verify all prerequisites are installed
3. Review build logs for specific error messages
4. Test on clean Windows 10/11 installation
