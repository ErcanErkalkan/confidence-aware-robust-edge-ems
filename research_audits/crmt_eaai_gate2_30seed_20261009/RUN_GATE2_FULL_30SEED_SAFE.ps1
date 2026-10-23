# Windows PowerShell 5.1+; refuses work without full data/source preflight.
param(
 [Parameter(Mandatory=$true)][string]$RepoRoot,
 [Parameter(Mandatory=$true)][string]$StageRoot,
 [Parameter(Mandatory=$true)][string]$RawRoot,
 [Parameter(Mandatory=$true)][string]$VerificationCsv,
 [Parameter(Mandatory=$true)][string]$BlockLockJson,
 [Parameter(Mandatory=$true)][string]$OutputRoot,
 [switch]$ExecuteAll,
 [string]$Python='python'
)
$ErrorActionPreference='Stop'
$Package=Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path -LiteralPath $OutputRoot) {throw "Output path exists, cannot overwrite: $OutputRoot"}
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$Report=Join-Path $OutputRoot 'GATE2_PREFLIGHT_30SEED.json'
$argsPre=@((Join-Path $Package 'tools\preflight_30seeds.py'),
 '--recovery-root',$Package,
 '--gate2-root',$StageRoot,
 '--repo-root',$RepoRoot,
 '--raw-root',$RawRoot,
 '--verification-csv',$VerificationCsv,
 '--block-lock-json',$BlockLockJson,
 '--report-json',$Report)
& $Python @argsPre
if ($LASTEXITCODE -ne 0) {throw 'Preflight BLOCKED. No real replay was started; read report.'}
if (-not $ExecuteAll) {
 Write-Host 'Preflight PASS. No replay ran. Add -ExecuteAll for 30 seeds (354000 controller-blocks).'
 return
}
$env:PYTHONPATH=(Join-Path $RepoRoot 'src')+';'+(Join-Path $RepoRoot 'tools')+';'+(Join-Path $Package 'cache_code\src')
foreach ($seed in (1001..1030)) {
 $dest=Join-Path $OutputRoot "seed$seed"
 if (Test-Path -LiteralPath $dest) {throw "Output exists, refusing overwrite: $dest"}
 & $Python (Join-Path $Package 'tools\p0_gate2_run_30seeds.py') `
   --seed $seed `
   --raw-root $RawRoot `
   --verification-csv $VerificationCsv `
   --block-lock-json $BlockLockJson `
   --shortlist-root (Join-Path $StageRoot 'outputs\locked_30seed\shortlists') `
   --output-dir $dest
 if ($LASTEXITCODE -ne 0) {throw "seed=$seed replay failed. Prior completed evidence kept."}
}
Write-Host 'Completed 30-seed exploratory VAL replay. Independent TEST is NOT included.'
