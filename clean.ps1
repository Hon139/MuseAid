<#
.SYNOPSIS
    Remove all virtual environments and Python caches from MuseAid sub-projects.

.DESCRIPTION
    Stops any MuseAid processes via stop.ps1, then deletes .venv and __pycache__
    folders in each sub-project (server, Composition_App, hand-gesture-app).

.EXAMPLE
    .\clean.ps1
#>

$Root = $PSScriptRoot
$subprojects = @("server", "Composition_App", "hand-gesture-app")
$removed = 0

Write-Host "=== MuseAid Clean ===" -ForegroundColor Cyan
Write-Host ""

# --- Stop running MuseAid processes so files are not locked ---
$stopScript = Join-Path $Root "stop.ps1"
if (Test-Path $stopScript) {
    Write-Host "Stopping running MuseAid processes..." -ForegroundColor Yellow
    & $stopScript
    Write-Host ""
}

# --- Remove .venv directories ---
foreach ($proj in $subprojects) {
    $venv = Join-Path $Root "$proj\.venv"
    if (-not (Test-Path $venv)) {
        Write-Host "  $proj\.venv - not found, skipping" -ForegroundColor DarkGray
        continue
    }

    Write-Host "  Removing $proj\.venv ..." -ForegroundColor Yellow
    cmd /c "rmdir /s /q `"$venv`"" 2>$null

    if (Test-Path $venv) {
        # Files still locked - kill any remaining python.exe and retry
        Write-Host "    Locked files detected, killing remaining Python processes..." -ForegroundColor DarkYellow
        Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        cmd /c "rmdir /s /q `"$venv`"" 2>$null
    }

    if (Test-Path $venv) {
        Write-Host "    WARNING: Could not fully remove $proj\.venv" -ForegroundColor Red
    } else {
        Write-Host "    Removed." -ForegroundColor DarkGray
        $removed++
    }
}

# --- Remove __pycache__ directories (only in source trees, not .venv) ---
Write-Host ""
Write-Host "  Removing __pycache__ directories..." -ForegroundColor Yellow
$cacheCount = 0
foreach ($proj in $subprojects) {
    $projDir = Join-Path $Root $proj
    # Search only src/ and top-level of each subproject, skip .venv
    Get-ChildItem -Path $projDir -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '[\\/]\.venv[\\/]' } |
        ForEach-Object {
            Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
            $cacheCount++
        }
}
# Also check ElevenL/
$elevenL = Join-Path $Root "ElevenL"
if (Test-Path $elevenL) {
    Get-ChildItem -Path $elevenL -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
        ForEach-Object {
            Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
            $cacheCount++
        }
}
if ($cacheCount -eq 0) {
    Write-Host "    No __pycache__ directories found." -ForegroundColor DarkGray
} else {
    Write-Host "    Removed $cacheCount __pycache__ directory(ies)." -ForegroundColor DarkGray
    $removed += $cacheCount
}

Write-Host ""
if ($removed -eq 0) {
    Write-Host "Nothing to clean." -ForegroundColor DarkGray
} else {
    Write-Host "Clean complete." -ForegroundColor Green
}
