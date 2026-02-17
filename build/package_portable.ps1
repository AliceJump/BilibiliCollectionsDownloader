$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $root "dist"
$pkgName = "BilibiliCollectionsDownloader"
$pkgDir = Join-Path $distRoot $pkgName

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "构建便携版（Python 3.13.3 + Chrome）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Clean
if (Test-Path $pkgDir) { 
    Write-Host "清理旧版本..." -ForegroundColor Yellow
    Remove-Item $pkgDir -Recurse -Force 
}
New-Item -ItemType Directory -Path $pkgDir | Out-Null

# 1) Download Python 3.13.3 embeddable
Write-Host "`n[1/5] 下载 Python 3.13.3 便携版..." -ForegroundColor Green
$pythonUrl = "https://www.python.org/ftp/python/3.13.3/python-3.13.3-embed-amd64.zip"
$pythonZip = Join-Path $pkgDir "python.zip"
Invoke-WebRequest $pythonUrl -OutFile $pythonZip
Expand-Archive $pythonZip -DestinationPath (Join-Path $pkgDir "python") -Force
Remove-Item $pythonZip -Force

# 2) Configure Python to support pip and local imports
Write-Host "[2/5] 配置 Python 环境..." -ForegroundColor Green
$pythonDir = Join-Path $pkgDir "python"
$pthFile = Get-ChildItem -Path $pythonDir -Filter "*._pth" | Select-Object -First 1

if ($pthFile) {
    # Enable site-packages and add parent directory to path
    $pthContent = @"
python313.zip
.
..

# Uncomment to run site.main() automatically
import site
"@
    Set-Content $pthFile.FullName $pthContent
}

# Download get-pip.py
$getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$getPipPath = Join-Path $pythonDir "get-pip.py"
Invoke-WebRequest $getPipUrl -OutFile $getPipPath

# Install pip
& (Join-Path $pythonDir "python.exe") $getPipPath
Remove-Item $getPipPath -Force

# 3) Install dependencies
Write-Host "[3/5] 安装 Python 依赖..." -ForegroundColor Green
& (Join-Path $pythonDir "python.exe") -m pip install --upgrade pip
& (Join-Path $pythonDir "python.exe") -m pip install -r (Join-Path $root "requirements.txt")

# 4) Download Chrome for Testing + chromedriver
Write-Host "[4/5] 下载 Chrome + ChromeDriver..." -ForegroundColor Green
$versionsUrl = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
$versions = Invoke-RestMethod $versionsUrl

$chromeInfo = $versions.channels.Stable.downloads.chrome | Where-Object { $_.platform -eq "win64" } | Select-Object -First 1
$driverInfo = $versions.channels.Stable.downloads.chromedriver | Where-Object { $_.platform -eq "win64" } | Select-Object -First 1

$chromeZip = Join-Path $pkgDir "chrome.zip"
$driverZip = Join-Path $pkgDir "driver.zip"

Invoke-WebRequest $chromeInfo.url -OutFile $chromeZip
Invoke-WebRequest $driverInfo.url -OutFile $driverZip

Expand-Archive $chromeZip -DestinationPath $pkgDir -Force
Expand-Archive $driverZip -DestinationPath $pkgDir -Force

Remove-Item $chromeZip, $driverZip -Force

Copy-Item (Join-Path $pkgDir "chromedriver-win64\chromedriver.exe") (Join-Path $pkgDir "chromedriver.exe") -Force
Remove-Item (Join-Path $pkgDir "chromedriver-win64") -Recurse -Force

# 5) Copy project files
Write-Host "[5/5] 复制项目文件..." -ForegroundColor Green
Copy-Item (Join-Path $root "main.py") $pkgDir -Force
Copy-Item (Join-Path $root "config.py") $pkgDir -Force
Copy-Item (Join-Path $root "logger.py") $pkgDir -Force
Copy-Item (Join-Path $root "parser.py") $pkgDir -Force
Copy-Item (Join-Path $root "downloader.py") $pkgDir -Force
Copy-Item (Join-Path $root "README.md") $pkgDir -Force

# Create start.bat for portable version
$startBatContent = @'
@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
set "PYTHON_EXE=%ROOT%python\python.exe"
set "CHROME_BROWSER_PATH=%ROOT%chrome-win64\chrome.exe"
set "CHROME_DRIVER_PATH=%ROOT%chromedriver.exe"

REM Add current directory to PYTHONPATH so Python can find local modules
set "PYTHONPATH=%ROOT%"

if not exist "%PYTHON_EXE%" (
  echo [错误] Python 未找到: %PYTHON_EXE%
  pause
  exit /b 1
)

if not exist "%CHROME_BROWSER_PATH%" (
  echo [错误] Chrome 未找到: %CHROME_BROWSER_PATH%
  pause
  exit /b 1
)

if not exist "%CHROME_DRIVER_PATH%" (
  echo [错误] ChromeDriver 未找到: %CHROME_DRIVER_PATH%
  pause
  exit /b 1
)

cd /d "%ROOT%"
"%PYTHON_EXE%" "%ROOT%main.py"

endlocal
'@

Set-Content (Join-Path $pkgDir "start.bat") $startBatContent -Encoding UTF8

# 6) Create zip
Write-Host "`n正在打包..." -ForegroundColor Green
$zipPath = Join-Path $distRoot "$pkgName-Portable-Windows.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $pkgDir "*") -DestinationPath $zipPath

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "构建完成！" -ForegroundColor Green
Write-Host "便携版位置: $zipPath" -ForegroundColor Yellow
Write-Host "解压后运行 start.bat 即可使用" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
