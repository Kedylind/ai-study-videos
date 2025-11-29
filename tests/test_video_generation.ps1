# Test script for video generation
# Usage: .\test_video_generation.ps1 -PaperId PMC10979640 -OutputDir tmp/PMC10979640

param(
    [Parameter(Mandatory=$true)]
    [string]$PaperId,
    
    [Parameter(Mandatory=$false)]
    [string]$OutputDir = "tmp/$PaperId",
    
    [Parameter(Mandatory=$false)]
    [string]$GeminiApiKey = $env:GEMINI_API_KEY,
    
    [Parameter(Mandatory=$false)]
    [string]$RunwayApiKey = $env:RUNWAYML_API_SECRET
)

# Check if API keys are set
if (-not $GeminiApiKey) {
    Write-Host "ERROR: GEMINI_API_KEY not set. Please set it as an environment variable or pass it as a parameter." -ForegroundColor Red
    Write-Host "You can set it temporarily with: `$env:GEMINI_API_KEY = 'your-key-here'" -ForegroundColor Yellow
    exit 1
}

if (-not $RunwayApiKey) {
    Write-Host "ERROR: RUNWAYML_API_SECRET not set. Please set it as an environment variable or pass it as a parameter." -ForegroundColor Red
    Write-Host "You can set it temporarily with: `$env:RUNWAYML_API_SECRET = 'your-key-here'" -ForegroundColor Yellow
    exit 1
}

# Set environment variables for this session
$env:GEMINI_API_KEY = $GeminiApiKey
$env:RUNWAYML_API_SECRET = $RunwayApiKey

Write-Host "Generating video for paper: $PaperId" -ForegroundColor Green
Write-Host "Output directory: $OutputDir" -ForegroundColor Green
Write-Host ""

# Get project root (assuming script is in tests/ directory)
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

# Activate virtual environment if it exists
if (Test-Path "venv\Scripts\activate.ps1") {
    & "venv\Scripts\activate.ps1"
}

# Run the video generation command from pipeline directory
$pipelineDir = Join-Path $projectRoot "pipeline"
Set-Location $pipelineDir
python main.py generate-video $PaperId $OutputDir
Set-Location $projectRoot

