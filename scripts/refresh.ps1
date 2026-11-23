# Rebuild the report from live GitHub + local session data. See README.md.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONIOENCODING = 'utf-8'
$collect = @('scripts/collect.py') + $args
foreach ($step in @($collect, @('scripts/sessions.py'), @('scripts/aggregate.py'), @('scripts/build.py'), @('scripts/og.py'))) {
    python @step
    if ($LASTEXITCODE) { throw "python $step failed ($LASTEXITCODE)" }
}
