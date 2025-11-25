# Start Celery Worker for Hidden Hill
# This script starts a Celery worker to process video generation tasks
# Make sure Redis is running on port 6379 before running this script

$ErrorActionPreference = "Continue"

Write-Host "=== Hidden Hill - Starting Celery Worker ===" -ForegroundColor Cyan
Write-Host ""

# Get project root directory (where this script is located)
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

# Check if virtual environment exists
$venvPath = Join-Path $projectRoot "venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "ERROR: Virtual environment not found at: $venvPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please create a virtual environment first:" -ForegroundColor Yellow
    Write-Host "  python -m venv venv" -ForegroundColor White
    exit 1
}

# Activate virtual environment
$activateScript = Join-Path $venvPath "Scripts\activate.ps1"
if (Test-Path $activateScript) {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    & $activateScript
} else {
    Write-Host "ERROR: Virtual environment activation script not found!" -ForegroundColor Red
    exit 1
}

# Check Redis connection
Write-Host ""
Write-Host "Checking Redis connection..." -ForegroundColor Yellow
try {
    $result = python -c "import redis; r = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=2); print('OK' if r.ping() else 'FAIL')" 2>&1
    if ($result -match "OK") {
        Write-Host "✓ Redis is running and accessible!" -ForegroundColor Green
    } else {
        Write-Host "✗ Redis connection failed" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please make sure Redis is running on localhost:6379" -ForegroundColor Yellow
        Write-Host "You should see Redis running in another terminal window." -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "✗ Failed to connect to Redis" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please make sure Redis is running on localhost:6379" -ForegroundColor Yellow
    exit 1
}

# Check if Celery is installed
Write-Host ""
Write-Host "Checking Celery installation..." -ForegroundColor Yellow
try {
    $celeryVersion = python -c "import celery; print(celery.__version__)" 2>&1
    if ($celeryVersion) {
        Write-Host "✓ Celery $celeryVersion is installed" -ForegroundColor Green
    } else {
        Write-Host "✗ Celery is not installed" -ForegroundColor Red
        Write-Host "Installing requirements..." -ForegroundColor Yellow
        pip install -r requirements.txt
    }
} catch {
    Write-Host "✗ Celery is not installed" -ForegroundColor Red
    Write-Host "Installing requirements..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Start Celery worker
Write-Host ""
Write-Host "=== Starting Celery Worker ===" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the worker" -ForegroundColor Yellow
Write-Host ""
Write-Host "Celery will connect to Redis at: redis://localhost:6379/0" -ForegroundColor Cyan
Write-Host ""

# Start Celery worker (this will block until Ctrl+C)
# Use --pool=solo for Windows compatibility (prefork doesn't work on Windows)
python -m celery -A config worker --pool=solo --loglevel=info

