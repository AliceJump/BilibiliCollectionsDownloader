$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$startBat = Join-Path $repoRoot "start.bat"

if (-not (Test-Path $startBat)) {
    throw "start.bat not found: $startBat"
}

function Invoke-LauncherCase {
    param(
        [string]$Name,
        [string]$InputText,
        [bool]$HasInput,
        [int]$ExpectedExitCode
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "cmd.exe"
    $psi.Arguments = "/d /s /c `"`"$startBat`"`""
    $psi.WorkingDirectory = $repoRoot
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi

    if (-not $process.Start()) {
        throw "$Name: failed to start launcher"
    }

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    if ($HasInput) {
        $process.StandardInput.WriteLine($InputText)
    }
    $process.StandardInput.Close()

    if (-not $process.WaitForExit(5000)) {
        cmd.exe /d /s /c "taskkill /PID $($process.Id) /T /F >nul 2>&1" | Out-Null
        throw "$Name: launcher did not exit within 5 seconds"
    }

    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result

    if ($process.ExitCode -ne $ExpectedExitCode) {
        throw "$Name: expected exit code $ExpectedExitCode, got $($process.ExitCode). stdout=$stdout stderr=$stderr"
    }

    if (($stdout.Length + $stderr.Length) -gt 65536) {
        throw "$Name: launcher produced unexpectedly large output"
    }

    Write-Host "PASS: $Name"
}

Invoke-LauncherCase -Name "redirected Q exits cleanly" -InputText "Q" -HasInput $true -ExpectedExitCode 0
Invoke-LauncherCase -Name "redirected invalid input exits" -InputText "invalid" -HasInput $true -ExpectedExitCode 1
Invoke-LauncherCase -Name "redirected EOF exits" -InputText "" -HasInput $false -ExpectedExitCode 1
