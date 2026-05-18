@echo off
setlocal
set ROOT=%~dp0

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
set /p APP_ARGS=请输入 App 启动参数（可留空）: 
if exist "%ROOT%BiliCollectionDownloader.exe" (
  "%ROOT%BiliCollectionDownloader.exe" %APP_ARGS%
  goto END
)
if exist "%ROOT%python\python.exe" (
  "%ROOT%python\python.exe" "%ROOT%app.py" %APP_ARGS%
  goto END
)
echo 未找到 BiliCollectionDownloader.exe 或嵌入式 Python 环境。
goto END

:WEB
set /p WEB_ARGS=请输入 Web 启动参数（可留空）: 
if exist "%ROOT%python\python.exe" (
  "%ROOT%python\python.exe" "%ROOT%run_web.py" %WEB_ARGS%
) else (
  python "%ROOT%run_web.py" %WEB_ARGS%
)
goto END

:END
endlocal
