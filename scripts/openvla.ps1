# Isolated OpenVLA candidate; commands do not alter the existing models.
$ErrorActionPreference = 'Stop'
$TaskRoot = Split-Path -Parent $PSScriptRoot
if ($args.Count -eq 0) {
    Write-Host 'Usage: scripts/openvla.ps1 setup | download | readiness | screen | native-ramekin | native-pairs | native-neutral | question-context | fact-first | fact-first-na; rollout commands require --output, diagnostic commands also require source runs.'
    exit 2
}
$TaskCommand = $args[0]
$TaskRest = @($args | Select-Object -Skip 1)
switch ($TaskCommand) {
    'setup' {
        & wsl.exe --distribution Ubuntu-22.04 --user root --cd $TaskRoot --exec python3 scripts/setup_openvla_spatial_4bit.py @TaskRest
    }
    'download' {
        & wsl.exe --distribution Ubuntu-22.04 --user root --cd $TaskRoot --exec .venvs/openvla-spatial-4bit/bin/python scripts/download_openvla_spatial_4bit.py @TaskRest
    }
    { $_ -in 'readiness','screen' } {
        & wsl.exe --distribution Ubuntu-22.04 --user root --cd $TaskRoot --exec .venvs/openvla-spatial-4bit/bin/python scripts/check_openvla_spatial_4bit.py --mode $TaskCommand @TaskRest
    }
    'native-ramekin' {
        & wsl.exe --distribution Ubuntu-22.04 --user root --cd $TaskRoot --exec .venvs/openvla-spatial-4bit/bin/python scripts/check_openvla_native_ramekin.py @TaskRest
    }
    'native-pairs' {
        & wsl.exe --distribution Ubuntu-22.04 --user root --cd $TaskRoot --exec .venvs/openvla-spatial-4bit/bin/python scripts/check_openvla_native_pairs.py @TaskRest
    }
    'native-neutral' {
        & wsl.exe --distribution Ubuntu-22.04 --user root --cd $TaskRoot --exec .venvs/openvla-spatial-4bit/bin/python scripts/check_openvla_native_neutral.py @TaskRest
    }
    'question-context' {
        & wsl.exe --distribution Ubuntu-22.04 --user root --cd $TaskRoot --exec .venvs/openvla-spatial-4bit/bin/python scripts/check_openvla_question_context.py @TaskRest
    }
    'fact-first' {
        & wsl.exe --distribution Ubuntu-22.04 --user root --cd $TaskRoot --exec .venvs/openvla-spatial-4bit/bin/python scripts/check_openvla_fact_first.py @TaskRest
    }
    'fact-first-na' {
        & wsl.exe --distribution Ubuntu-22.04 --user root --cd $TaskRoot --exec .venvs/openvla-spatial-4bit/bin/python scripts/check_openvla_fact_first_na.py @TaskRest
    }
    default { throw "Unknown OpenVLA command: $TaskCommand" }
}
exit $LASTEXITCODE
