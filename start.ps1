$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$scriptPath = $MyInvocation.MyCommand.Path
if ([string]::IsNullOrEmpty($scriptPath)) {
    if ($PSScriptRoot) {
        $root = $PSScriptRoot
    }
    else {
        $root = (Get-Location).ProviderPath
    }
}
else {
    $root = Split-Path -Parent $scriptPath
}
$exeName = "BiliCollectionDownloader.exe"
$exePath = Join-Path $root $exeName
$embeddedPython = Join-Path $root "python\python.exe"
$appScript = Join-Path $root "app.py"
$webScript = Join-Path $root "run_web.py"
$exitCode = 0

function Show-MainMenu {
    Write-Host ""
    Write-Host "================================"
    Write-Host "  BiliCollectionDownloader"
    Write-Host "================================"
    Write-Host "[1] 启动 App 版本（桌面版）"
    Write-Host "[2] 启动 Web 版本（本地服务）"
    Write-Host "[Q] 退出"
    Write-Host ""
}

while ($true) {
    Show-MainMenu
    $mode = Read-Host "请选择启动模式"

    if ($mode -eq "1") {
        if (Test-Path $exePath) {
            & $exePath
            $exitCode = $LASTEXITCODE
            break
        }

        if (Test-Path $embeddedPython) {
            & $embeddedPython $appScript
            $exitCode = $LASTEXITCODE
            break
        }

        Write-Host "未找到 $exeName 或嵌入式 Python 环境。"
        $exitCode = 1
        break
    }

    if ($mode -eq "2") {
        if (Test-Path $embeddedPython) {
            & $embeddedPython $webScript
            $exitCode = $LASTEXITCODE
            break
        }

        $systemPython = Get-Command python -ErrorAction SilentlyContinue
        if (-not $systemPython) {
            Write-Host "未找到可用的系统 Python 解释器。"
            $exitCode = 1
            break
        }

        & $systemPython.Path $webScript
        $exitCode = $LASTEXITCODE
        break
    }

    if ($mode -ieq "Q") {
        $exitCode = 0
        break
    }

    Write-Host "输入无效，请重试。"
}

exit $exitCode
