param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $root

Write-Host "=== AlphaTW Desktop Build ==="
Write-Host "Project: $root"

if (-not $SkipFrontend) {
    Write-Host "[1/3] Building frontend dist..."
    Set-Location "$root\frontend"
    npm run build
    Set-Location $root
}

Write-Host "[2/3] Building PyInstaller bundle..."
python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --name AlphaTW `
  --collect-all google.genai `
  --collect-all google.generativeai `
  --collect-all yfinance `
  --collect-all apscheduler `
  --collect-all feedparser `
  --add-data ".env;." `
  --add-data "frontend\dist;frontend\dist" `
  --add-data "docs;docs" `
  desktop_launcher.py

Write-Host "[3/3] Build complete."
Write-Host "Output: $root\dist\AlphaTW\AlphaTW.exe"
Write-Host ""
Write-Host "Optional installer:"
Write-Host "  Open packaging\AlphaTW.iss with Inno Setup and click Build."
