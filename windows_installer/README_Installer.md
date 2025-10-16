# FilantropiaSolar v1.0.3 - Windows Installer Build Guide

This directory contains all necessary files and scripts to create a professional Windows installer for FilantropiaSolar v1.0.3 Smart Caching Edition.

## 📋 Overview

The Windows installer provides:
- Professional installation wizard with modern UI
- System requirements validation (Windows 10+, 64-bit, 4GB RAM, 2GB disk space)
- Desktop and Start Menu shortcuts
- Registry integration for Windows Add/Remove Programs
- Uninstaller with cache preservation options
- LZMA compression for smaller download size

## 📁 Directory Structure

```
windows_installer/
├── installer.nsi           # NSIS installer script
├── FilantropiaSolar.spec   # PyInstaller specification
├── build_installer.bat     # Windows build script
├── README_Installer.md     # This documentation
├── requirements.txt        # Dependencies for building
└── resources/              # Installer assets (created during build)
    ├── icon.ico           # Application icon
    ├── uninstall.ico      # Uninstaller icon
    ├── header.bmp         # Installer header image
    └── wizard.bmp         # Welcome page image
```

## 🛠️ Prerequisites

### Required Software
1. **Python 3.9+** with all FilantropiaSolar dependencies installed
2. **PyInstaller** 5.0+
3. **NSIS (Nullsoft Scriptable Install System)** 3.08+
   - Download from: https://nsis.sourceforge.io/
   - Add NSIS to your PATH environment variable

### Required Files
- `LICENSE.txt` in project root
- `README.md` in project root  
- `CHANGELOG_v1.0.3.md` in project root
- All application source files and data directories

## 📦 Build Process

### Step 1: Prepare PyInstaller Build

First, ensure PyInstaller is installed:
```bash
pip install pyinstaller
```

Build the standalone executable:
```bash
# From the windows_installer directory
pyinstaller FilantropiaSolar.spec
```

This creates `dist/FilantropiaSolar/` with all bundled files.

### Step 2: Build Windows Installer

Run the build script:
```batch
# From windows_installer directory
build_installer.bat
```

The script will:
1. Validate all prerequisites and dependencies
2. Check for required files and directories
3. Create resources directory if needed
4. Build the NSIS installer
5. Report build status and installer size

### Step 3: Distribute

The final installer will be created as:
```
windows_installer/wininstaller.exe
```

## 🎯 Installer Features

### Installation Options
- **Full Installation**: All components including shortcuts
- **Compact Installation**: Core application with Start Menu shortcuts only

### Components
- **Core Application** (Required): Main executable and dependencies
- **Desktop Shortcut**: Desktop shortcut for easy access
- **Start Menu Shortcuts**: Program group with multiple shortcuts
- **Quick Launch**: Quick launch toolbar shortcut

### System Integration
- Registry entries for Add/Remove Programs
- File associations and application paths
- Proper version information and metadata
- Estimated installation size calculation

### Validation Checks
- Windows version compatibility (Windows 10+ required)
- System architecture (64-bit required)
- Available RAM (4GB recommended)
- Disk space requirements (2GB minimum)
- Existing installation detection with upgrade options

## 🔧 Customization

### Icons and Graphics
Place custom installer graphics in `resources/`:
- `icon.ico`: Application icon (32x32, 48x48, 256x256 recommended)
- `uninstall.ico`: Uninstaller icon
- `header.bmp`: Installer header (150x57 pixels)
- `wizard.bmp`: Welcome page image (164x314 pixels)

### Version Information
Update version details in `installer.nsi`:
```nsis
!define PRODUCT_VERSION "1.0.3"
!define PRODUCT_DISPLAY_VERSION "1.0.3 - Smart Caching Edition"
```

### Installation Directory
Default installation path can be modified:
```nsis
InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"
```

## 🧪 Testing

### Pre-Release Testing
1. Test installation on clean Windows 10/11 systems
2. Verify all shortcuts work correctly
3. Test uninstaller functionality
4. Confirm cache preservation option works
5. Validate Add/Remove Programs entries

### Installation Verification
- Check application launches correctly
- Verify cache initialization on first run
- Test cache loading performance
- Confirm all data files are accessible

## 📊 Expected Results

### Installation Size
- **Installer download**: ~250-300MB (compressed)
- **Installed application**: ~600MB (including data/models)
- **Cache directory**: ~385MB (after first run)
- **Total disk usage**: ~985MB

### Performance Metrics
- **First launch**: 3-4 minutes (cache building)
- **Subsequent launches**: 5-10 seconds (cached)
- **Installation time**: 2-3 minutes
- **Uninstall time**: 1-2 minutes

## 🚨 Troubleshooting

### Common Build Issues

**NSIS not found**
```
ERROR: NSIS is not installed or not in PATH
```
Solution: Install NSIS and add to PATH environment variable

**PyInstaller dist missing**
```
ERROR: PyInstaller distribution not found
```
Solution: Run `pyinstaller FilantropiaSolar.spec` first

**Missing LICENSE.txt**
```
ERROR: LICENSE.txt not found
```
Solution: Create LICENSE.txt file in project root

### Runtime Issues

**Installation fails with permission error**
- Run installer as Administrator
- Ensure target directory is writable

**Application doesn't launch after installation**
- Check Windows Defender/antivirus exclusions
- Verify all dependencies are bundled correctly

## 📝 Version History

### v1.0.3 - Smart Caching Edition
- Professional NSIS installer with modern UI
- System requirements validation
- Cache management integration
- Performance optimizations
- Registry integration for Windows

## 🔗 Additional Resources

- [NSIS Documentation](https://nsis.sourceforge.io/Docs/)
- [PyInstaller Manual](https://pyinstaller.readthedocs.io/)
- [Windows Installer Guidelines](https://docs.microsoft.com/en-us/windows/win32/msi/windows-installer-portal)

## 📞 Support

For build issues or questions:
1. Check this documentation
2. Review build logs for specific errors
3. Verify all prerequisites are installed
4. Test on a clean Windows environment

---

**Note**: This installer is designed for FilantropiaSolar v1.0.3 Smart Caching Edition. Ensure version numbers and file paths are updated for future releases.