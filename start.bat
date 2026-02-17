@echo off
setlocal

set "ROOT=%~dp0"
set "CHROME_BROWSER_PATH=%ROOT%chrome-win64\chrome.exe"
set "CHROME_DRIVER_PATH=%ROOT%chromedriver.exe"

if not exist "%CHROME_BROWSER_PATH%" (
  echo [ERROR] Chrome not found: %CHROME_BROWSER_PATH%
  echo Please place chrome-win64\chrome.exe in project root.
  pause
  exit /b 1
)

if not exist "%CHROME_DRIVER_PATH%" (
  echo [ERROR] ChromeDriver not found: %CHROME_DRIVER_PATH%
  echo Please place chromedriver.exe in project root.
  pause
  exit /b 1
)

if exist "%ROOT%.venv\Scripts\python.exe" (
  "%ROOT%.venv\Scripts\python.exe" "%ROOT%main.py"
) else (
  python "%ROOT%main.py"
)

endlocal
