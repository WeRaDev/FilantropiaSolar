@echo off
:: FilantropiaSolar v1.0.3 - Build Windows Installer
:: This script builds the complete Windows installer package

echo ========================================
echo FilantropiaSolar v1.0.3 Installer Build
echo ========================================
echo.

:: Set paths
set PROJECT_ROOT=%~dp0..
set INSTALLER_DIR=%~dp0
set DIST_DIR=%PROJECT_ROOT%\dist
set RESOURCES_DIR=%INSTALLER_DIR%\resources

:: Check if NSIS is installed
echo Checking NSIS installation...
where makensis >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: NSIS is not installed or not in PATH
    echo Please install NSIS from: https://nsis.sourceforge.io/
    echo Add NSIS to your PATH environment variable
    pause
    exit /b 1
)
echo ✓ NSIS found

:: Check if PyInstaller dist exists
echo Checking PyInstaller distribution...
if not exist "%DIST_DIR%\FilantropiaSolar" (
    echo ERROR: PyInstaller distribution not found
    echo Expected: %DIST_DIR%\FilantropiaSolar
    echo Please run PyInstaller first: pyinstaller FilantropiaSolar.spec
    pause
    exit /b 1
)
echo ✓ PyInstaller dist found

:: Check required files
echo Checking required files...
if not exist "%PROJECT_ROOT%\README.md" (
    echo WARNING: README.md not found
)

if not exist "%PROJECT_ROOT%\CHANGELOG_v1.0.3.md" (
    echo WARNING: CHANGELOG_v1.0.3.md not found
)

if not exist "%PROJECT_ROOT%\LICENSE.txt" (
    echo ERROR: LICENSE.txt not found
    echo Please create a LICENSE.txt file in the project root
    pause
    exit /b 1
)

:: Create resources directory for installer assets
if not exist "%RESOURCES_DIR%" (
    echo Creating resources directory...
    mkdir "%RESOURCES_DIR%"
)

:: Copy or create installer icons if they don't exist
if not exist "%RESOURCES_DIR%\icon.ico" (
    echo Creating placeholder icon.ico...
    :: Note: In practice, you'd want to copy an actual .ico file
    echo. > "%RESOURCES_DIR%\icon.ico"
)

if not exist "%RESOURCES_DIR%\uninstall.ico" (
    echo Creating placeholder uninstall.ico...
    :: Note: In practice, you'd want to copy an actual .ico file  
    echo. > "%RESOURCES_DIR%\uninstall.ico"
)

:: Build the installer
echo.
echo Building Windows installer...
cd /d "%INSTALLER_DIR%"

makensis installer.nsi

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Installer build failed
    pause
    exit /b 1
)

:: Check if installer was created
if not exist "%INSTALLER_DIR%\wininstaller.exe" (
    echo.
    echo ERROR: Installer executable was not created
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS: Installer built successfully!
echo ========================================
echo.
echo Installer location: %INSTALLER_DIR%\wininstaller.exe
echo.

:: Get file size
for %%A in ("%INSTALLER_DIR%\wininstaller.exe") do (
    echo Installer size: %%~zA bytes
)

echo.
echo The installer includes:
echo - Core application and dependencies
echo - Data files and weather data
echo - Desktop and Start Menu shortcuts
echo - Professional uninstaller
echo - System requirements validation
echo - Registry integration
echo.
echo Ready for distribution!
echo.
pause