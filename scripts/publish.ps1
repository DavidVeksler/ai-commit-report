# One command: refresh data, rebuild, sync into davidveksler.com, commit, deploy, verify live.
# Usage: scripts\publish.ps1 [-SkipFetch] [-NoDeploy]
# Deploying is the approval gate: run it only when David has said to publish.
param([switch]$SkipFetch, [switch]$NoDeploy)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$site = Join-Path (Split-Path $root -Parent) 'davidveksler.com'
Set-Location $root
if (git -C $site status --porcelain) { throw "davidveksler.com has uncommitted changes; commit or stash them first" }

$refresh = @()
if ($SkipFetch) { $refresh += '--skip-fetch' }
& "$PSScriptRoot\refresh.ps1" @refresh
if ($LASTEXITCODE) { throw "refresh failed" }
python scripts/sync_site.py
if ($LASTEXITCODE) { throw "sync failed" }

$asof = (Get-Content data/stats.json -Raw | ConvertFrom-Json)
git -C $site add public/commits
if (-not (git -C $site status --porcelain)) { Write-Host "Site already current ($($asof.asof)); nothing to deploy."; exit 0 }
git -C $site commit -q -m "Update /commits: counts through $($asof.asof), $('{0:N0}' -f $asof.total) commits`n`nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git -C $site push -q
# Keep the generator repo's data in git too.
git add data/stats.json
git diff --cached --quiet; if ($LASTEXITCODE) { git commit -q -m "Refresh through $($asof.asof): $('{0:N0}' -f $asof.total) commits`n`nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"; git push -q origin main }
if ($NoDeploy) { Write-Host "Committed; skipped deploy."; exit 0 }

Push-Location $site
npm run deploy:win -- -Yes
if ($LASTEXITCODE) { throw "deploy failed" }
Pop-Location
$live = (Invoke-WebRequest "https://davidveksler.com/commits/?v=$(Get-Random)" -UseBasicParsing).Content
if ($live -notmatch [regex]::Escape("`"asof`":`"$($asof.asof)`"")) { throw "live page does not show asof $($asof.asof)" }
Write-Host "Live: https://davidveksler.com/commits/ now shows $($asof.asof), $('{0:N0}' -f $asof.total) commits"
