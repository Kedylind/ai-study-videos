# Simulation Mode - Test Upload Flow Without Generating Videos

Simulation mode allows you to test the complete upload and status update flow through the web UI without actually generating videos or incurring API costs.

## How It Works

When simulation mode is enabled:
- Uploads through the web UI will simulate pipeline progress instead of running the actual pipeline
- Test paper IDs (starting with "TEST") skip validation
- The status page will show real-time progress updates as the simulation runs
- All files and database records are created just like a real pipeline

## Enabling Simulation Mode

### Option 1: Environment Variable

Set `SIMULATION_MODE=True` in your `.env` file:

```bash
SIMULATION_MODE=True
```

### Option 2: Environment Variable (Command Line)

```powershell
$env:SIMULATION_MODE="True"
```

## Usage

### Step 1: Enable Simulation Mode

Add to your `.env` file:
```
SIMULATION_MODE=True
```

Or set environment variable before starting Django:
```powershell
$env:SIMULATION_MODE="True"
python manage.py runserver
```

### Step 2: Start Services

You'll need:
- Django server (required)
- Celery worker (required for tasks to run)
- Redis (required for Celery)

```powershell
# Terminal 1: Celery Worker
celery -A config worker --loglevel=info

# Terminal 2: Django Server
python manage.py runserver
```

### Step 3: Upload Through Web UI

1. Go to: http://localhost:8000/upload/
2. Log in (if required)
3. Enter a **test paper ID** (must start with "TEST", e.g., `TEST123`, `TEST456`)
4. Enter your access code
5. Click Submit

**Note:** Test IDs (starting with "TEST") skip paper ID validation in simulation mode. Real PubMed IDs will still be validated.

### Step 4: Watch Status Updates

After submitting, you'll be redirected to the status page. The page will automatically update every 3 seconds showing:
- Progress bar (0-100%)
- Current step name
- Completed steps list
- Progress through all 5 pipeline steps

The simulation takes approximately 15 seconds (5 steps × 3 seconds each).

## What Gets Simulated

The simulation creates the same files and database records as a real pipeline:

1. **fetch-paper** (20%) - Creates `paper.json`
2. **generate-script** (40%) - Creates `script.json`
3. **generate-audio** (60%) - Creates `audio.wav`, `audio_metadata.json`
4. **generate-videos** (80%) - Creates `clips/.videos_complete`, `clips/video_metadata.json`
5. **add-captions** (100%) - Creates `final_video.mp4` (dummy file)

## Differences from Real Pipeline

- ✅ No API calls (Gemini, RunwayML) - **No costs**
- ✅ Faster (15 seconds vs minutes/hours)
- ✅ Always succeeds (no real errors)
- ✅ Creates dummy files (not real videos)
- ✅ Uses simulated paper data

## Disabling Simulation Mode

To disable and use real pipeline:

1. Remove `SIMULATION_MODE=True` from `.env`, or
2. Set `SIMULATION_MODE=False`, or
3. Unset the environment variable

Then restart Django server and Celery worker.

## Testing Different Scenarios

### Test Upload Flow
1. Enable simulation mode
2. Upload `TEST123` through web UI
3. Watch status page update in real-time

### Test Error Handling
Simulation mode always succeeds. To test errors, you'd need to use the test script (`tests/test_status_updates.py`) to manually create failed states.

### Test Multiple Uploads
Upload multiple test IDs (`TEST123`, `TEST456`, etc.) to test concurrent job handling.

## Troubleshooting

### "Invalid access code" Error
Make sure `VIDEO_ACCESS_CODE` is set in your `.env` file.

### Status Page Not Updating
1. Check browser console for JavaScript errors
2. Verify Django server is running
3. Check Celery worker logs - you should see simulation messages
4. Verify simulation mode is enabled: Check that `settings.SIMULATION_MODE` is `True`

### Test IDs Not Working
- Test IDs must start with "TEST" (case-insensitive)
- Simulation mode must be enabled
- Check Celery worker is running (simulation runs in Celery task)

### Real Paper IDs Still Fail
Real paper IDs (non-TEST) still go through validation. Use TEST IDs for simulation mode testing.

## Example Workflow

```powershell
# 1. Enable simulation mode
echo "SIMULATION_MODE=True" >> .env

# 2. Start Celery worker (Terminal 1)
celery -A config worker --loglevel=info

# 3. Start Django server (Terminal 2)
python manage.py runserver

# 4. Open browser
# http://localhost:8000/upload/

# 5. Upload TEST123
# Paper ID: TEST123
# Access Code: (your code)

# 6. Watch status page auto-update!
# http://localhost:8000/status/TEST123/
```

## Comparison: Simulation vs Test Script

| Feature | Simulation Mode | Test Script |
|---------|----------------|-------------|
| **Flow** | Full web UI upload | Command-line only |
| **Status Page** | ✅ Real-time updates | ✅ Can view after |
| **Celery Tasks** | ✅ Uses real tasks | ❌ Direct file creation |
| **User Testing** | ✅ Full user flow | ❌ No upload UI |
| **Speed** | 15 seconds | Instant |

**Use Simulation Mode when:**
- Testing the complete upload → status page flow
- Demonstrating the system to users
- Testing user experience

**Use Test Script when:**
- Quick testing of specific steps
- Creating test data without Celery
- Testing specific scenarios

