$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Day 2 - Building Blocks COMPLETE submission" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python is not available on PATH." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Ollama is not available on PATH." -ForegroundColor Red
    exit 1
}

$model = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "qwen2.5:7b" }
Write-Host "Model: $model"

try {
    Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 | Out-Null
}
catch {
    Write-Host "Starting Ollama server..."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized
    Start-Sleep -Seconds 5
}

Write-Host "[1/4] Ensuring model is installed..." -ForegroundColor Yellow
ollama pull $model
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[2/4] Running real Labs 2.2, 2.3 and 2.6..." -ForegroundColor Yellow
python tools\run_day2_evidence.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/4] Building the one-document submission..." -ForegroundColor Yellow
python tools\finalize_submission.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[4/4] Strict completeness verification..." -ForegroundColor Yellow
python tools\verify_completeness.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " PASS - DAY 2 COMPLETENESS READY" -ForegroundColor Green
Write-Host " Submit ONLY:" -ForegroundColor Green
Write-Host " submission\Day2-Building-Blocks-Lab-Submission-FINAL.md" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
