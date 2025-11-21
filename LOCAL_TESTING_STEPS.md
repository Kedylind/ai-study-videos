# Local Testing Steps - Manual Guide

## Step 1: Install Dependencies (DONE ✓)
Dependencies are already installed.

## Step 2: Start Redis

You need Redis running. Choose ONE option:

### Option A: Docker (Recommended if you have Docker)
```powershell
docker run -d -p 6379:6379 --name redis redis:latest
```

### Option B: WSL (if you have WSL installed)
```bash
# In WSL terminal
sudo apt-get install redis-server
redis-server
```

### Option C: Download Redis for Windows
1. Download from: https://github.com/microsoftarchive/redis/releases
2. Extract the ZIP file
3. Run `redis-server.exe`

### Verify Redis is Running
```powershell
python -c "import redis; r = redis.Redis(host='localhost', port=6379, db=0); print('Redis OK!' if r.ping() else 'FAILED')"
```

## Step 3: Start Services in Separate Terminals

### Terminal 1: Celery Worker
```powershell
cd "C:\Users\david\OneDrive\Desktop\Cursor Projects\Hidden-Hill"
venv\Scripts\activate.ps1
celery -A config worker --loglevel=info
```

You should see:
```
celery@hostname v5.3.6 (singularity)
[INFO/MainProcess] Connected to redis://localhost:6379/0
[INFO/MainProcess] celery@hostname ready.
```

### Terminal 2: Django Server
```powershell
cd "C:\Users\david\OneDrive\Desktop\Cursor Projects\Hidden-Hill"
venv\Scripts\activate.ps1
python manage.py runserver
```

You should see:
```
Starting development server at http://127.0.0.1:8000/
```

## Step 4: Test

1. Open browser: http://localhost:8000/upload/
2. Enter a PubMed ID (e.g., `PMC10979640`)
3. Enter your access code
4. Submit the form
5. Watch Terminal 1 (Celery) - you should see the task being processed

## Troubleshooting

### Redis Connection Error
- Make sure Redis is running on port 6379
- Check: `netstat -an | findstr 6379` (should show LISTENING)

### Celery Can't Connect
- Verify Redis is running (see Step 2 verification)
- Check that port 6379 is not blocked by firewall

### Tasks Not Processing
- Check Celery worker logs for errors
- Verify both services are running
- Check that REDIS_URL is not set in .env (should use default localhost)

