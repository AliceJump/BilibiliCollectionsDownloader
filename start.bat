@echo off
setlocal
rem ASCII-only launcher. Switch the console to UTF-8 before PowerShell prints Chinese.
chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"
set "PS1_SCRIPT=%SCRIPT_DIR%start.ps1"

if not exist "%PS1_SCRIPT%" (
  echo start.ps1 not found: %PS1_SCRIPT%
  endlocal
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1_SCRIPT%"
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
