<#
.SYNOPSIS
    Create / refresh virtual environments for all MuseAid sub-projects.

.DESCRIPTION
    Runs "uv sync" in each sub-project (server, Composition_App, hand-gesture-app)
    to create or update the .venv and install all dependencies.

.EXAMPLE
    .\build.ps1
#>

$Root = $PSScriptRoot
$UvArgs = @("--python-preference", "only-system")
$subprojects = @(
    @{ Name = "server";          Path = "server" },
    @{ Name = "Composition App"; Path = "Composition_App" },
    @{ Name = "Hand-Gesture App"; Path = "hand-gesture-app" }
)

Write-Host "=== MuseAid Build ===" -ForegroundColor Cyan
Write-Host ""

$step = 0
foreach ($proj in $subprojects) {
    $step++
    $dir = Join-Path $Root $proj.Path
    Write-Host "[$step/$($subprojects.Count)] Syncing $($proj.Name)..." -ForegroundColor Yellow

    Push-Location $dir
    try {
        uv sync @UvArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Host "       uv sync failed for $($proj.Name)" -ForegroundColor Red
        } else {
            Write-Host "       Done." -ForegroundColor DarkGray
        }
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Build complete - all virtual environments are ready." -ForegroundColor Green
