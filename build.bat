@echo off
chcp 65001 >nul
echo ========================================
echo  BilibiliCollectionsDownloader 打包工具
echo ========================================
echo.
echo 选择打包方式:
echo   1. 便携版 (Python 3.13.3 嵌入式)
echo   2. EXE 版 (PyInstaller 单文件)
echo   3. 两种都打包
echo.
set /p choice="请输入选择 (1/2/3): "

if "%choice%"=="1" goto portable
if "%choice%"=="2" goto exe
if "%choice%"=="3" goto both
echo 无效的选择！
pause
exit /b 1

:portable
echo.
echo 开始构建便携版...
powershell -ExecutionPolicy Bypass -File "%~dp0build\package_portable.ps1"
goto end

:exe
echo.
echo 开始构建 EXE 版...
powershell -ExecutionPolicy Bypass -File "%~dp0build\package_exe.ps1"
goto end

:both
echo.
echo 开始构建便携版...
powershell -ExecutionPolicy Bypass -File "%~dp0build\package_portable.ps1"
echo.
echo 开始构建 EXE 版...
powershell -ExecutionPolicy Bypass -File "%~dp0build\package_exe.ps1"
goto end

:end
echo.
echo ========================================
echo 打包完成！请查看 dist 目录
echo ========================================
pause
