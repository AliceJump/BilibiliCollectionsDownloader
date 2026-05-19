@echo off
setlocal
set SCRIPT_DIR=%~dp0
set PS1_SCRIPT=%SCRIPT_DIR%start.ps1

if not exist "%PS1_SCRIPT%" (
  echo 未找到启动脚本：%PS1_SCRIPT%
  endlocal
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -Encoding UTF8 -Raw '%PS1_SCRIPT%' | Out-String | Invoke-Expression"
set EXIT_CODE=%errorlevel%
endlocal
exit /b %EXIT_CODE%
