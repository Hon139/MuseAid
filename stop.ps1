<#
.SYNOPSIS
    Stop all running MuseAid components.

.DESCRIPTION
    Finds and terminates every process spawned by MuseAid: the uvicorn server,
    the Composition App, the hand-gesture app, and any orphaned child processes
    (e.g. multiprocessing workers). Also closes the PowerShell host windows
    opened by start.ps1.
#>

$Root = $PSScriptRoot
$rootEscaped = [regex]::Escape($Root)

Write-Host "=== Stopping MuseAid ===" -ForegroundColor Cyan
Write-Host ""

# --- Snapshot all processes once (avoids repeated slow CIM queries) ---
$allProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue

# Collect PIDs to kill (use a set to avoid duplicates)
$pidsToKill = [System.Collections.Generic.HashSet[int]]::new()

# --- 1. Processes whose executable or command line references the project ---
foreach ($proc in $allProcs) {
    $cmd = $proc.CommandLine
    $exe = $proc.ExecutablePath

    # Match executables inside any .venv under the project root
    if ($exe -and $exe.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        [void]$pidsToKill.Add([int]$proc.ProcessId)
        continue
    }

    # Match known MuseAid command-line patterns
    if ($cmd -and (
        $cmd -match "museaid_server|music.app|music_app|src\.main" -or
        $cmd -match "uvicorn.*museaid" -or
        $cmd -match $rootEscaped
    )) {
        [void]$pidsToKill.Add([int]$proc.ProcessId)
    }
}

# --- 2. Walk the process tree to catch orphaned children ---
do {
    $added = $false
    foreach ($proc in $allProcs) {
        if ($proc.ParentProcessId -and
            $pidsToKill.Contains([int]$proc.ParentProcessId) -and
            -not $pidsToKill.Contains([int]$proc.ProcessId)) {
            [void]$pidsToKill.Add([int]$proc.ProcessId)
            $added = $true
        }
    }
} while ($added)

# --- 3. Remove our own PID and parent so we don't kill ourselves ---
[void]$pidsToKill.Remove($PID)
$myProc = $allProcs | Where-Object { $_.ProcessId -eq $PID } | Select-Object -First 1
if ($myProc) {
    [void]$pidsToKill.Remove([int]$myProc.ParentProcessId)
}

# --- 4. Kill everything collected ---
$stopped = 0
foreach ($killPid in $pidsToKill) {
    $live = Get-Process -Id $killPid -ErrorAction SilentlyContinue
    if (-not $live) { continue }

    # Build a short description from the snapshot
    $info = $allProcs | Where-Object { $_.ProcessId -eq $killPid } | Select-Object -First 1
    $desc = $live.ProcessName
    if ($info -and $info.CommandLine) {
        $snippet = $info.CommandLine
        if ($snippet.Length -gt 80) { $snippet = $snippet.Substring(0, 77) + "..." }
        $desc = "$($live.ProcessName): $snippet"
    }

    Write-Host "  Stopping PID $killPid ($desc)" -ForegroundColor Yellow
    Stop-Process -Id $killPid -Force -ErrorAction SilentlyContinue
    $stopped++
}

# Brief pause so OS releases file handles
if ($stopped -gt 0) { Start-Sleep -Milliseconds 500 }

Write-Host ""
if ($stopped -eq 0) {
    Write-Host "No MuseAid processes found running." -ForegroundColor DarkGray
} else {
    Write-Host "Stopped $stopped process(es)." -ForegroundColor Green
}
