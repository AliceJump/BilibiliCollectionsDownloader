$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $root "dist"
$pkgName = "BilibiliCollectionsDownloader"
$buildDir = Join-Path $root "build_temp"
$pkgDir = Join-Path $distRoot "${pkgName}-EXE"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "构建 EXE 版本（PyInstaller）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Clean
if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force }
if (Test-Path $pkgDir) { Remove-Item $pkgDir -Recurse -Force }
New-Item -ItemType Directory -Path $buildDir | Out-Null
New-Item -ItemType Directory -Path $pkgDir | Out-Null

# 1) Install PyInstaller
Write-Host "`n[1/4] 安装 PyInstaller..." -ForegroundColor Green
python -m pip install --upgrade pip
pip install pyinstaller

# 2) Build EXE
Write-Host "[2/4] 构建 EXE..." -ForegroundColor Green
pyinstaller `
  --name $pkgName `
  --onefile `
  --console `
  --clean `
  --distpath $buildDir `
  --workpath (Join-Path $buildDir "work") `
  --specpath $buildDir `
  --hidden-import=config `
  --hidden-import=logger `
  --hidden-import=parser `
  --hidden-import=downloader `
  (Join-Path $root "main.py")

Copy-Item (Join-Path $buildDir "$pkgName.exe") $pkgDir -Force

# 3) Download Chrome + ChromeDriver
Write-Host "[3/4] 下载 Chrome + ChromeDriver..." -ForegroundColor Green
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

# 4) Copy README
Write-Host "[4/4] 复制文档..." -ForegroundColor Green
Copy-Item (Join-Path $root "README.md") $pkgDir -Force

# Create start.bat
$startBatContent = @'
@echo off
chcp 65001 >nul
"%~dp0BilibiliCollectionsDownloader.exe"
'@
Set-Content (Join-Path $pkgDir "start.bat") $startBatContent -Encoding UTF8

# 5) Zip
Write-Host "`n正在打包..." -ForegroundColor Green
$zipPath = Join-Path $distRoot "$pkgName-EXE-Windows.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $pkgDir "*") -DestinationPath $zipPath

# Cleanup
Remove-Item $buildDir -Recurse -Force

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "构建完成！" -ForegroundColor Green
Write-Host "EXE 版本位置: $zipPath" -ForegroundColor Yellow
Write-Host "解压后双击 start.bat 或 exe 即可使用" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
