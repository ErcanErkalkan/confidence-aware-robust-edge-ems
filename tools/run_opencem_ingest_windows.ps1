param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot,
    [string]$Python = "python",
    [switch]$VerifyOnly,
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"

$Manifest = Join-Path $ProjectRoot "02_DATA\04_PROVENANCE\opencem_git_tree_manifest_v2.csv"
$RawRoot = Join-Path $ProjectRoot "02_DATA\01_RAW_EXTERNAL\OpenCEM"
$Checksums = Join-Path $ProjectRoot "02_DATA\05_CHECKSUMS"
$QaDir = Join-Path $ProjectRoot "02_DATA\06_QA"
$Tools = Join-Path $ProjectRoot "08_REPRODUCIBILITY\05_TOOLS"
$Downloader = Join-Path $Tools "opencem_ingest.py"
$QaScript = Join-Path $Tools "opencem_qa.py"
$VerificationCsv = Join-Path $Checksums "opencem_download_verification.csv"
$VerificationJson = Join-Path $Checksums "opencem_download_verification.json"
$QaJson = Join-Path $QaDir "opencem_real_data_qa.json"

foreach ($p in @($Manifest, $Downloader, $QaScript)) {
    if (-not (Test-Path $p)) { throw "Required file not found: $p" }
}
New-Item -ItemType Directory -Force -Path $RawRoot, $Checksums, $QaDir | Out-Null

$args = @(
    $Downloader,
    "--manifest", $Manifest,
    "--raw-root", $RawRoot,
    "--result-csv", $VerificationCsv,
    "--result-json", $VerificationJson
)
if ($VerifyOnly) { $args += "--verify-only" }
if ($Limit -gt 0) { $args += @("--limit", "$Limit") }

Write-Host "OpenCEM immutable ingest/verification starting..."
& $Python @args
if ($LASTEXITCODE -ne 0) { throw "OpenCEM ingest/verification failed with exit code $LASTEXITCODE" }

if ($Limit -eq 0) {
    Write-Host "All selected partitions verified. Running QA..."
    & $Python $QaScript `
        "--raw-root" $RawRoot `
        "--verification-csv" $VerificationCsv `
        "--output-json" $QaJson `
        "--expected-inverters" "1,2"
    if ($LASTEXITCODE -ne 0) { throw "OpenCEM QA failed with exit code $LASTEXITCODE" }
    Write-Host "QA report: $QaJson"
} else {
    Write-Host "Limit=$Limit smoke mode: QA skipped because the full partition set is not present."
}

Write-Host "Verification CSV: $VerificationCsv"
Write-Host "Verification JSON: $VerificationJson"
