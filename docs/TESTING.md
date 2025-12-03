# Testing Guide

Complete guide for testing the Hidden Hill video generation system locally.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Testing Status Updates](#testing-status-updates)
4. [Testing Full Pipeline](#testing-full-pipeline)
5. [Simulation Mode](#simulation-mode)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### 1. Install Dependencies

```powershell
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

### 2. Start Redis

Redis is required for Celery. Choose ONE option:

**Option A: Docker (Recommended)**
```powershell
docker run -d -p 6379:6379 --name redis redis:latest
```

**Option B: WSL (if installed)**
```bash
sudo apt-get install redis-server
redis-server
```

**Option C: Windows Native**
- Download from: https://github.com/microsoftarchive/redis/releases
- Or use Memurai: https://www.memurai.com/get-memurai

**Verify Redis:**
```powershell
python -c "import redis; r = redis.Redis(host='localhost', port=6379, db=0); print('✓ Redis OK!' if r.ping() else '✗ FAILED')"
```

---

## Quick Start

### Start Services

**Terminal 1: Celery Worker**
```powershell
celery -A config worker --loglevel=info
```

**Terminal 2: Django Server**
```powershell
python manage.py runserver
```

You should see:
- Celery: `Connected to redis://localhost:6379/0` and `celery@hostname ready.`
- Django: `Starting development server at http://127.0.0.1:8000/`

---

## Testing Status Updates

Test the status update system without generating videos (no API costs).

### Option 1: Simulation Mode (Recommended)

Test the complete upload → status page flow through the web UI.

1. **Enable simulation mode** - Add to `.env`:
   ```
   SIMULATION_MODE=True
   ```

2. **Start services** (see Quick Start above)

3. **Upload through web UI:**
   - Go to: http://localhost:8000/upload/
   - Paper ID: `TEST123` (must start with TEST)
   - Enter access code
   - Submit!

4. **Watch status page auto-update:**
   - Automatically redirected to status page
   - Updates every 3 seconds
   - Progresses through all 5 steps (~15 seconds)

See `docs/SIMULATION_MODE.md` for detailed documentation.

### Option 2: Test Script (Quick Testing)

Use command-line script to quickly create test data.

**Prerequisites:**
- Django server running (Celery worker NOT needed for script testing)
- At least one user created: `python manage.py createsuperuser`

**Quick Test:**
```powershell
# Test at specific step
python tests/test_status_updates.py TEST123 --step generate-script

# Auto-progress through all steps
python tests/test_status_updates.py TEST123 --auto

# With custom delay
python tests/test_status_updates.py TEST123 --auto --delay 5
```

**Open status page:**
```
http://localhost:8000/status/TEST123/
```

The page auto-refreshes every 3 seconds.

**Common Commands:**
```powershell
# Test at 20% (fetch-paper)
python tests/test_status_updates.py TEST123 --step fetch-paper

# Test at 40% (generate-script)
python tests/test_status_updates.py TEST123 --step generate-script

# Test at 60% (generate-audio)
python tests/test_status_updates.py TEST123 --step generate-audio

# Test at 80% (generate-videos)
python tests/test_status_updates.py TEST123 --step generate-videos

# Test at 100% (completed)
python tests/test_status_updates.py TEST123 --step generate-videos

# Create job for specific user
python tests/test_status_updates.py TEST123 --step generate-script --user admin
```

**Pipeline Steps:**
1. `fetch-paper` (20%) - Fetches paper from PubMed
2. `generate-script` (40%) - Generates video script
3. `generate-audio` (60%) - Generates audio narration
4. `generate-videos` (80%) - Generates video clips
4. `generate-videos` (100%) - Creates final video

**View JSON Status:**
```
http://localhost:8000/status/TEST123/?_json=1
```

---

## Testing Full Pipeline

**Warning:** This will incur API costs (Gemini, RunwayML).

1. **Start services** (see Quick Start above)

2. **Upload through web UI:**
   - Go to: http://localhost:8000/upload/
   - Enter a PubMed ID (e.g., `PMC10979640`)
   - Enter your access code
   - Submit

3. **Watch Celery worker** - you should see the task being processed:
   ```
   [INFO/MainProcess] Task web.tasks.generate_video_task[...] received
   [INFO/ForkPoolWorker-1] Starting video generation task for PMC10979640
   ```

4. **Monitor status:**
   - Status page: http://localhost:8000/status/PMC10979640/
   - Watch progress updates in real-time

---

## Simulation Mode

Simulation mode allows you to test the complete upload and status update flow without generating videos or incurring API costs.

**How it works:**
- Uploads through web UI simulate pipeline progress
- Test paper IDs (starting with "TEST") skip validation
- Status page shows real-time progress updates
- All files and database records are created like a real pipeline

**Enable:**
Add to `.env`:
```
SIMULATION_MODE=True
```

**Usage:**
1. Start services (Django + Celery + Redis)
2. Go to http://localhost:8000/upload/
3. Enter paper ID starting with "TEST" (e.g., `TEST123`)
4. Submit and watch status page update

See `docs/SIMULATION_MODE.md` for detailed documentation.

---

## Troubleshooting

### Redis Connection Error

**Error:** `Cannot connect to redis://localhost:6379/0: Error 10061`

**Solution:**
1. Make sure Redis is running (see Prerequisites)
2. Check port: `netstat -an | findstr 6379` (should show LISTENING)
3. Verify connection: `python -c "import redis; r = redis.Redis(host='localhost', port=6379, db=0); print('OK' if r.ping() else 'FAILED')"`

### Celery Can't Connect

- Verify Redis is running
- Check that port 6379 is not blocked by firewall
- Ensure REDIS_URL is not set in .env (should use default localhost)

### Tasks Not Processing

- Check Celery worker logs for errors
- Verify both Django and Celery services are running
- Check that REDIS_URL is not set in .env

### Status Page Not Updating

- Check browser console for errors
- Verify Django server is running
- Check JSON endpoint: http://localhost:8000/status/TEST123/?_json=1
- Verify files exist in `media/TEST123/`

### "User not found" Error

Create a user first:
```powershell
python manage.py createsuperuser
```

Then use `--user` flag:
```powershell
python tests/test_status_updates.py TEST123 --user your_username
```

### Files Not Created

1. Check that `MEDIA_ROOT` is set correctly in `config/settings.py`
2. Verify write permissions on the media directory
3. Check script output for error messages

---

## Additional Resources

- **Simulation Mode Details:** `docs/SIMULATION_MODE.md`
- **API Documentation:** `docs/API_README.md`
- **Pipeline Documentation:** `docs/PIPELINE_README.md`

