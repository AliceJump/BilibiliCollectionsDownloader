$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$startBat = Join-Path $repoRoot "start.bat"
$maxOutputBytes = 65536
$timeoutMs = 5000

if (-not (Test-Path $startBat)) {
    throw "start.bat not found: $startBat"
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)

    if ($Process -and -not $Process.HasExited) {
        cmd.exe /d /s /c "taskkill /PID $($Process.Id) /T /F >nul 2>&1" | Out-Null
        $Process.WaitForExit()
    }
}

function Get-FileLength {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) {
        return (Get-Item -LiteralPath $Path).Length
    }

    return 0
}

function Invoke-LauncherCase {
    param(
        [string]$Name,
        [string]$InputText,
        [bool]$HasInput,
        [int]$ExpectedExitCode
    )

    $caseDir = Join-Path ([System.IO.Path]::GetTempPath()) ("bcd-startup-test-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $caseDir | Out-Null

    $stdinPath = Join-Path $caseDir "stdin.txt"
    $stdoutPath = Join-Path $caseDir "stdout.txt"
    $stderrPath = Join-Path $caseDir "stderr.txt"
    $process = $null

    try {
        if ($HasInput) {
            [System.IO.File]::WriteAllText($stdinPath, $InputText + [Environment]::NewLine, [System.Text.Encoding]::ASCII)
        }
        else {
            [System.IO.File]::WriteAllBytes($stdinPath, [byte[]]@())
        }

        $arguments = "/d /s /c `"`"$startBat`"`""
        $process = Start-Process -FilePath "cmd.exe" -ArgumentList $arguments -WorkingDirectory $repoRoot -RedirectStandardInput $stdinPath -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -WindowStyle Hidden -PassThru

        if (-not $process) {
            throw "${Name}: failed to start launcher"
        }

        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

        while (-not $process.HasExited) {
            $outputBytes = (Get-FileLength $stdoutPath) + (Get-FileLength $stderrPath)

            if ($outputBytes -gt $maxOutputBytes) {
                Stop-ProcessTree $process
                throw "${Name}: launcher output exceeded $maxOutputBytes bytes"
            }

            if ($stopwatch.ElapsedMilliseconds -gt $timeoutMs) {
                Stop-ProcessTree $process
                throw "${Name}: launcher did not exit within 5 seconds"
            }

            Start-Sleep -Milliseconds 50
        }

        $stopwatch.Stop()
        $process.WaitForExit()

        $outputBytes = (Get-FileLength $stdoutPath) + (Get-FileLength $stderrPath)
        if ($outputBytes -gt $maxOutputBytes) {
            throw "${Name}: launcher output exceeded $maxOutputBytes bytes"
        }

        $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { "" }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { "" }

        if ($process.ExitCode -ne $ExpectedExitCode) {
            throw "${Name}: expected exit code $ExpectedExitCode, got $($process.ExitCode). stdout=$stdout stderr=$stderr"
        }

        Write-Host "PASS: $Name"
    }
    finally {
        if ($process) {
            Stop-ProcessTree $process
            $process.Dispose()
        }

        Remove-Item -LiteralPath $caseDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Invoke-LauncherCase -Name "redirected Q exits cleanly" -InputText "Q" -HasInput $true -ExpectedExitCode 0
Invoke-LauncherCase -Name "redirected invalid input exits" -InputText "invalid" -HasInput $true -ExpectedExitCode 1
Invoke-LauncherCase -Name "redirected EOF exits" -InputText "" -HasInput $false -ExpectedExitCode 1
