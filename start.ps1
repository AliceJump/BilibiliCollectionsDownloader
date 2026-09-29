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
$embeddedPython = Join-Path $root "python\python.exe"
$appScript = Join-Path $root "app.py"
$webScript = Join-Path $root "run_web.py"
$exitCode = 0
$inputRedirected = [Console]::IsInputRedirected

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

function Read-StartupMode {
    if ($inputRedirected) {
        return [Console]::In.ReadLine()
    }
    return Read-Host "请选择启动模式"
}

while ($true) {
    Show-MainMenu

    try {
        $mode = Read-StartupMode
    }
    catch {
        Write-Host "无法读取启动模式，退出。"
        $exitCode = 1
        break
    }

    if ($null -eq $mode) {
        Write-Host "未读取到启动模式，退出。"
        $exitCode = 1
        break
    }

    $mode = $mode.Trim()

    if ($mode -eq "1") {
        if (Test-Path $embeddedPython) {
            & $embeddedPython $appScript
            $exitCode = $LASTEXITCODE
            break
        }

        $systemPython = Get-Command python -ErrorAction SilentlyContinue
        if ($systemPython) {
            & $systemPython.Path $appScript
            $exitCode = $LASTEXITCODE
            break
        }

        Write-Host "未找到嵌入式 Python 环境或可用的系统 Python 解释器。"
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

    if ($inputRedirected) {
        Write-Host "非交互输入无效，退出。"
        $exitCode = 1
        break
    }

    Write-Host "输入无效，请重试。"
}

exit $exitCode
