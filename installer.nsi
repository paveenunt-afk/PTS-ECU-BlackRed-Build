Unicode True
!include "MUI2.nsh"
Name "PTS ECU Tuning Suite Black/Red v10"
OutFile "PTS_ECU_BlackRed_v10_Setup.exe"
InstallDir "$PROGRAMFILES64\PTS ECU Tuning Suite"
RequestExecutionLevel admin
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"
Section "Install"
  SetOutPath "$INSTDIR"
  File "dist\PTS_ECU_BlackRed_v10.exe"
  CreateShortcut "$DESKTOP\PTS ECU BlackRed.lnk" "$INSTDIR\PTS_ECU_BlackRed_v10.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd
Section "Uninstall"
  Delete "$DESKTOP\PTS ECU BlackRed.lnk"
  Delete "$INSTDIR\PTS_ECU_BlackRed_v10.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
