[CmdletBinding()]
param(
    [string]$Distribution = 'Ubuntu-22.04',
    [switch]$Elevated
)

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskLogDir = Join-Path $taskRoot 'logs'
New-Item -ItemType Directory -Path $taskLogDir -Force | Out-Null
$taskLog = Join-Path $taskLogDir 'wsl-install.log'
$taskStatus = Join-Path $taskLogDir 'wsl-install-status.json'
$taskIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$taskPrincipal = [Security.Principal.WindowsPrincipal]::new($taskIdentity)

if (-not $taskPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    if ($Elevated) { throw 'Windows administrator rights are required to enable WSL2.' }
    $taskArguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $PSCommandPath), '-Distribution', ('"{0}"' -f $Distribution), '-Elevated')
    Write-Host 'Approve the Windows UAC dialog to install WSL2. No automatic reboot will occur.'
    $taskProcess = Start-Process -FilePath 'powershell.exe' -Verb RunAs -WindowStyle Hidden -ArgumentList $taskArguments -Wait -PassThru
    if (Test-Path -LiteralPath $taskStatus) { Get-Content -LiteralPath $taskStatus }
    exit $taskProcess.ExitCode
}

Start-Transcript -Path $taskLog -Append | Out-Null
try {
    $taskReboot = $false
    foreach ($taskFeature in @('Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform')) {
        $taskFeatureState = Get-WindowsOptionalFeature -Online -FeatureName $taskFeature
        if ($taskFeatureState.State -eq 'EnablePending') { $taskReboot = $true }
        elseif ($taskFeatureState.State -ne 'Enabled') {
            $taskFeatureResult = Enable-WindowsOptionalFeature -Online -FeatureName $taskFeature -All -NoRestart
            $taskReboot = $taskReboot -or $taskFeatureResult.RestartNeeded
        }
    }
    if ($taskReboot) {
        @{ status = 'restart_required'; distribution = $Distribution; message = 'Restart Windows, then run this script again.' } |
            ConvertTo-Json | Set-Content -LiteralPath $taskStatus -Encoding UTF8
        Write-Host 'Windows restart required. Save your work and restart, then run bootstrap_wsl.ps1 again.'
        exit 3010
    }
    & wsl.exe --install -d $Distribution --no-launch --web-download
    $taskInstallExit = $LASTEXITCODE
    if ($taskInstallExit -eq 3010) {
        @{ status = 'restart_required'; distribution = $Distribution } | ConvertTo-Json |
            Set-Content -LiteralPath $taskStatus -Encoding UTF8
        exit 3010
    }
    if ($taskInstallExit -ne 0) { throw "WSL installation failed (exit $taskInstallExit). See $taskLog." }
    & wsl.exe --set-default-version 2
    if ($LASTEXITCODE -ne 0) { throw 'Unable to set WSL2 as the default version.' }
    @{ status = 'installed'; distribution = $Distribution; message = 'Open Ubuntu once to create your Linux username/password.' } |
        ConvertTo-Json | Set-Content -LiteralPath $taskStatus -Encoding UTF8
}
catch {
    @{ status = 'failed'; distribution = $Distribution; message = $_.Exception.Message } |
        ConvertTo-Json | Set-Content -LiteralPath $taskStatus -Encoding UTF8
    throw
}
finally { Stop-Transcript | Out-Null }
