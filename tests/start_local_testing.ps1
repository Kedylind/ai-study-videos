# Start Local Testing Environment for Hidden Hill
$ErrorActionPreference = "Continue"

Write-Host "=== Hidden Hill - Starting Local Testing Environment ===" -ForegroundColor Cyan
Write-Host ""

# Get project root (assuming script is in tests/ directory)
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

# Activate virtual environment
if (Test-Path "venv\Scripts\activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    & "venv\Scripts\activate.ps1"
} else {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    exit 1
}

# Check Redis connection
Write-Host "Checking Redis connection..." -ForegroundColor Yellow
$redisRunning = $false
try {
    $result = python -c "import redis; r = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=2); print('OK' if r.ping() else 'FAIL')" 2>&1
    if ($result -match "OK") {
        Write-Host "✓ Redis is running!" -ForegroundColor Green
        $redisRunning = $true
    }
} catch {
    $redisRunning = $false
}

if (-not $redisRunning) {
    Write-Host "✗ Redis is not running" -ForegroundColor Red
    Write-Host ""
    Write-Host "You need to start Redis first. Choose one option:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Option 1 - Docker (if installed):" -ForegroundColor Cyan
    Write-Host "  docker run -d -p 6379:6379 --name redis redis:latest" -ForegroundColor White
    Write-Host ""
    Write-Host "Option 2 - WSL (if you have WSL):" -ForegroundColor Cyan
    Write-Host "  wsl sudo apt-get install redis-server" -ForegroundColor White
    Write-Host "  wsl redis-server" -ForegroundColor White
    Write-Host ""
    Write-Host "Option 3 - Download Redis for Windows:" -ForegroundColor Cyan
    Write-Host "  https://github.com/microsoftarchive/redis/releases" -ForegroundColor White
    Write-Host "  Extract and run redis-server.exe" -ForegroundColor White
    Write-Host ""
    Write-Host "After starting Redis, run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "=== Starting Services ===" -ForegroundColor Cyan
Write-Host ""

# Start Celery Worker in background
Write-Host "Starting Celery worker..." -ForegroundColor Yellow
$celeryScript = @"
Set-Location '$projectRoot'
& '$projectRoot\venv\Scripts\python.exe' -m celery -A config worker --loglevel=info
"@

$celeryJob = Start-Job -ScriptBlock ([scriptblock]::Create($celeryScript))

# Start Django server in background
Write-Host "Starting Django server..." -ForegroundColor Yellow
$djangoScript = @"
Set-Location '$projectRoot'
& '$projectRoot\venv\Scripts\python.exe' manage.py runserver
"@

$djangoJob = Start-Job -ScriptBlock ([scriptblock]::Create($djangoScript))

# Wait for services to start
Start-Sleep -Seconds 3

Write-Host "✓ Services started!" -ForegroundColor Green
Write-Host ""
Write-Host "=== Services Running ===" -ForegroundColor Cyan
Write-Host "Celery Worker Job ID: $($celeryJob.Id)" -ForegroundColor Green
Write-Host "Django Server Job ID: $($djangoJob.Id)" -ForegroundColor Green
Write-Host ""
Write-Host "Open your browser: http://localhost:8000/upload/" -ForegroundColor Cyan
Write-Host ""
Write-Host "=== View Logs ===" -ForegroundColor Cyan
Write-Host "Celery: Receive-Job -Id $($celeryJob.Id)" -ForegroundColor White
Write-Host "Django: Receive-Job -Id $($djangoJob.Id)" -ForegroundColor White
Write-Host ""
Write-Host "=== Stop Services ===" -ForegroundColor Cyan
Write-Host "Stop-Job -Id $($celeryJob.Id), $($djangoJob.Id)" -ForegroundColor White
Write-Host "Remove-Job -Id $($celeryJob.Id), $($djangoJob.Id)" -ForegroundColor White
Write-Host ""

# Show initial logs
Write-Host "=== Initial Logs (waiting 2 seconds) ===" -ForegroundColor Cyan
Start-Sleep -Seconds 2
Write-Host "Celery:" -ForegroundColor Yellow
Receive-Job -Job $celeryJob | Select-Object -First 5
Write-Host "Django:" -ForegroundColor Yellow
Receive-Job -Job $djangoJob | Select-Object -First 3
