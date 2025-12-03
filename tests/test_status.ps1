# PowerShell script to test video generation status updates
# Usage: .\tests\test_status.ps1 -PaperId TEST123 -Step generate-script
#        .\tests\test_status.ps1 -PaperId TEST123 -Auto
#        .\tests\test_status.ps1 -PaperId TEST123 -Auto -Delay 5

param(
    [Parameter(Mandatory=$true)]
    [string]$PaperId,
    
    [ValidateSet("fetch-paper", "generate-script", "generate-audio", "generate-videos")]
    [string]$Step,
    
    [switch]$Auto,
    
    [int]$Delay = 3,
    
    [string]$User
)

$ErrorActionPreference = "Continue"

# Get project root (assuming script is in scripts/ directory)
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $projectRoot

Write-Host "=== Testing Video Generation Status Updates ===" -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
if (Test-Path "venv\Scripts\activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    & "venv\Scripts\activate.ps1"
} else {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please activate your virtual environment first." -ForegroundColor Yellow
    exit 1
}

# Build Python command
$pythonCmd = "python tests\test_status_updates.py $PaperId"

if ($Auto) {
    $pythonCmd += " --auto --delay $Delay"
} elseif ($Step) {
    $pythonCmd += " --step $Step"
}

if ($User) {
    $pythonCmd += " --user $User"
}

Write-Host "Running: $pythonCmd" -ForegroundColor Yellow
Write-Host ""

# Run the Python script
Invoke-Expression $pythonCmd

Write-Host ""
Write-Host "=== Next Steps ===" -ForegroundColor Cyan
Write-Host "Open status page: http://localhost:8000/status/$PaperId/" -ForegroundColor Green
Write-Host "View JSON status: http://localhost:8000/status/$PaperId/?_json=1" -ForegroundColor Green
Write-Host ""

if ($Auto) {
    Write-Host "Status page will automatically update every 3 seconds." -ForegroundColor Yellow
    Write-Host "Script will progress through all steps with $Delay second delays." -ForegroundColor Yellow
}

