@echo off
setlocal
set ROOT=%~dp0
set EXE_NAME=BiliCollectionDownloader.exe
set EXE_PATH=%ROOT%%EXE_NAME%

:MENU
echo.
echo ================================
echo   BilibiliCollectionsDownloader
echo ================================
echo [1] 启动 App 版本（桌面版）
echo [2] 启动 Web 版本（本地服务）
echo [Q] 退出
echo.
set /p MODE=请选择启动模式: 

if /I "%MODE%"=="1" goto APP
if /I "%MODE%"=="2" goto WEB
if /I "%MODE%"=="Q" goto END

echo 输入无效，请重试。
goto MENU

:APP
echo.
echo [1] 桌面窗口模式
echo [2] 命令行模式（--cli）
set /p APP_MODE=请选择 App 参数: 

if exist "%EXE_PATH%" (
  if "%APP_MODE%"=="2" (
    "%EXE_PATH%" --cli
  ) else (
    "%EXE_PATH%"
  )
  goto END
)
if exist "%ROOT%python\python.exe" (
  if "%APP_MODE%"=="2" (
    "%ROOT%python\python.exe" "%ROOT%app.py" --cli
  ) else (
    "%ROOT%python\python.exe" "%ROOT%app.py"
  )
  goto END
)
echo 未找到 %EXE_NAME% 或嵌入式 Python 环境。
goto END

:WEB
if exist "%ROOT%python\python.exe" (
  "%ROOT%python\python.exe" "%ROOT%run_web.py"
) else (
  python "%ROOT%run_web.py"
)
goto END

:END
endlocal
