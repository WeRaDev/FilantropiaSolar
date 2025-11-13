# FilantropiaSolar Windows Installer Build Script
# Builds PyInstaller exe and NSIS installer with version injection from pyproject.toml
#
# Usage:
#   .\windows_installer\make_installer.ps1
#
# Prerequisites:
#   - Python 3.11+ with project dependencies installed
#   - PyInstaller 5.0+ (pip install pyinstaller)
#   - NSIS 3.08+ installed and in PATH

param(
    [string]$VenvPath = "venv",
    [switch]$SkipPyInstaller = $false,
    [switch]$Help = $false
)

if ($Help) {
    Write-Host @"
FilantropiaSolar Windows Installer Build Script

Usage:
    .\windows_installer\make_installer.ps1 [options]

Options:
    -VenvPath <path>      Path to Python virtual environment (default: venv)
    -SkipPyInstaller      Skip PyInstaller build (use existing dist/)
    -Help                 Show this help message

Examples:
    .\windows_installer\make_installer.ps1
    .\windows_installer\make_installer.ps1 -VenvPath .venv
    .\windows_installer\make_installer.ps1 -SkipPyInstaller

Prerequisites:
    - Python 3.11+ with project dependencies
    - PyInstaller 5.0+ (pip install pyinstaller)
    - NSIS 3.08+ in PATH
"@
    exit 0
}

$ErrorActionPreference = "Stop"

# ASCII art banner
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  FilantropiaSolar Installer Builder" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "[INFO] Project root: $ProjectRoot" -ForegroundColor Green
Write-Host "[INFO] Script directory: $ScriptDir" -ForegroundColor Green
Write-Host ""

# Change to project root
Push-Location $ProjectRoot

try {
    # Step 1: Check prerequisites
    Write-Host "[1/7] Checking prerequisites..." -ForegroundColor Yellow
    
    # Check NSIS
    $nsisPath = Get-Command makensis -ErrorAction SilentlyContinue
    if (-not $nsisPath) {
        Write-Host "[ERROR] NSIS not found in PATH" -ForegroundColor Red
        Write-Host "        Please install NSIS from: https://nsis.sourceforge.io/" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ NSIS found: $($nsisPath.Source)" -ForegroundColor Green
    
    # Check Python
    $pythonCmd = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
    $pythonPath = Get-Command $pythonCmd -ErrorAction SilentlyContinue
    if (-not $pythonPath) {
        Write-Host "[ERROR] Python not found" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ Python found: $($pythonPath.Source)" -ForegroundColor Green
    
    # Check venv if needed
    if (-not $SkipPyInstaller) {
        $venvPython = Join-Path $VenvPath "Scripts\python.exe"
        if (Test-Path $venvPython) {
            Write-Host "  ✓ Virtual environment found: $VenvPath" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ Virtual environment not found at $VenvPath" -ForegroundColor Yellow
            Write-Host "    Will use system Python" -ForegroundColor Yellow
        }
    }
    
    Write-Host ""
    
    # Step 2: Extract version from pyproject.toml
    Write-Host "[2/7] Extracting version from pyproject.toml..." -ForegroundColor Yellow
    
    $versionScript = Join-Path $ProjectRoot "scripts\extract_version.py"
    if (-not (Test-Path $versionScript)) {
        Write-Host "[ERROR] Version extraction script not found: $versionScript" -ForegroundColor Red
        exit 1
    }
    
    $version = & $pythonCmd $versionScript
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to extract version from pyproject.toml" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "  ✓ Version: $version" -ForegroundColor Green
    Write-Host ""
    
    # Step 3: Clean old build artifacts
    Write-Host "[3/7] Cleaning old build artifacts..." -ForegroundColor Yellow
    
    if (-not $SkipPyInstaller) {
        $dirsToClean = @("build", "dist")
        foreach ($dir in $dirsToClean) {
            $fullPath = Join-Path $ProjectRoot $dir
            if (Test-Path $fullPath) {
                Write-Host "  Removing $dir/" -ForegroundColor Gray
                Remove-Item -Path $fullPath -Recurse -Force
            }
        }
    }
    
    $oldInstaller = Join-Path $ScriptDir "FilantropiaSolar-setup-*.exe"
    if (Test-Path $oldInstaller) {
        Write-Host "  Removing old installer" -ForegroundColor Gray
        Remove-Item -Path $oldInstaller -Force
    }
    
    Write-Host "  ✓ Cleanup complete" -ForegroundColor Green
    Write-Host ""
    
    # Step 4: Run PyInstaller
    if (-not $SkipPyInstaller) {
        Write-Host "[4/7] Building PyInstaller executable..." -ForegroundColor Yellow
        
        $specFile = Join-Path $ProjectRoot "filantropia_solar.spec"
        if (-not (Test-Path $specFile)) {
            Write-Host "[ERROR] PyInstaller spec file not found: $specFile" -ForegroundColor Red
            exit 1
        }
        
        # Use venv python if available, otherwise system python
        $buildPython = if (Test-Path $venvPython) { $venvPython } else { $pythonCmd }
        
        Write-Host "  Running: pyinstaller --clean --noconfirm filantropia_solar.spec" -ForegroundColor Gray
        & $buildPython -m PyInstaller --clean --noconfirm $specFile
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] PyInstaller build failed" -ForegroundColor Red
            exit 1
        }
        
        Write-Host "  ✓ PyInstaller build complete" -ForegroundColor Green
    } else {
        Write-Host "[4/7] Skipping PyInstaller build" -ForegroundColor Yellow
    }
    Write-Host ""
    
    # Step 5: Verify PyInstaller output
    Write-Host "[5/7] Verifying PyInstaller output..." -ForegroundColor Yellow
    
    $distDir = Join-Path $ProjectRoot "dist\FilantropiaSolar"
    $exePath = Join-Path $distDir "FilantropiaSolar.exe"
    
    if (-not (Test-Path $exePath)) {
        Write-Host "[ERROR] PyInstaller executable not found: $exePath" -ForegroundColor Red
        Write-Host "        Expected: dist\FilantropiaSolar\FilantropiaSolar.exe" -ForegroundColor Red
        Write-Host "        Please run PyInstaller first or check for build errors" -ForegroundColor Red
        exit 1
    }
    
    $exeSize = (Get-Item $exePath).Length / 1MB
    Write-Host "  ✓ Executable found: FilantropiaSolar.exe ($([math]::Round($exeSize, 1)) MB)" -ForegroundColor Green
    
    # Check for _internal directory
    $internalDir = Join-Path $distDir "_internal"
    if (Test-Path $internalDir) {
        Write-Host "  ✓ Dependencies found: _internal/" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ _internal directory not found (may be one-file build)" -ForegroundColor Yellow
    }
    
    Write-Host ""
    
    # Step 6: Check for icon
    Write-Host "[6/7] Checking installer resources..." -ForegroundColor Yellow
    
    $iconPath = Join-Path $ScriptDir "resources\icon.ico"
    if (Test-Path $iconPath) {
        Write-Host "  ✓ Icon found: resources\icon.ico" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Icon not found: resources\icon.ico (will use default)" -ForegroundColor Yellow
    }
    
    Write-Host ""
    
    # Step 7: Build NSIS installer
    Write-Host "[7/7] Building NSIS installer..." -ForegroundColor Yellow
    
    $nsisScript = Join-Path $ScriptDir "installer_v2.nsi"
    if (-not (Test-Path $nsisScript)) {
        Write-Host "[ERROR] NSIS script not found: $nsisScript" -ForegroundColor Red
        exit 1
    }
    
    # Build makensis command with defines
    $distDirRelative = "dist\FilantropiaSolar"
    $makeNsisArgs = @(
        "/DPRODUCT_VERSION=$version",
        "/DPRODUCT_NAME=FilantropiaSolar",
        "/DCOMPANY_NAME=WeRaDev Team",
        "/DDIST_DIR=..\$distDirRelative",
        $nsisScript
    )
    
    Write-Host "  Running: makensis $($makeNsisArgs -join ' ')" -ForegroundColor Gray
    
    Push-Location $ScriptDir
    & makensis $makeNsisArgs
    $nsisExitCode = $LASTEXITCODE
    Pop-Location
    
    if ($nsisExitCode -ne 0) {
        Write-Host "[ERROR] NSIS build failed with exit code $nsisExitCode" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "  ✓ NSIS build complete" -ForegroundColor Green
    Write-Host ""
    
    # Step 8: Verify installer
    $installerPath = Join-Path $ScriptDir "FilantropiaSolar-setup-$version-x64.exe"
    if (-not (Test-Path $installerPath)) {
        Write-Host "[ERROR] Installer not created: $installerPath" -ForegroundColor Red
        exit 1
    }
    
    $installerSize = (Get-Item $installerPath).Length / 1MB
    
    # Success banner
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  BUILD SUCCESSFUL!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Installer: " -NoNewline
    Write-Host "$installerPath" -ForegroundColor Cyan
    Write-Host "Size:      " -NoNewline
    Write-Host "$([math]::Round($installerSize, 1)) MB" -ForegroundColor Cyan
    Write-Host "Version:   " -NoNewline
    Write-Host "$version" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Test the installer on a clean Windows 10/11 system"
    Write-Host "  2. Verify all shortcuts work correctly"
    Write-Host "  3. Test upgrade from previous version"
    Write-Host "  4. Check data/weather_files preservation on uninstall"
    Write-Host ""
    Write-Host "To enable logging during install:" -ForegroundColor Yellow
    Write-Host "  FilantropiaSolar-setup-$version-x64.exe /LOG=install.log"
    Write-Host ""
    
} finally {
    Pop-Location
}
