$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $root "dist"
$pkgName = "BilibiliCollectionsDownloader"
$pkgDir = Join-Path $distRoot $pkgName

if (Test-Path $pkgDir) { Remove-Item $pkgDir -Recurse -Force }
New-Item -ItemType Directory -Path $pkgDir | Out-Null

# 1) Create venv and install deps
$venvPath = Join-Path $pkgDir ".venv"
python -m venv $venvPath
& "$venvPath\Scripts\python.exe" -m pip install --upgrade pip
& "$venvPath\Scripts\python.exe" -m pip install -r (Join-Path $root "requirements.txt")

# 2) Download Chrome for Testing + chromedriver (win64 stable)
$versionsUrl = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
$versions = Invoke-RestMethod $versionsUrl
$chromeInfo = $versions.channels.Stable.downloads.chrome | Where-Object { $_.platform -eq "win64" } | Select-Object -First 1
$driverInfo = $versions.channels.Stable.downloads.chromedriver | Where-Object { $_.platform -eq "win64" } | Select-Object -First 1

$chromeZip = Join-Path $pkgDir "chrome-win64.zip"
$driverZip = Join-Path $pkgDir "chromedriver-win64.zip"
Invoke-WebRequest $chromeInfo.url -OutFile $chromeZip
Invoke-WebRequest $driverInfo.url -OutFile $driverZip

Expand-Archive -Path $chromeZip -DestinationPath $pkgDir -Force
Expand-Archive -Path $driverZip -DestinationPath $pkgDir -Force
Remove-Item $chromeZip, $driverZip -Force

# 3) Place chromedriver.exe in root and keep chrome-win64 folder
Copy-Item (Join-Path $pkgDir "chromedriver-win64\chromedriver.exe") (Join-Path $pkgDir "chromedriver.exe") -Force
Remove-Item (Join-Path $pkgDir "chromedriver-win64") -Recurse -Force

# 4) Copy project files
Copy-Item (Join-Path $root "bilicollectiondownloader.py") $pkgDir -Force
Copy-Item (Join-Path $root "start.Qbat") $pkgDir -Force
Copy-Item (Join-Path $root "README.md") $pkgDir -Force
Copy-Item (Join-Path $root "requirements.txt") $pkgDir -Force

# 5) Zip package
$zipPath = Join-Path $distRoot "$pkgName-windows.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $pkgDir "*") -DestinationPath $zipPath

Write-Host "Package created: $zipPath"
