# Starts the SG Expenditure Tracker: backend (FastAPI) + frontend (Vite) dev
# servers, each in its own window, then opens the app in your browser.
#
# Run with:  powershell -ExecutionPolicy Bypass -File scripts/start.ps1
# (or just double-click scripts/start.bat)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent  # this script lives in scripts/, repo root is one level up
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

function Test-Port($port, $path = "/") {
    # Vite binds to localhost/::1, uvicorn binds to 127.0.0.1 - try both
    # rather than assuming, so "already running" detection actually works.
    foreach ($host_ in @("127.0.0.1", "localhost")) {
        try {
            $r = Invoke-WebRequest -Uri "http://${host_}:${port}${path}" -UseBasicParsing -TimeoutSec 1
            if ($r.StatusCode -eq 200) { return $true }
        } catch {}
    }
    return $false
}

Write-Host "SG Expenditure Tracker" -ForegroundColor Cyan
Write-Host "-----------------------"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'uv' is not installed or not on PATH. Install it from https://docs.astral.sh/uv/" -ForegroundColor Red
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'npm' is not installed or not on PATH. Install Node.js from https://nodejs.org/" -ForegroundColor Red
    exit 1
}

$windowsOpened = 0

# --- Backend -----------------------------------------------------------------
if (Test-Port 8000 "/api/health") {
    Write-Host "Backend already running on port 8000 - leaving it as is." -ForegroundColor Yellow
} else {
    Write-Host "Starting backend (http://127.0.0.1:8000)..."
    Start-Process powershell -ArgumentList @(
        '-NoExit', '-Command',
        "cd '$backendDir'; uv sync; uv run uvicorn app.main:app --reload"
    )
    $windowsOpened++
}

# --- Frontend ------------------------------------------------------------------
if (Test-Port 5173) {
    Write-Host "Frontend already running on port 5173 - leaving it as is." -ForegroundColor Yellow
} else {
    Write-Host "Starting frontend (http://localhost:5173)..."
    $installStep = if (Test-Path (Join-Path $frontendDir "node_modules")) { "" } else { "npm install; " }
    Start-Process powershell -ArgumentList @(
        '-NoExit', '-Command',
        "cd '$frontendDir'; $installStep npm run dev"
    )
    $windowsOpened++
}

# --- Wait for both, then open the browser ---------------------------------------
Write-Host "Waiting for both servers to come up (first run can take a minute for npm install)..."
$backendReady = $false
$frontendReady = $false
for ($i = 0; $i -lt 60; $i++) {
    if (-not $backendReady) { $backendReady = Test-Port 8000 "/api/health" }
    if (-not $frontendReady) { $frontendReady = Test-Port 5173 }
    if ($backendReady -and $frontendReady) { break }
    Start-Sleep -Seconds 1
}
if (-not $backendReady) {
    Write-Host "Backend didn't respond within 60s - check its window for errors." -ForegroundColor Yellow
}
if (-not $frontendReady) {
    Write-Host "Frontend didn't respond within 60s - check its window for errors." -ForegroundColor Yellow
}

if ($frontendReady) {
    Start-Process "http://localhost:5173"
}

Write-Host ""
if ($windowsOpened -gt 0) {
    Write-Host "$windowsOpened new window(s) opened for server logs. Close them (or Ctrl+C inside each) to stop the app." -ForegroundColor Cyan
} else {
    Write-Host "Both servers were already running - nothing new to start." -ForegroundColor Cyan
}
