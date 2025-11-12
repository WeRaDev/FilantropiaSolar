; FilantropiaSolar v1.2.2 - NSIS Installer Script
; Creates professional Windows installer with modern UI

;--------------------------------
; Includes
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"

;--------------------------------
; General Configuration
Unicode True
!define PRODUCT_NAME "FilantropiaSolar"
!define PRODUCT_VERSION "1.2.2"
!define PRODUCT_DISPLAY_VERSION "1.2.2"
!define PRODUCT_PUBLISHER "WeRaDev Team"
!define PRODUCT_WEB_SITE "https://github.com/FilantropiaSolar"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\main.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"
!define ROOT_DIR "${__FILEDIR__}\\.."
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"

; Output file configuration
OutFile "wininstaller.exe"

; Installation directory
InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""

; Request application privileges
RequestExecutionLevel admin

; Show installation details
ShowInstDetails show
ShowUnInstDetails show

; Set compression
SetCompressor /SOLID lzma

; Application information
VIProductVersion "${PRODUCT_VERSION}.0"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "Comments" "Advanced Solar Energy Analysis Application"
VIAddVersionKey "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey "LegalTrademarks" ""
VIAddVersionKey "LegalCopyright" "© 2025 ${PRODUCT_PUBLISHER}"
VIAddVersionKey "FileDescription" "${PRODUCT_NAME} Installer"
VIAddVersionKey "FileVersion" "${PRODUCT_VERSION}.0"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"

;--------------------------------
; Modern UI Configuration
!define MUI_ABORTWARNING
!define MUI_ICON "${__FILEDIR__}\\resources\\icon.ico"
!define MUI_UNICON "${__FILEDIR__}\\resources\\uninstall.ico"
!define MUI_HEADERIMAGE

; Welcome page configuration
!define MUI_WELCOMEPAGE_TITLE "Welcome to ${PRODUCT_NAME} v${PRODUCT_VERSION} Setup"
!define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through the installation of ${PRODUCT_NAME}.$\r$\n$\r$\nFilantropiaSolar is an advanced solar energy analysis application with smart caching for lightning-fast performance.$\r$\n$\r$\nClick Next to continue."

; License page
!define MUI_LICENSEPAGE_TEXT_TOP "Please read the following license agreement carefully."
!define MUI_LICENSEPAGE_TEXT_BOTTOM "If you accept the terms of the agreement, click 'I Agree' to continue. You must accept the agreement to install ${PRODUCT_NAME}."

; Components page
!define MUI_COMPONENTSPAGE_TEXT_TOP "Select the components you wish to install and uncheck the components you do not want to install. Click Next to continue."

; Directory page
!define MUI_DIRECTORYPAGE_TEXT_TOP "Setup will install ${PRODUCT_NAME} in the following folder. To install in a different folder, click Browse and select another folder. Click Next to continue."

; Installation page
!define MUI_INSTFILESPAGE_PROGRESSBAR "colored"

; Finish page
!define MUI_FINISHPAGE_TITLE "Completing the ${PRODUCT_NAME} Setup Wizard"
!define MUI_FINISHPAGE_TEXT "${PRODUCT_NAME} has been installed on your computer.$\r$\n$\r$\nClick Finish to close this wizard."
!define MUI_FINISHPAGE_RUN "$INSTDIR\bin\main.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Start ${PRODUCT_NAME}"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.txt"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "View README file"

; Uninstaller finish page
!define MUI_UNFINISHPAGE_TEXT "${PRODUCT_NAME} has been uninstalled from your computer.$\r$\n$\r$\nClick Finish to close this wizard."

;--------------------------------
; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${ROOT_DIR}\\LICENSE.txt"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

;--------------------------------
; Languages
!insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Version Information
Var IsWin10OrLater
Var SystemRAM
Var AvailableSpace

;--------------------------------
; Installation Types
InstType "Full Installation"
InstType "Compact Installation"

;--------------------------------
; Sections
Section "!Core Application" SecCore
  SectionIn 1 2 RO
  
  DetailPrint "Installing core application files..."
  
  ; Set output path to the installation directory
  SetOutPath "$INSTDIR"
  
  ; Create directories
  CreateDirectory "$INSTDIR\bin"
  CreateDirectory "$INSTDIR\data"
  CreateDirectory "$INSTDIR\weather_files"
  CreateDirectory "$INSTDIR\cache"
  CreateDirectory "$INSTDIR\logs"
  
  ; Copy main application files
  SetOutPath "$INSTDIR\\bin"
  File /r "${ROOT_DIR}\\dist\\FilantropiaSolar\\*.*"
  
  ; Copy data files
  SetOutPath "$INSTDIR\\data"
  File /r "${ROOT_DIR}\\data\\*.*"
  
  ; Copy weather files
  SetOutPath "$INSTDIR\\weather_files"
  File /r "${ROOT_DIR}\\weather_files\\*.*"
  
  ; Copy documentation
  SetOutPath "$INSTDIR"
  File "${ROOT_DIR}\\README.md"
  File "${ROOT_DIR}\\CHANGELOG.md"
  File "${ROOT_DIR}\\LICENSE.txt"
  
  ; Create README.txt for Windows users
  FileOpen $0 "$INSTDIR\README.txt" w
  FileWrite $0 "FilantropiaSolar v${PRODUCT_VERSION}$\r$\n"
  FileWrite $0 "================================================$\r$\n$\r$\n"
  FileWrite $0 "Thank you for installing FilantropiaSolar!$\r$\n$\r$\n"
  FileWrite $0 "To start the application:$\r$\n"
  FileWrite $0 "1. Double-click the desktop shortcut, OR$\r$\n"
  FileWrite $0 "2. Use Start Menu -> FilantropiaSolar, OR$\r$\n"
  FileWrite $0 "3. Run: $INSTDIR\bin\main.exe$\r$\n$\r$\n"
  FileWrite $0 "First Run:$\r$\n"
  FileWrite $0 "- Initial startup takes 3-4 minutes (building cache)$\r$\n"
  FileWrite $0 "- Subsequent runs: 5-10 seconds (cached)$\r$\n$\r$\n"
  FileWrite $0 "For support and documentation:$\r$\n"
  FileWrite $0 "- Check CHANGELOG.md for version details$\r$\n"
  FileWrite $0 "- Visit: ${PRODUCT_WEB_SITE}$\r$\n"
  FileClose $0
SectionEnd

Section "Desktop Shortcut" SecDesktop
  SectionIn 1
  
  DetailPrint "Creating desktop shortcut..."
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\bin\main.exe" "" "$INSTDIR\bin\main.exe" 0 SW_SHOWNORMAL ALT|CONTROL|SHIFT|F5 "FilantropiaSolar - Advanced Solar Energy Analysis"
SectionEnd

Section "Start Menu Shortcuts" SecStartMenu
  SectionIn 1 2
  
  DetailPrint "Creating start menu shortcuts..."
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\bin\main.exe" "" "$INSTDIR\bin\main.exe" 0
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\README.lnk" "$INSTDIR\README.txt"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Quick Launch" SecQuickLaunch
  SectionIn 1
  
  DetailPrint "Creating quick launch shortcut..."
  CreateShortCut "$QUICKLAUNCH\${PRODUCT_NAME}.lnk" "$INSTDIR\bin\main.exe" "" "$INSTDIR\bin\main.exe" 0
SectionEnd

;--------------------------------
; Section Descriptions
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecCore} "Core application files and data (Required)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Create a desktop shortcut for easy access"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "Create Start Menu shortcuts and program group"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecQuickLaunch} "Create Quick Launch shortcut"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
; Installer Functions
Function .onInit
  ; Check Windows version
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP|MB_OK "FilantropiaSolar requires Windows 10 (version 1909) or later.$\r$\nYour system is not supported."
    Abort
  ${EndIf}
  
  ; Check if 64-bit system
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK "FilantropiaSolar requires a 64-bit Windows system.$\r$\nYour system is not supported."
    Abort
  ${EndIf}
  
  ; Check available RAM
  System::Call "kernel32::GlobalMemoryStatusEx(*l) i(4, .r0, .r1, .r2, .r3, .r4, .r5, .r6) .r7"
  IntOp $SystemRAM $4 / 1048576  ; Convert to MB
  ${If} $SystemRAM < 4000
    MessageBox MB_ICONEXCLAMATION|MB_YESNO "FilantropiaSolar recommends at least 4GB RAM for optimal performance.$\r$\nYour system has ${SystemRAM}MB RAM.$\r$\n$\r$\nContinue installation?" IDYES continue
    Abort
    continue:
  ${EndIf}
  
  ; Check available disk space
  ${GetRoot} "$INSTDIR" $0
  ${DriveSpace} "$0" "/D=F /S=M" $AvailableSpace
  ${If} $AvailableSpace < 2000
    MessageBox MB_ICONEXCLAMATION|MB_OK "FilantropiaSolar requires at least 2GB free disk space.$\r$\nAvailable space: ${AvailableSpace}MB$\r$\n$\r$\nPlease free up disk space and try again."
    Abort
  ${EndIf}
  
  ; Check if already installed
  ReadRegStr $R0 ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString"
  StrCmp $R0 "" done
  
  MessageBox MB_ICONEXCLAMATION|MB_YESNOCANCEL|MB_DEFBUTTON2 \
    "${PRODUCT_NAME} is already installed.$\r$\n$\r$\nDo you want to uninstall the previous version before installing v${PRODUCT_VERSION}?" \
    IDYES uninst IDNO done
  Abort
  
  uninst:
    ClearErrors
    ExecWait '$R0 /S _?=$INSTDIR'
    
    IfErrors no_remove_uninstaller done
    no_remove_uninstaller:
  
  done:
FunctionEnd

;--------------------------------
; Post-installation
Section -AdditionalIcons
  WriteIniStr "$INSTDIR\${PRODUCT_NAME}.url" "InternetShortcut" "URL" "${PRODUCT_WEB_SITE}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Website.lnk" "$INSTDIR\${PRODUCT_NAME}.url"
SectionEnd

Section -Post
  ; Write registry keys
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\bin\main.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_DISPLAY_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\bin\main.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "NoModify" 1
  WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "NoRepair" 1
  
  ; Calculate installed size
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "EstimatedSize" "$0"
SectionEnd

;--------------------------------
; Uninstaller
Function un.onUninstSuccess
  HideWindow
  MessageBox MB_ICONINFORMATION|MB_OK "$(^Name) was successfully removed from your computer."
FunctionEnd

Function un.onInit
  MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 "Are you sure you want to completely remove $(^Name) and all of its components?" IDYES +2
  Abort
FunctionEnd

Section Uninstall
  ; Remove registry keys
  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
  
  ; Remove files and uninstaller
  Delete "$INSTDIR\${PRODUCT_NAME}.url"
  Delete "$INSTDIR\Uninstall.exe"
  Delete "$INSTDIR\README.txt"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\\CHANGELOG.md"
  Delete "$INSTDIR\LICENSE.txt"
  
  ; Remove application files
  RMDir /r "$INSTDIR\bin"
  RMDir /r "$INSTDIR\data"
  RMDir /r "$INSTDIR\weather_files"
  
  ; Ask about cache and logs
  MessageBox MB_ICONQUESTION|MB_YESNO "Do you want to remove cache files and logs?$\r$\n(This will remove all cached data and application logs)" IDNO skip_cache
  RMDir /r "$INSTDIR\cache"
  RMDir /r "$INSTDIR\logs"
  skip_cache:
  
  ; Remove shortcuts
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  Delete "$QUICKLAUNCH\${PRODUCT_NAME}.lnk"
  
  ; Remove start menu
  RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
  
  ; Remove installation directory if empty
  RMDir "$INSTDIR"
  
  SetAutoClose true
SectionEnd
