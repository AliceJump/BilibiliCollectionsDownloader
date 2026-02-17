@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"

REM Check if exe version exists, run it if present
if exist "%ROOT%BilibiliCollectionsDownloader.exe" (
  "%ROOT%BilibiliCollectionsDownloader.exe"
  goto end
)

REM Otherwise use venv if available
if exist "%ROOT%.venv\Scripts\python.exe" (
  "%ROOT%.venv\Scripts\python.exe" "%ROOT%app.py"
  goto end
)

REM Or use system Python
python "%ROOT%app.py"

:end
endlocal
