$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $root "dist"
$pkgName = "BilibiliCollectionsDownloader"
$buildDir = Join-Path $root "build_temp"
$pkgDir = Join-Path $distRoot $pkgName

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "构建单文件 EXE（Python 3.13.3）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Clean
if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force }
if (Test-Path $pkgDir) { Remove-Item $pkgDir -Recurse -Force }
New-Item -ItemType Directory -Path $buildDir, $pkgDir | Out-Null

# 1) Install PyInstaller and dependencies
Write-Host "`n[1/4] 安装 PyInstaller..." -ForegroundColor Green
python -m pip install --upgrade pip
pip install pyinstaller
pip install -r (Join-Path $root "requirements.txt")

# 2) Build single-file EXE
Write-Host "[2/4] 构建单文件 EXE..." -ForegroundColor Green
$appPath = Join-Path $root "app.py"
pyinstaller `
  --name $pkgName `
  --onefile `
  --console `
  --clean `
  --distpath $buildDir `
  --workpath (Join-Path $buildDir "work") `
  --specpath $buildDir `
  --hidden-import=cv2 `
  --hidden-import=selenium `
  --hidden-import=seleniumwire `
  --hidden-import=pyzbar `
  --hidden-import=requests `
  --collect-all=seleniumwire `
  $appPath

Copy-Item (Join-Path $buildDir "$pkgName.exe") $pkgDir -Force
Write-Host "EXE 构建完成：$pkgDir\$pkgName.exe" -ForegroundColor Green

# 3) Download Chrome + ChromeDriver
Write-Host "[3/4] 下载 Chrome + ChromeDriver..." -ForegroundColor Green
$versionsUrl = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
$versions = Invoke-RestMethod $versionsUrl

$chromeInfo = $versions.channels.Stable.downloads.chrome | Where-Object { $_.platform -eq "win64" } | Select-Object -First 1
$driverInfo = $versions.channels.Stable.downloads.chromedriver | Where-Object { $_.platform -eq "win64" } | Select-Object -First 1

Write-Host "Chrome 版本: $($chromeInfo.version)" -ForegroundColor Yellow
Write-Host "ChromeDriver 版本: $($driverInfo.version)" -ForegroundColor Yellow

$chromeZip = Join-Path $pkgDir "chrome.zip"
$driverZip = Join-Path $pkgDir "driver.zip"

Invoke-WebRequest $chromeInfo.url -OutFile $chromeZip
Invoke-WebRequest $driverInfo.url -OutFile $driverZip

Expand-Archive $chromeZip -DestinationPath $pkgDir -Force
Expand-Archive $driverZip -DestinationPath $pkgDir -Force

Remove-Item $chromeZip, $driverZip -Force

# Place files correctly
Copy-Item (Join-Path $pkgDir "chromedriver-win64\chromedriver.exe") (Join-Path $pkgDir "chromedriver.exe") -Force
Remove-Item (Join-Path $pkgDir "chromedriver-win64") -Recurse -Force

# 4) Create launch scripts
Write-Host "[4/4] 创建启动脚本..." -ForegroundColor Green

# Create start.bat
$startBatContent = @'
@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
set "CHROME_BROWSER_PATH=%ROOT%chrome-win64\chrome.exe"
set "CHROME_DRIVER_PATH=%ROOT%chromedriver.exe"

REM Check requirements
if not exist "%CHROME_BROWSER_PATH%" (
  echo [ERROR] Chrome not found at %CHROME_BROWSER_PATH%
  pause
  exit /b 1
)

if not exist "%CHROME_DRIVER_PATH%" (
  echo [ERROR] ChromeDriver not found at %CHROME_DRIVER_PATH%
  pause
  exit /b 1
)

cd /d "%ROOT%"
"%ROOT%BilibiliCollectionsDownloader.exe"

endlocal
'@
Set-Content (Join-Path $pkgDir "start.bat") $startBatContent -Encoding UTF8

# Create PowerShell launcher
$psLauncherContent = @'
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
$exe = Join-Path $ROOT "BilibiliCollectionsDownloader.exe"
& $exe
'@
Set-Content (Join-Path $pkgDir "start.ps1") $psLauncherContent -Encoding UTF8

# Create README
$readmeContent = @'
# BilibiliCollectionsDownloader - 便携版

## 使用说明

1. **准备输入**
   - 选项 A：在 `qrcodes` 文件夹放置收藏集分享二维码图片 (.jpg 或 .png)
   - 选项 B：编辑 `urls.txt`，每行一个收藏集分享链接

2. **运行程序**
   - Windows: 双击 `start.bat`
   - 或直接运行 `BilibiliCollectionsDownloader.exe`

3. **选择选项**
   - 输入方式：1（二维码）或 2（urls.txt）
   - 视频类型：1（无水印）/ 2（有水印）/ 12（两者）

4. **下载位置**
   - 视频和图片保存在 `dlc\<活动名>\` 目录下
   - 日志文件在 `logs\` 目录下

## 文件结构

```
BilibiliCollectionsDownloader.exe  # 主程序
start.bat                          # 启动脚本（推荐）
chrome-win64/                      # Chrome 浏览器
chromedriver.exe                   # Chrome 驱动
qrcodes/                           # 放置二维码图片
urls.txt                           # 链接列表
dlc/                               # 下载目录（自动创建）
logs/                              # 日志目录（自动创建）
```

## 系统需求

- Windows 10 或更高版本
- 管理员权限（首次启动时）

## 常见问题

Q: 提示找不到 Chrome？
A: 确保 `chrome-win64/chrome.exe` 和 `chromedriver.exe` 在正确位置

Q: 如何修改下载文件夹？
A: 用文本编辑器打开 `.exe` 所在目录，找不到可以修改源代码重新构建
'@
Set-Content (Join-Path $pkgDir "README.md") $readmeContent -Encoding UTF8

# 5) Create qrcodes and urls.txt placeholders
New-Item -ItemType Directory -Path (Join-Path $pkgDir "qrcodes") -Force | Out-Null
Set-Content (Join-Path $pkgDir "urls.txt") "# 在此输入 B 站收藏集分享链接，每行一个`n" -Encoding UTF8

# 6) Zip
Write-Host "`n正在打包..." -ForegroundColor Green
$zipPath = Join-Path $distRoot "$pkgName-Standalone-Windows.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $pkgDir "*") -DestinationPath $zipPath

# Cleanup
Remove-Item $buildDir -Recurse -Force

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "构建完成！" -ForegroundColor Green
Write-Host "位置: $zipPath" -ForegroundColor Yellow
Write-Host "大小: $([math]::Round((Get-Item $zipPath).Length / 1MB, 2)) MB" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
