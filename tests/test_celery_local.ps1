# Local Celery Testing Script for Hidden Hill
# This script helps you test Celery locally before deploying to Railway

Write-Host "=== Hidden Hill - Local Celery Testing ===" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "manage.py")) {
    Write-Host "ERROR: Please run this script from the project root directory" -ForegroundColor Red
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path "venv\Scripts\activate.ps1")) {
    Write-Host "ERROR: Virtual environment not found. Please create one first:" -ForegroundColor Red
    Write-Host "  python -m venv venv" -ForegroundColor Yellow
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Green
& "venv\Scripts\activate.ps1"

# Check if dependencies are installed
Write-Host "Checking dependencies..." -ForegroundColor Green
try {
    python -c "import celery; import redis" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Modules not found"
    }
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Yellow
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=== Setup Instructions ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "You need to run these commands in SEPARATE terminal windows:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. TERMINAL 1 - Start Redis (choose one):" -ForegroundColor Cyan
Write-Host "   Option A (Docker): docker run -d -p 6379:6379 --name redis redis:latest" -ForegroundColor White
Write-Host "   Option B (WSL):   wsl redis-server" -ForegroundColor White
Write-Host "   Option C:         Download Redis for Windows and run redis-server.exe" -ForegroundColor White
Write-Host ""
Write-Host "2. TERMINAL 2 - Start Celery Worker:" -ForegroundColor Cyan
$currentDir = $PWD.Path
Write-Host "   cd `"$currentDir`"" -ForegroundColor White
Write-Host "   venv\Scripts\activate.ps1" -ForegroundColor White
Write-Host "   celery -A config worker --loglevel=info" -ForegroundColor White
Write-Host ""
Write-Host "3. TERMINAL 3 - Start Django Server:" -ForegroundColor Cyan
Write-Host "   cd `"$currentDir`"" -ForegroundColor White
Write-Host "   venv\Scripts\activate.ps1" -ForegroundColor White
Write-Host "   python manage.py runserver" -ForegroundColor White
Write-Host ""
Write-Host "4. Open browser: http://localhost:8000/upload/" -ForegroundColor Cyan
Write-Host ""
Write-Host "=== Quick Test Commands ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test Redis connection:" -ForegroundColor Yellow
Write-Host '   python -c "import redis; r = redis.Redis(host=''localhost'', port=6379, db=0); print(r.ping())"' -ForegroundColor White
Write-Host ""
Write-Host "Test Celery connection:" -ForegroundColor Yellow
Write-Host "   celery -A config inspect ping" -ForegroundColor White
Write-Host ""

