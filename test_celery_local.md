# Testing Celery Locally

## Prerequisites

1. **Install Redis** (choose one option):

   **Option A: Using Docker (Recommended)**
   ```powershell
   docker run -d -p 6379:6379 --name redis redis:latest
   ```
   
   **Option B: Using WSL (if you have WSL installed)**
   ```bash
   # In WSL terminal
   sudo apt-get update
   sudo apt-get install redis-server
   redis-server
   ```
   
   **Option C: Download Redis for Windows**
   - Download from: https://github.com/microsoftarchive/redis/releases
   - Extract and run `redis-server.exe`

2. **Verify Redis is running:**
   ```powershell
   # Test connection (if you have redis-cli)
   redis-cli ping
   # Should return: PONG
   ```

## Step-by-Step Testing

### Terminal 1: Start Redis (if not using Docker)
```powershell
# If using Docker, Redis is already running
# Otherwise, start Redis server
redis-server
```

### Terminal 2: Start Celery Worker
```powershell
cd "C:\Users\david\OneDrive\Desktop\Cursor Projects\Hidden-Hill"
# Activate your virtual environment if you have one
# venv\Scripts\activate  # if using venv
celery -A config worker --loglevel=info
```

You should see:
```
celery@hostname v5.3.6 (singularity)
[INFO/MainProcess] Connected to redis://localhost:6379/0
[INFO/MainProcess] celery@hostname ready.
```

### Terminal 3: Start Django Server
```powershell
cd "C:\Users\david\OneDrive\Desktop\Cursor Projects\Hidden-Hill"
# Activate your virtual environment if you have one
# venv\Scripts\activate  # if using venv
python manage.py runserver
```

### Terminal 4: Test (Optional - or use browser)
Open your browser and go to: http://localhost:8000

## Testing the Pipeline

1. **Go to upload page:** http://localhost:8000/upload/
2. **Enter a PubMed ID** (e.g., `PMC10979640`)
3. **Enter your access code**
4. **Submit the form**
5. **Watch Terminal 2 (Celery worker)** - you should see the task being picked up:
   ```
   [INFO/MainProcess] Task web.tasks.generate_video_task[...] received
   [INFO/ForkPoolWorker-1] Starting video generation task for PMC10979640
   ```

## Troubleshooting

### Redis connection error:
```
Error: [Errno 10061] No connection could be made because the target machine actively refused it
```
**Solution:** Make sure Redis is running on port 6379

### Celery can't find tasks:
```
[ERROR/MainProcess] Received unregistered task
```
**Solution:** Make sure you're running `celery -A config worker` from the project root

### Module not found errors:
**Solution:** Make sure you've installed dependencies:
```powershell
pip install -r requirements.txt
```

