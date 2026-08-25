# Starts a throwaway SpendTrack instance pointed at a scratch database, on
# different ports than the normal dev servers, so it can run side-by-side
# with (and never touch data from) a real instance you already have open.
# Meant for agents/scripts driving the UI to verify a change - not for
# everyday development, which is scripts/start.ps1.
#
# Run with:  powershell -ExecutionPolicy Bypass -File scripts/start-test.ps1
# Wipe the scratch data with:  Remove-Item -Recurse -Force .scratch-test

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent  # this script lives in scripts/, repo root is one level up
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$scratchDir = Join-Path $root ".scratch-test"
$dbPath = Join-Path $scratchDir "data.db"

$backendPort = 8001
$frontendPort = 5174

function Test-Port($port, $path = "/") {
    foreach ($host_ in @("127.0.0.1", "localhost")) {
        try {
            $r = Invoke-WebRequest -Uri "http://${host_}:${port}${path}" -UseBasicParsing -TimeoutSec 1
            if ($r.StatusCode -eq 200) { return $true }
        } catch {}
    }
    return $false
}

Write-Host "SpendTrack (scratch test instance)" -ForegroundColor Cyan
Write-Host "-----------------------------------"
Write-Host "Database: $dbPath" -ForegroundColor Yellow

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'uv' is not installed or not on PATH. Install it from https://docs.astral.sh/uv/" -ForegroundColor Red
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'npm' is not installed or not on PATH. Install Node.js from https://nodejs.org/" -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Force -Path $scratchDir | Out-Null

$windowsOpened = 0

# --- Backend -----------------------------------------------------------------
if (Test-Port $backendPort "/api/health") {
    Write-Host "Backend already running on port $backendPort - leaving it as is." -ForegroundColor Yellow
} else {
    Write-Host "Starting backend (http://127.0.0.1:$backendPort)..."
    Start-Process powershell -ArgumentList @(
        '-NoExit', '-Command',
        "cd '$backendDir'; uv sync; `$env:SPENDTRACK_DB_PATH = '$dbPath'; uv run uvicorn app.main:app --reload --port $backendPort"
    )
    $windowsOpened++
}

# --- Frontend ------------------------------------------------------------------
if (Test-Port $frontendPort) {
    Write-Host "Frontend already running on port $frontendPort - leaving it as is." -ForegroundColor Yellow
} else {
    Write-Host "Starting frontend (http://localhost:$frontendPort)..."
    $installStep = if (Test-Path (Join-Path $frontendDir "node_modules")) { "" } else { "npm install; " }
    Start-Process powershell -ArgumentList @(
        '-NoExit', '-Command',
        "cd '$frontendDir'; $installStep `$env:VITE_DEV_PORT = '$frontendPort'; `$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:$backendPort'; npm run dev"
    )
    $windowsOpened++
}

# --- Wait for both, then open the browser ---------------------------------------
Write-Host "Waiting for both servers to come up (first run can take a minute for npm install)..."
$backendReady = $false
$frontendReady = $false
for ($i = 0; $i -lt 60; $i++) {
    if (-not $backendReady) { $backendReady = Test-Port $backendPort "/api/health" }
    if (-not $frontendReady) { $frontendReady = Test-Port $frontendPort }
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
    Start-Process "http://localhost:$frontendPort"
}

Write-Host ""
Write-Host "Scratch database: $dbPath" -ForegroundColor Cyan
if ($windowsOpened -gt 0) {
    Write-Host "$windowsOpened new window(s) opened for server logs. Close them (or Ctrl+C inside each) to stop the app." -ForegroundColor Cyan
} else {
    Write-Host "Both servers were already running - nothing new to start." -ForegroundColor Cyan
}
