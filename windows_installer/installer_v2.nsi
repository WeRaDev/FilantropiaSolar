; FilantropiaSolar v1.2.2 - NSIS Installer Script
; Professional Windows installer with system validation and data preservation
; Build with: makensis /DPRODUCT_VERSION=1.2.2 /DDIST_DIR=..\dist\FilantropiaSolar installer_v2.nsi

;--------------------------------
; Includes
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"

;--------------------------------
; Configuration
Unicode True
SetCompressor /SOLID lzma
RequestExecutionLevel admin
; SetRegView 64  ; configured in .onInit / un.onInit

;--------------------------------
; Defines (can be overridden via /D flags)
!ifndef PRODUCT_VERSION
  !define PRODUCT_VERSION "1.2.2"
!endif

!ifndef PRODUCT_NAME
  !define PRODUCT_NAME "FilantropiaSolar"
!endif

!ifndef COMPANY_NAME
  !define COMPANY_NAME "WeRaDev Team"
!endif

!ifndef DIST_DIR
  !define DIST_DIR "..\dist\FilantropiaSolar"
!endif

!define PRODUCT_WEB_SITE "https://github.com/WeRaDev/FilantropiaSolar"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\${PRODUCT_NAME}.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

; Version information for Windows
VIProductVersion "${PRODUCT_VERSION}.0"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "CompanyName" "${COMPANY_NAME}"
VIAddVersionKey "FileDescription" "${PRODUCT_NAME} Installer"
VIAddVersionKey "FileVersion" "${PRODUCT_VERSION}.0"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"
VIAddVersionKey "LegalCopyright" "© 2025 ${COMPANY_NAME}"

;--------------------------------
; Names and output
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "FilantropiaSolar-setup-${PRODUCT_VERSION}-x64.exe"
InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""

;--------------------------------
; Modern UI Configuration
!define MUI_ABORTWARNING
!define MUI_ICON "resources\icon.ico"
!define MUI_UNICON "resources\uninstall.ico"

; Welcome page
!define MUI_WELCOMEPAGE_TITLE "Welcome to ${PRODUCT_NAME} v${PRODUCT_VERSION} Setup"
!define MUI_WELCOMEPAGE_TEXT "${PRODUCT_NAME} is an advanced solar energy analysis application.$\r$\n$\r$\nThis wizard will guide you through the installation.$\r$\n$\r$\nClick Next to continue."

; License page
!define MUI_LICENSEPAGE_TEXT_TOP "Please review the license agreement."
!define MUI_LICENSEPAGE_TEXT_BOTTOM "If you accept the terms, click I Agree to continue."

; Directory page
!define MUI_DIRECTORYPAGE_TEXT_TOP "Setup will install ${PRODUCT_NAME} in the following folder."

; Finish page
!define MUI_FINISHPAGE_TITLE "Completing ${PRODUCT_NAME} Setup"
!define MUI_FINISHPAGE_TEXT "${PRODUCT_NAME} has been installed successfully.$\r$\n$\r$\nClick Finish to close the installer."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${PRODUCT_NAME}.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${PRODUCT_NAME}"

;--------------------------------
; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

;--------------------------------
; Languages
!insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Variables
Var SystemRAM
Var AvailableSpace

;--------------------------------
; Installer Functions
Function .onInit
  SetRegView 64
  ; Deny silent installation
  IfSilent 0 +3
    MessageBox MB_OK|MB_ICONSTOP "Silent installation is not supported.$\r$\nPlease run the installer interactively."
    Abort
  
  ; Check Windows version (require Win10+)
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_OK|MB_ICONSTOP "${PRODUCT_NAME} requires Windows 10 or later.$\r$\nYour system is not supported."
    Abort
  ${EndIf}
  
  ; Check 64-bit system
  ${IfNot} ${RunningX64}
    MessageBox MB_OK|MB_ICONSTOP "${PRODUCT_NAME} requires a 64-bit Windows system.$\r$\nYour system is not supported."
    Abort
  ${EndIf}
  
  ; Check RAM (warn if < 4GB)
  System::Call "kernel32::GlobalMemoryStatusEx(*l) i(4, .r0, .r1, .r2, .r3, .r4, .r5, .r6) .r7"
  IntOp $SystemRAM $4 / 1048576  ; Convert bytes to MB
  ${If} $SystemRAM < 4000
    MessageBox MB_YESNO|MB_ICONEXCLAMATION "${PRODUCT_NAME} recommends at least 4GB RAM for optimal performance.$\r$\nYour system has $SystemRAM MB RAM.$\r$\n$\r$\nContinue anyway?" IDYES ram_ok
    Abort
    ram_ok:
  ${EndIf}
  
  ; Check disk space (require 2GB free)
  ${GetRoot} "$INSTDIR" $0
  ${DriveSpace} "$0" "/D=F /S=M" $AvailableSpace
  ${If} $AvailableSpace < 2000
    MessageBox MB_OK|MB_ICONEXCLAMATION "${PRODUCT_NAME} requires at least 2GB free disk space.$\r$\nAvailable: $AvailableSpace MB$\r$\n$\r$\nPlease free up space and try again."
    Abort
  ${EndIf}
  
  ; Check for existing installation
  ReadRegStr $R0 ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString"
  ${If} $R0 != ""
    MessageBox MB_YESNO|MB_ICONEXCLAMATION "${PRODUCT_NAME} is already installed.$\r$\n$\r$\nUninstall the previous version before installing ${PRODUCT_VERSION}?$\r$\n(Note: data and weather_files folders will be preserved)" IDYES uninstall_old
    Goto done_check
    uninstall_old:
      ; Run uninstaller with _?=$INSTDIR to prevent auto-delete of directory
      ClearErrors
      ExecWait '$R0 _?=$INSTDIR'
      IfErrors uninstall_failed
      Goto done_check
      uninstall_failed:
        MessageBox MB_OK|MB_ICONEXCLAMATION "Failed to uninstall previous version.$\r$\nYou may need to uninstall manually."
    done_check:
  ${EndIf}
FunctionEnd

;--------------------------------
; Installation Section
Section "Core Application" SecCore
  SectionIn RO  ; Required section
  
  DetailPrint "Installing ${PRODUCT_NAME} v${PRODUCT_VERSION}..."
  
  ; Set output path
  SetOutPath "$INSTDIR"
  
  ; Install PyInstaller bundle
  DetailPrint "Copying application files..."
  File /r "${DIST_DIR}\*.*"
  
  ; Install data directories (nonfatal - may not exist during build)
  DetailPrint "Copying data files..."
  File /nonfatal /r "..\data"
  File /nonfatal /r "..\weather_files"
  
  ; Copy documentation
  File /nonfatal "..\README.md"
  File /nonfatal "..\CHANGELOG.md"
  File /nonfatal "..\LICENSE.txt"
  
  ; Validate critical directories
  ${If} ${FileExists} "$INSTDIR\data\*.*"
    DetailPrint "Data directory installed successfully"
  ${Else}
    DetailPrint "WARNING: data directory not found"
  ${EndIf}
  
  ${If} ${FileExists} "$INSTDIR\weather_files\*.*"
    DetailPrint "Weather files directory installed successfully"
  ${Else}
    DetailPrint "WARNING: weather_files directory not found"
  ${EndIf}
  
  ; Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  
  ; Register App Paths
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\${PRODUCT_NAME}.exe"
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "Path" "$INSTDIR"
  
  ; Write uninstall registry keys
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${COMPANY_NAME}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\${PRODUCT_NAME}.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "NoModify" 1
  WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "NoRepair" 1
  
  ; Calculate installed size
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "EstimatedSize" "$0"
  
  DetailPrint "Installation complete!"
SectionEnd

;--------------------------------
; Shortcuts Section
Section "Desktop & Start Menu Shortcuts" SecShortcuts
  SectionIn RO
  
  ; Create Start Menu folder
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_NAME}.exe" "" "$INSTDIR\${PRODUCT_NAME}.exe" 0
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  
  ; Create Desktop shortcut
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_NAME}.exe" "" "$INSTDIR\${PRODUCT_NAME}.exe" 0
  
  DetailPrint "Shortcuts created"
SectionEnd

;--------------------------------
; Post-installation Info
Section -Post
  ; Show data status if directories are missing
  ${IfNot} ${FileExists} "$INSTDIR\data\*.*"
  ${OrIfNot} ${FileExists} "$INSTDIR\weather_files\*.*"
    MessageBox MB_OK|MB_ICONINFORMATION "Installation complete!$\r$\n$\r$\nNote: Please ensure data and weather_files folders contain the required files for ${PRODUCT_NAME} to function properly.$\r$\n$\r$\nLocation: $INSTDIR"
  ${EndIf}
SectionEnd

;--------------------------------
; Uninstaller Functions
Function un.onInit
  SetRegView 64
  ; Deny silent uninstall
  IfSilent 0 +3
    MessageBox MB_OK|MB_ICONSTOP "Silent uninstall is not supported.$\r$\nPlease run the uninstaller interactively."
    Abort
  
  ; Confirm uninstall
  MessageBox MB_YESNO|MB_ICONQUESTION "Are you sure you want to remove ${PRODUCT_NAME}?$\r$\n$\r$\nNote: data and weather_files folders will be preserved." IDYES +2
  Abort
FunctionEnd

Function un.onUninstSuccess
  MessageBox MB_OK|MB_ICONINFORMATION "${PRODUCT_NAME} has been removed from your computer.$\r$\n$\r$\nYour data and weather_files folders have been preserved."
FunctionEnd

;--------------------------------
; Uninstaller Section
Section Uninstall
  ; Remove shortcuts
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
  
  ; Remove registry keys
  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
  
  ; Remove application files (preserve data and weather_files)
  Delete "$INSTDIR\${PRODUCT_NAME}.exe"
  Delete "$INSTDIR\Uninstall.exe"
  Delete "$INSTDIR\*.md"
  Delete "$INSTDIR\*.txt"
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\models"
  
  ; Preserve data and weather_files - do NOT delete
  DetailPrint "Preserving data and weather_files directories"
  
  ; Try to remove install dir (will only work if empty)
  RMDir "$INSTDIR"
  
  ${If} ${FileExists} "$INSTDIR\*.*"
    DetailPrint "Installation directory preserved (contains user data)"
  ${EndIf}
  
  SetAutoClose true
SectionEnd
