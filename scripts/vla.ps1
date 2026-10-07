# Run the configured Linux environments from this Windows project directory.
$ErrorActionPreference = 'Stop'
$TaskRoot = Split-Path -Parent $PSScriptRoot
if ($args.Count -eq 0) {
    Write-Host 'Usage: powershell -ExecutionPolicy Bypass -File scripts/vla.ps1 doctor all --policy'
    exit 2
}
& wsl.exe --distribution Ubuntu-22.04 --user root --cd $TaskRoot --exec python3 scripts/vla.py @args
exit $LASTEXITCODE
