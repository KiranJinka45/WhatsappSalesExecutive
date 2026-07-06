# Closely AI - Dev-Sec-Ops Quality Gate Runner
# Run this script from the backend/ directory to execute all quality checks.
# Usage: powershell -ExecutionPolicy Bypass -File quality_checks.ps1

$ErrorActionPreference = "Continue"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"

# Ensure evidence directories exist
$evidenceBase = "..\evidence\Sprint2"
New-Item -ItemType Directory -Force -Path "$evidenceBase\coverage" | Out-Null
New-Item -ItemType Directory -Force -Path "$evidenceBase\security" | Out-Null
New-Item -ItemType Directory -Force -Path "$evidenceBase\tests" | Out-Null

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Closely AI - Quality Gate Runner ($timestamp)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Gate 1: Unit & Integration Tests with Coverage ──────────────────────────
Write-Host "[1/4] Running pytest with coverage..." -ForegroundColor Yellow
& .\venv\Scripts\pytest --cov=app --cov-report=term-missing --cov-report=html:htmlcov tests/ 2>&1 | Tee-Object -FilePath "$evidenceBase\coverage\pytest_coverage_$timestamp.txt"
$testExitCode = $LASTEXITCODE

if ($testExitCode -eq 0) {
    Write-Host "  [PASS] All tests passed." -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Some tests failed (exit code: $testExitCode)." -ForegroundColor Red
}
Write-Host ""

# ── Gate 2: Static Type Analysis (mypy) ─────────────────────────────────────
Write-Host "[2/4] Running mypy static type analysis..." -ForegroundColor Yellow
& .\venv\Scripts\mypy app --ignore-missing-imports --no-error-summary 2>&1 | Tee-Object -FilePath "$evidenceBase\security\mypy_report_$timestamp.txt"
$mypyExitCode = $LASTEXITCODE

if ($mypyExitCode -eq 0) {
    Write-Host "  [PASS] No type errors found." -ForegroundColor Green
} else {
    Write-Host "  [WARN] Type issues detected (exit code: $mypyExitCode)." -ForegroundColor Yellow
}
Write-Host ""

# ── Gate 3: Security Linter (bandit) ────────────────────────────────────────
Write-Host "[3/4] Running bandit security linter..." -ForegroundColor Yellow
& .\venv\Scripts\bandit -r app -f txt --severity-level medium 2>&1 | Tee-Object -FilePath "$evidenceBase\security\bandit_report_$timestamp.txt"
$banditExitCode = $LASTEXITCODE

if ($banditExitCode -eq 0) {
    Write-Host "  [PASS] No security issues found." -ForegroundColor Green
} else {
    Write-Host "  [WARN] Security findings detected (exit code: $banditExitCode)." -ForegroundColor Yellow
}
Write-Host ""

# ── Gate 4: Code Style (ruff) ──────────────────────────────────────────────
Write-Host "[4/4] Running ruff linter..." -ForegroundColor Yellow
& .\venv\Scripts\ruff check app 2>&1 | Tee-Object -FilePath "$evidenceBase\security\ruff_report_$timestamp.txt"
$ruffExitCode = $LASTEXITCODE

if ($ruffExitCode -eq 0) {
    Write-Host "  [PASS] No lint issues found." -ForegroundColor Green
} else {
    Write-Host "  [WARN] Lint issues detected (exit code: $ruffExitCode)." -ForegroundColor Yellow
}
Write-Host ""

# ── Summary ─────────────────────────────────────────────────────────────────
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Quality Gate Summary" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$gates = @(
    @{Name="Tests + Coverage"; Code=$testExitCode},
    @{Name="mypy Type Check"; Code=$mypyExitCode},
    @{Name="bandit Security"; Code=$banditExitCode},
    @{Name="ruff Lint"; Code=$ruffExitCode}
)

$allPassed = $true
foreach ($gate in $gates) {
    $status = if ($gate.Code -eq 0) { "[PASS]" } else { "[FAIL]" }
    $color = if ($gate.Code -eq 0) { "Green" } else { "Red" }
    Write-Host "  $status $($gate.Name)" -ForegroundColor $color
    if ($gate.Code -ne 0) { $allPassed = $false }
}

Write-Host ""
if ($allPassed) {
    Write-Host "  All quality gates PASSED. Safe to commit." -ForegroundColor Green
} else {
    Write-Host "  Some quality gates FAILED. Review reports before committing." -ForegroundColor Red
}
Write-Host "  Evidence saved to: $evidenceBase\" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
