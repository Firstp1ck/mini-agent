; NSIS 3+ Unicode installer for mini-agent (PyInstaller one-file exe).
Unicode true
RequestExecutionLevel user
SetCompressor /SOLID lzma

!ifndef VERSION
  !define VERSION "dev"
!endif

!define PRODUCT_NAME "mini-agent"
!define CLI_COMMAND "mini-agent-cli.cmd"

Name "${PRODUCT_NAME} ${VERSION}"
OutFile "dist\windows-nsis\mini-agent-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\${PRODUCT_NAME}"
InstallDirRegKey HKCU "Software\${PRODUCT_NAME}" "InstallDir"

Section "Application" SEC_APP
  SetOutPath "$INSTDIR"
  File "dist\windows-nsis\mini-agent.exe"
  File "dist\windows-nsis\mini-agent-cli.exe"

  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\mini-agent.exe" "" "$INSTDIR\mini-agent.exe" 0

  CreateDirectory "$LOCALAPPDATA\Microsoft\WindowsApps"
  FileOpen $0 "$LOCALAPPDATA\Microsoft\WindowsApps\${CLI_COMMAND}" w
  FileWrite $0 '@echo off$\r$\n'
  FileWrite $0 '"$INSTDIR\mini-agent-cli.exe" %*$\r$\n'
  FileClose $0

  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\${PRODUCT_NAME}" "InstallDir" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  Delete "$LOCALAPPDATA\Microsoft\WindowsApps\${CLI_COMMAND}"
  Delete "$INSTDIR\mini-agent.exe"
  Delete "$INSTDIR\mini-agent-cli.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
  DeleteRegKey HKCU "Software\${PRODUCT_NAME}"
SectionEnd
