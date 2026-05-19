$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exeName = "BiliCollectionDownloader.exe"
$exePath = Join-Path $root $exeName
$embeddedPython = Join-Path $root "python\python.exe"
$appScript = Join-Path $root "app.py"
$webScript = Join-Path $root "run_web.py"

function Show-MainMenu {
    Write-Host ""
    Write-Host "================================"
    Write-Host "  BilibiliCollectionsDownloader"
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
        while ($true) {
            Write-Host ""
            Write-Host "[1] 桌面窗口模式"
            Write-Host "[2] 命令行模式（--cli）"
            $appMode = Read-Host "请选择 App 参数"

            if ($appMode -eq "1" -or $appMode -eq "2") {
                break
            }

            Write-Host "输入无效，请重试。"
        }

        $cliArgs = @()
        if ($appMode -eq "2") {
            $cliArgs = @("--cli")
        }

        if (Test-Path $exePath) {
            & $exePath @cliArgs
            exit $LASTEXITCODE
        }

        if (Test-Path $embeddedPython) {
            & $embeddedPython $appScript @cliArgs
            exit $LASTEXITCODE
        }

        Write-Host "未找到 $exeName 或嵌入式 Python 环境。"
        exit 1
    }

    if ($mode -eq "2") {
        if (Test-Path $embeddedPython) {
            & $embeddedPython $webScript
            exit $LASTEXITCODE
        }

        $systemPython = Get-Command python -ErrorAction SilentlyContinue
        if (-not $systemPython) {
            Write-Host "未找到可用的 Python 解释器（嵌入式或系统 Python）。"
            exit 1
        }

        & $systemPython.Source $webScript
        exit $LASTEXITCODE
    }

    if ($mode -ieq "Q") {
        exit 0
    }

    Write-Host "输入无效，请重试。"
}
