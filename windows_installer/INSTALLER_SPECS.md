# FilantropiaSolar v1.0.3 - Windows Installer Specifications

**Target**: Create `wininstaller.exe` for automated Windows 10+ installation

---

## 📋 **Installer Requirements**

### **Target Environment**
- **Windows Version**: Windows 10 (1909+) and Windows 11
- **Architecture**: x64 (64-bit)
- **RAM**: Minimum 4GB, Recommended 8GB+
- **Storage**: 2GB free space (includes cache)
- **Dependencies**: Bundled (no external requirements)

### **Installation Features**
- ✅ **One-click installation**: Complete automated setup
- ✅ **Standalone package**: All dependencies bundled
- ✅ **Desktop shortcut**: Easy application access
- ✅ **Start menu integration**: Professional Windows integration
- ✅ **Uninstaller**: Clean removal capability
- ✅ **Smart caching**: Optimized performance from first run

---

## 🏗️ **Build Architecture**

### **Step 1: PyInstaller Executable**
Create standalone Windows executable from Python source:
```
main.exe (standalone)
├── Python runtime embedded
├── Required libraries bundled
├── Data files included
└── Cache system ready
```

### **Step 2: NSIS Installer Package**
Professional installer wrapping the executable:
```
wininstaller.exe
├── Application files
├── Installation wizard
├── Registry entries
├── Shortcuts creation
└── Uninstaller generation
```

---

## 📦 **Package Structure**

### **Installation Directory** 
`C:\Program Files\FilantropiaSolar\`
```
FilantropiaSolar/
├── bin/
│   ├── main.exe                    # Main application
│   ├── python3*.dll               # Python runtime
│   └── _internal/                  # PyInstaller dependencies
├── data/                           # PV installation data
│   ├── PV Plants Metadata.xlsx
│   └── PV Plants Datasets.xlsx
├── weather_files/                  # Weather data
│   ├── Lisbon_weather.csv
│   ├── Setubal_weather.csv
│   └── [other weather files]
├── cache/                          # Smart cache directory (created on first run)
├── logs/                           # Application logs directory
├── LICENSE.txt                     # Software license
├── README.txt                      # Quick start guide
└── Uninstall.exe                   # Uninstaller
```

### **Registry Entries**
```
HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\FilantropiaSolar
├── DisplayName: "FilantropiaSolar v1.0.3"
├── DisplayVersion: "1.0.3"
├── Publisher: "FilantropiaSolar Team"
├── InstallLocation: "[INSTALLDIR]"
├── UninstallString: "[INSTALLDIR]\Uninstall.exe"
└── DisplayIcon: "[INSTALLDIR]\bin\icon.ico"
```

---

## 🎯 **Installation Process**

### **Installation Steps**
1. **Welcome Screen**: Application introduction
2. **License Agreement**: Software license acceptance
3. **Installation Directory**: Customizable install location
4. **Component Selection**: Full/Custom installation options
5. **Installation Progress**: Real-time progress indicator
6. **Desktop Shortcut**: Optional shortcut creation
7. **Completion**: Launch option and finish

### **Post-Installation**
- Desktop shortcut created (if selected)
- Start menu entry added
- Windows registry entries created
- Application ready for first run
- Smart cache system initialized on first launch

---

## ⚙️ **Build Tools Required**

### **Windows Build Environment**
```batch
# Required software:
- Python 3.11+ (with pip)
- PyInstaller (pip install pyinstaller)
- NSIS 3.08+ (Nullsoft Scriptable Install System)
- Visual Studio Redistributable 2019+ (for compatibility)
```

### **Python Dependencies**
All requirements from `requirements.txt` will be bundled:
- tkinter (GUI framework)
- pandas, numpy (data processing)
- scikit-learn (machine learning)
- matplotlib (charting)
- openpyxl (Excel file handling)
- And all smart caching dependencies

---

## 🔧 **Build Configuration**

### **PyInstaller Settings**
```python
# main.spec configuration
a = Analysis(['main.py'],
             pathex=['.'],
             binaries=[],
             datas=[('data', 'data'),
                    ('weather_files', 'weather_files'),
                    ('src', 'src')],
             hiddenimports=['sklearn.utils._cython_blas',
                           'sklearn.neighbors.typedefs',
                           'sklearn.neighbors.quad_tree',
                           'sklearn.tree._utils'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=None,
             noarchive=False)
```

### **NSIS Installer Settings**
```nsis
!define PRODUCT_NAME "FilantropiaSolar"
!define PRODUCT_VERSION "1.0.3"
!define PRODUCT_PUBLISHER "FilantropiaSolar Team"
!define PRODUCT_WEB_SITE "https://github.com/your-repo"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\main.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
```

---

## 📄 **Installer Features**

### **Professional Appearance**
- Custom application icon
- Professional installer UI
- Progress indicators
- Error handling and rollback
- Multilingual support ready

### **Smart Installation**
- Automatic dependency detection
- Windows version compatibility check
- Sufficient disk space validation
- Administrator privileges handling
- Clean installation on upgrade

### **User Experience**
- One-click installation for novice users
- Advanced options for power users
- Clear installation status messages
- Optional components selection
- Post-install launch capability

---

## 🔍 **Quality Assurance**

### **Testing Requirements**
- ✅ Windows 10 (multiple versions)
- ✅ Windows 11 compatibility
- ✅ Fresh system installation
- ✅ Upgrade from previous versions
- ✅ Uninstall verification
- ✅ Shortcut functionality
- ✅ Application launch test
- ✅ Cache system initialization

### **Validation Checklist**
- [ ] Installer creates all required directories
- [ ] All data files copied correctly
- [ ] Application launches without errors
- [ ] Smart caching system functional
- [ ] Desktop shortcut works
- [ ] Start menu entry created
- [ ] Uninstaller removes all components
- [ ] No registry orphans after uninstall

---

## 📊 **Size Estimates**

### **Component Sizes**
```
Estimated installer size breakdown:
- Python runtime + libraries:  ~150MB
- Application source code:     ~2MB
- PV installation data:        ~10MB
- Weather data files:          ~15MB
- Installer overhead:          ~5MB
- TOTAL INSTALLER SIZE:        ~180MB
```

### **Post-Installation**
```
Installed application footprint:
- Application files:           ~170MB
- Initial cache (empty):       ~1MB
- Logs directory:              ~1MB
- Full cache (after use):      ~400MB
- TOTAL DISK USAGE:           ~570MB (with cache)
```

---

## 🚀 **Deployment Strategy**

### **Distribution Options**
1. **GitHub Releases**: Primary distribution channel
2. **Direct Download**: From project website
3. **Microsoft Store**: Future consideration
4. **Enterprise Deployment**: MSI package option

### **Version Management**
- Automatic version detection
- Upgrade capability without uninstall
- Downgrade protection
- Settings preservation across updates

---

## 🛡️ **Security Considerations**

### **Code Signing** (Recommended)
```
# For production releases:
- Authenticode digital signature
- Trusted publisher certificate
- Windows SmartScreen compatibility
- Reduced security warnings
```

### **Installation Security**
- Administrator privileges only when required
- Secure default installation path
- No modifications to system files
- Clean uninstallation process

---

**Ready to build professional Windows installer for FilantropiaSolar v1.0.3!** 🏗️💻