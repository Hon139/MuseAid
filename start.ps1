<#
.SYNOPSIS
    Launch all MuseAid components (server, composition app, hand-gesture app).

.DESCRIPTION
    Opens three PowerShell windows — one for each service.
    The server starts first so the other apps can connect.

.PARAMETER NoGestures
    Skip launching the hand-gesture app (useful if you don't have a webcam).

.EXAMPLE
    .\start.ps1
    .\start.ps1 -NoGestures
#>
param(
    [switch]$NoGestures
)

$Root = $PSScriptRoot
$UvArgs = "--python-preference only-system"

Write-Host "=== MuseAid Launcher ===" -ForegroundColor Cyan
Write-Host ""

# --- 1. Server ---
Write-Host "[1/3] Starting MuseAid server..." -ForegroundColor Yellow
$serverCmd = "Set-Location '$Root\server'; Write-Host 'MuseAid Server' -ForegroundColor Cyan; uv sync $UvArgs; uv run uvicorn museaid_server.main:app --reload --host 0.0.0.0 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $serverCmd

# Give the server a moment to bind the port
Write-Host "       Waiting for server to start..." -ForegroundColor DarkGray
Start-Sleep -Seconds 4

# --- 2. Composition App ---
Write-Host "[2/3] Starting Composition App..." -ForegroundColor Yellow
$compCmd = "Set-Location '$Root\Composition_App'; Write-Host 'Composition App' -ForegroundColor Cyan; uv sync $UvArgs; uv run music-app"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $compCmd

# --- 3. Hand-Gesture App ---
if (-not $NoGestures) {
    Write-Host "[3/3] Starting Hand-Gesture App..." -ForegroundColor Yellow
    $gestureCmd = "Set-Location '$Root\hand-gesture-app'; Write-Host 'Hand-Gesture App' -ForegroundColor Cyan; uv sync $UvArgs; uv run python -m src.main"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $gestureCmd
} else {
    Write-Host "[3/3] Skipping Hand-Gesture App (-NoGestures)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "All components launched. Close the individual windows to stop them," -ForegroundColor Green
Write-Host "or run .\stop.ps1 to shut everything down." -ForegroundColor Green
