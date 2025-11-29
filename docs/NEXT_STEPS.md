# Hidden Hill - Next Steps & Roadmap

**Last Updated:** 2025-01-28  
**Project Status:** Core Features Complete, Cloud Storage Required for Production

---

## 🎯 Project Overview

Hidden Hill is a Django web application that converts scientific papers into engaging social media videos (TikTok/Instagram Reels format). The system uses AI (Gemini for text/audio, Runway for video) to automatically generate educational content from PubMed papers.

**Current Status:**
- ✅ Core pipeline fully functional
- ✅ Web UI and REST API working
- ✅ User authentication implemented
- ✅ Celery task queue integrated (tasks survive server restarts)
- ✅ Access control implemented (access code required)
- ✅ Database models for job tracking implemented
- ✅ "My Videos" archive page implemented
- ⚠️ Progress tracking implemented but unreliable (needs real-time parsing fix)
- 🔴 **CRITICAL BUG:** Video download link missing on status page when pipeline completes
- 🔴 **BLOCKER:** Cloud storage not implemented - videos lost on Railway container restarts

---

## 🚀 High Priority (Production Readiness)

### 1. 🔴 CRITICAL: Fix Missing Video Download Link on Status Page
**Status:** Not implemented  
**Priority:** 🔴 **CRITICAL - Users cannot access completed videos**  
**Estimated Effort:** 1-2 hours

**PROBLEM:**
- When pipeline completes (100% progress, all steps done), the status page shows completion
- **BUT:** No video download/play button is visible
- Users cannot access their completed videos from the status page
- This is a critical UX issue - users generate videos but can't access them

**Root Cause:**
- The template checks `{% if final_video_exists %}` but this might be False even when video exists
- The JavaScript checks for `data.final_video_url` in JSON response, but it might not be set correctly
- The JSON endpoint uses `MEDIA_URL` instead of the `serve_video` endpoint
- When status is "completed" from database, the file existence check might not run properly

**Solution: Fix Video Detection and URL Generation**

---

## Step-by-Step Fix

### Step 1: Fix JSON Response to Always Include Video URL When Complete

**File:** `web/views.py` - `pipeline_status()` function

**Current code (around line 1029-1030):**
```python
"final_video_url": (
    f"{settings.MEDIA_URL}{pmid}/final_video.mp4" if final_video.exists() else None
),
```

**Problem:** Uses `MEDIA_URL` which might not work in production. Should use `serve_video` endpoint.

**Fix:**
```python
# In the JSON response section (around line 1023-1056)
if request.GET.get("_json"):
    # ... existing code ...
    
    # Fix: Always check file existence and use serve_video endpoint
    final_video_url = None
    if final_video.exists():
        from django.urls import reverse
        final_video_url = reverse("serve_video", args=[pmid])
    
    status = {
        "pmid": pmid,
        "exists": output_dir.exists(),
        "final_video": final_video.exists(),
        "final_video_url": final_video_url,  # Use serve_video endpoint
        "status": progress.get("status", "pending"),
        "current_step": progress.get("current_step"),
        "completed_steps": progress.get("completed_steps", []),
        "progress_percent": progress.get("progress_percent", 0),
    }
    
    # CRITICAL FIX: If status is completed or progress is 100%, ensure final_video_url is set
    if (status["status"] == "completed" or status["progress_percent"] >= 100):
        if final_video.exists() and not final_video_url:
            from django.urls import reverse
            final_video_url = reverse("serve_video", args=[pmid])
            status["final_video_url"] = final_video_url
            status["final_video"] = True
```

---

### Step 2: Fix HTML Context to Always Check File Existence

**File:** `web/views.py` - `pipeline_status()` function (HTML rendering section)

**Current code (around line 1074-1087):**
```python
# Use dedicated video endpoint if video exists, otherwise use media URL
if final_video.exists():
    from django.urls import reverse
    final_video_url = reverse("serve_video", args=[pmid])
else:
    final_video_url = f"{settings.MEDIA_URL}{pmid}/final_video.mp4"

context = {
    "pmid": pmid,
    "final_video_exists": final_video.exists(),
    "final_video_url": final_video_url,
    "log_tail": log_tail,
    "progress": progress,
    "error_message": error_message,
}
```

**Problem:** If progress shows 100% but `final_video.exists()` returns False (file system issue), video section won't show.

**Fix:**
```python
# CRITICAL FIX: If progress is 100% or status is completed, check file again
final_video_exists = final_video.exists()
if (progress.get("progress_percent", 0) >= 100 or progress.get("status") == "completed"):
    # Double-check file existence - might have been created after initial check
    final_video_exists = final_video.exists()
    # If still doesn't exist, check if job says it's completed
    if not final_video_exists:
        try:
            from web.models import VideoGenerationJob
            job = VideoGenerationJob.objects.filter(paper_id=pmid).order_by('-created_at').first()
            if job and job.status == 'completed' and job.final_video_path:
                # Job says completed, try to construct path from job record
                final_video_path = Path(job.final_video_path)
                if final_video_path.exists():
                    final_video_exists = True
        except:
            pass

# Use dedicated video endpoint if video exists
if final_video_exists:
    from django.urls import reverse
    final_video_url = reverse("serve_video", args=[pmid])
else:
    final_video_url = None  # Don't set invalid URL

context = {
    "pmid": pmid,
    "final_video_exists": final_video_exists,  # Use the checked value
    "final_video_url": final_video_url,
    "log_tail": log_tail,
    "progress": progress,
    "error_message": error_message,
}
```

---

### Step 3: Fix JavaScript to Show Video Section When Complete

**File:** `web/templates/status.html`

**Current code (around line 158):**
```javascript
if ((data.status === 'completed' || data.final_video) && data.final_video_url) {
```

**Problem:** Logic might not catch all cases where video is ready.

**Fix:**
```javascript
// Update status alert
const statusContainer = document.getElementById('status-alert-container');
if (statusContainer) {
    // Check if video exists - multiple conditions
    const videoReady = (
        (data.status === 'completed' && data.final_video_url) ||
        (data.progress_percent >= 100 && data.final_video_url) ||
        (data.final_video === true && data.final_video_url)
    );
    
    if (videoReady) {
        // Video is ready - show success message
        statusContainer.innerHTML = `
            <div class="alert alert-info" style="background-color: #e8f5e9; border: 2px solid #4CAF50; border-radius: 8px; padding: 1.5em;">
                <h3 style="margin-top: 0; color: #2e7d32;">🎬 Video Ready!</h3>
                <p style="font-size: 1.1em; margin-bottom: 1em;">Your video has been successfully generated and is ready to download or play.</p>
                <div class="button-group" style="display: flex; gap: 1em; flex-wrap: wrap;">
                    <a href="${data.final_video_url}" class="btn-primary" style="padding: 0.75em 1.5em; font-size: 1.1em; text-decoration: none; background-color: #2196F3; color: white; border-radius: 4px; font-weight: bold;">▶️ Play/Download Video</a>
                    <a href="/result/${pmid}" class="btn-secondary" style="padding: 0.75em 1.5em; font-size: 1.1em; text-decoration: none; background-color: #757575; color: white; border-radius: 4px;">📄 View Result Page</a>
                </div>
            </div>
        `;
        
        // Also show the static video section if it exists
        const videoSection = document.querySelector('[data-video-section]');
        if (videoSection) {
            videoSection.style.display = 'block';
        }
        
        isCompleted = true;
        stopPolling();
    } else if (data.status === 'failed') {
        // ... existing error handling ...
    }
}
```

---

### Step 4: Add Fallback Video Section That Always Shows When Complete

**File:** `web/templates/status.html`

**Add this after the progress section (around line 86):**

```html
<!-- Video Section - Always show when progress is 100% -->
{% if progress.progress_percent >= 100 %}
<div id="video-section-fallback" data-video-section style="background-color: #e8f5e9; border: 2px solid #4CAF50; border-radius: 8px; padding: 1.5em; margin: 1.5em 0;">
    <h2 style="margin-top: 0; color: #2e7d32;">🎬 Video Ready!</h2>
    <p style="font-size: 1.1em; margin-bottom: 1em;">Your video has been successfully generated.</p>
    {% if final_video_exists and final_video_url %}
    <div class="button-group" style="display: flex; gap: 1em; flex-wrap: wrap;">
        <a href="{{ final_video_url }}" class="btn-primary" style="padding: 0.75em 1.5em; font-size: 1.1em; text-decoration: none; background-color: #2196F3; color: white; border-radius: 4px; font-weight: bold;">▶️ Play/Download Video</a>
        <a href="/result/{{ pmid }}" class="btn-secondary" style="padding: 0.75em 1.5em; font-size: 1.1em; text-decoration: none; background-color: #757575; color: white; border-radius: 4px;">📄 View Result Page</a>
    </div>
    {% else %}
    <p style="color: #f57c00;">Video file is being processed. Please refresh the page in a moment.</p>
    <a href="/result/{{ pmid }}" class="btn-secondary">Try Result Page</a>
    {% endif %}
</div>
{% endif %}
```

---

## Testing Checklist

- [ ] Generate a video and wait for completion
- [ ] Check status page - video download button should be visible
- [ ] Click "Play/Download Video" - should open video
- [ ] Check JSON endpoint (`/status/<pmid>/?_json=1`) - should have `final_video_url`
- [ ] Refresh page after completion - video section should still show
- [ ] Test with video that exists but status wasn't updated - should still show
- [ ] Test error case - video doesn't exist but status says completed

---

## Expected Result

After fix:
- ✅ When pipeline completes (100% progress), video download button appears immediately
- ✅ Video section is visible on status page
- ✅ "Play/Download Video" button works correctly
- ✅ JSON response includes `final_video_url` when video is ready
- ✅ Works even if file system check has timing issues
- ✅ Fallback section shows if JavaScript doesn't update

---

## Files to Modify

1. **`web/views.py`**:
   - Fix JSON response to use `serve_video` endpoint
   - Add better file existence checking when status is completed
   - Ensure `final_video_url` is always set when video exists

2. **`web/templates/status.html`**:
   - Fix JavaScript video detection logic
   - Add fallback video section that shows when progress is 100%

---

### 2. ⚠️ CRITICAL: Implement Persistent Video Storage with Railway Volumes
**Status:** Not implemented  
**Priority:** 🔴 **CRITICAL - BLOCKING PRODUCTION**  
**Estimated Effort:** 1-2 hours

**WHY THIS IS CRITICAL:**
- **Current Problem:** Videos are saved to local filesystem (`MEDIA_ROOT = BASE_DIR / "media"`)
- **Railway Issue:** Railway uses **ephemeral filesystem** - all files are **LOST** on:
  - Container restart
  - Deployment
  - Service restart
  - Scaling events
- **Impact:** Users generate videos → videos disappear after any restart → **unusable in production**
- **This must be fixed before deploying to production!**

**Solution: Railway Volumes (Easiest Solution)**

Railway Volumes provide persistent storage that survives container restarts. This is the simplest solution that requires no external services or code changes to the pipeline.

---

## Step-by-Step Implementation Guide

### Step 1: Create Railway Volume in Dashboard

1. **Go to Railway Dashboard:**
   - Navigate to your Hidden Hill project
   - Click on your web service (the Django app service)

2. **Add Volume:**
   - In the service settings, find the "Volumes" section
   - Click "Add Volume" or "New Volume"
   - Name it: `media-storage` (or any descriptive name)
   - Set the size (start with 10GB, can increase later)
   - Click "Create"

3. **Mount the Volume:**
   - After creating the volume, you'll see a "Mount Path" field
   - Set the mount path to: `/app/media`
   - This is where Railway will mount the persistent volume in your container
   - Save the configuration

**Important:** The mount path `/app/media` must match where your Django app expects media files. We'll verify this in the next step.

---

### Step 2: Verify MEDIA_ROOT Path

**File to check:** `config/settings.py`

**Current setting (around line 148-149):**
```python
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

**What to verify:**
- `BASE_DIR` is the project root directory (typically `/app` in Railway containers)
- So `MEDIA_ROOT` resolves to `/app/media`
- This matches the volume mount path from Step 1 ✅

**If MEDIA_ROOT is different:**
- Either change `MEDIA_ROOT` to match the volume mount path
- Or change the volume mount path to match `MEDIA_ROOT`
- They must be the same for this to work

**No code changes needed if `MEDIA_ROOT = BASE_DIR / "media"` and volume is mounted at `/app/media`** ✅

---

### Step 3: Verify Pipeline Code Uses MEDIA_ROOT

**Files to check:**
- `pipeline/main.py` - Should use `output_dir` parameter
- `web/tasks.py` - Should pass `MEDIA_ROOT / paper_id` as output directory
- `web/views.py` - Should use `settings.MEDIA_ROOT` for file paths

**Current implementation check:**

1. **Check `web/tasks.py` (around line 460):**
   ```python
   output_dir = Path(settings.MEDIA_ROOT) / pmid
   ```
   ✅ This is correct - it uses `MEDIA_ROOT` which will now point to the mounted volume

2. **Check `web/views.py` (around line 647):**
   ```python
   output_dir = Path(settings.MEDIA_ROOT) / pmid
   ```
   ✅ This is correct - uses `MEDIA_ROOT`

3. **Check `pipeline/main.py`:**
   - The pipeline receives `output_dir` as a parameter
   - It writes files directly to that directory
   - Since `output_dir` comes from `MEDIA_ROOT`, files will go to the volume ✅

**No code changes needed** - the existing code already uses `MEDIA_ROOT` correctly!

---

### Step 4: Deploy and Test

1. **Deploy to Railway:**
   - Push your code (if you made any changes)
   - Railway will automatically redeploy
   - The volume will be mounted at `/app/media`

2. **Test Video Generation:**
   - Go to your Railway app URL
   - Log in and generate a video
   - Wait for it to complete
   - Note the paper ID (e.g., `PMC10979640`)

3. **Verify File Location:**
   - The video should be at: `/app/media/<paper_id>/final_video.mp4`
   - This path is now on the persistent volume

4. **Test Persistence:**
   - **Option A (Recommended):** In Railway dashboard, restart the service manually
   - **Option B:** Trigger a redeploy
   - After restart, check if the video is still accessible
   - Go to `/result/<paper_id>/` - video should still play ✅

5. **Verify in Database:**
   - Check `VideoGenerationJob` records in Django admin or database
   - `final_video_path` should show the path (e.g., `media/PMC10979640/final_video.mp4`)
   - The file should exist at that path even after restart

---

### Step 5: Verify Volume Mounting (Optional Debugging)

If videos are still being lost, verify the volume is mounted:

1. **Check Railway Logs:**
   - Look for volume mount messages during container startup
   - Should see something like: "Volume mounted at /app/media"

2. **Add Debug Endpoint (Temporary):**
   - Add to `web/views.py`:
   ```python
   def debug_media_path(request):
       import os
       from pathlib import Path
       from django.conf import settings
       
       media_root = Path(settings.MEDIA_ROOT)
       info = {
           "MEDIA_ROOT": str(media_root),
           "MEDIA_ROOT_exists": media_root.exists(),
           "MEDIA_ROOT_is_dir": media_root.is_dir(),
           "MEDIA_ROOT_writable": os.access(media_root, os.W_OK),
           "files_in_media": list(media_root.iterdir())[:10] if media_root.exists() else [],
       }
       return JsonResponse(info)
   ```
   - Add route: `path("debug-media/", debug_media_path, name="debug_media")`
   - Visit `/debug-media/` to see if volume is mounted correctly

3. **Check File System:**
   - `MEDIA_ROOT_exists` should be `True`
   - `MEDIA_ROOT_writable` should be `True`
   - If either is `False`, the volume isn't mounted correctly

---

## Troubleshooting

### Problem: Videos still lost after restart

**Possible causes:**
1. Volume not mounted correctly
   - **Fix:** Check Railway dashboard → Volumes → Verify mount path is `/app/media`
   - Verify service is using the volume (should show in service settings)

2. MEDIA_ROOT path mismatch
   - **Fix:** Ensure `MEDIA_ROOT = BASE_DIR / "media"` and volume is at `/app/media`
   - Check that `BASE_DIR` is `/app` in Railway (it should be)

3. Files being written to wrong location
   - **Fix:** Add debug endpoint (Step 5) to verify where files are actually being written
   - Check `web/tasks.py` and `web/views.py` - ensure they use `settings.MEDIA_ROOT`

### Problem: Permission errors

**If you see permission errors:**
- Railway volumes should have correct permissions automatically
- If not, you may need to set volume permissions in Railway dashboard
- Or add a startup script to set permissions (rarely needed)

### Problem: Volume not showing in dashboard

**If you can't find Volumes section:**
- Make sure you're on the correct service (web service, not database)
- Some Railway plans may have volume limits - check your plan
- Try creating volume from project level instead of service level

---

## Expected Result

After completing these steps:

✅ Videos are saved to `/app/media/<paper_id>/final_video.mp4`  
✅ Files persist across container restarts  
✅ Files persist across deployments  
✅ Users can access videos even after service restarts  
✅ Database records match actual file locations  
✅ "My Videos" page shows accessible videos  

---

## Files That May Need Changes

**Most likely: NONE** - The existing code should work as-is if:
- `MEDIA_ROOT = BASE_DIR / "media"` in `config/settings.py`
- Volume is mounted at `/app/media` in Railway
- Pipeline code uses `output_dir` parameter (which it does)

**Only modify if:**
- You need to change the media path
- You want to add volume-specific configuration
- You encounter permission issues (rare)

---

## Testing Checklist

- [ ] Volume created in Railway dashboard
- [ ] Volume mounted at `/app/media`
- [ ] `MEDIA_ROOT` in settings matches mount path
- [ ] Generated a test video
- [ ] Video file exists at expected path
- [ ] Restarted Railway service
- [ ] Video still accessible after restart
- [ ] Database record shows correct path
- [ ] User can view video in "My Videos" page
- [ ] Video playback works correctly

---

## Next Steps After Implementation

Once Railway Volumes are working:

1. **Monitor storage usage:**
   - Check volume size in Railway dashboard
   - Plan for cleanup of old videos if needed (future feature)

2. **Consider cleanup strategy:**
   - Videos will accumulate on the volume
   - May want to implement video deletion feature later
   - Or set up automatic cleanup of videos older than X days

3. **Optional: Migrate to S3 later:**
   - Railway Volumes work great for now
   - Can migrate to AWS S3 later if you need:
     - Multi-region support
     - CDN integration
     - More flexible storage options

---

### 3. Fix Progress Tracking - Real-Time Pipeline Output Parsing
**Status:** Not implemented  
**Priority:** 🔴 **CRITICAL - Progress tracking not working reliably**  
**Estimated Effort:** 2-3 hours

**WHY THIS IS NEEDED:**
- **Current Problem:** Progress tracking uses file existence checks which are unreliable
- **Issues:**
  - Files may not be immediately visible after creation
  - Background thread may not be running properly
  - 5-second polling delay causes missed updates
  - File system timing issues on different platforms
- **Impact:** Progress bar doesn't update reliably, users see stuck progress

**Solution: Parse Pipeline Output in Real-Time**

Instead of checking file existence, parse the pipeline's stdout/stderr output in real-time to detect when steps complete. The pipeline already logs step completions (e.g., `"Step: fetch-paper"` and `"✓ Complete"`).

---

## Step-by-Step Implementation Guide

### Step 1: Modify Subprocess to Capture Output

**File:** `web/tasks.py`

**Current code (around line 199-207):**
```python
with open(log_path, "ab") as log_file:
    process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=str(settings.BASE_DIR),
        start_new_session=True,
    )
```

**Change to:**
```python
# Open log file for writing
log_file = open(log_path, "ab")

# Create subprocess with PIPE for stdout so we can read it
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,  # Changed from log_file to PIPE
    stderr=subprocess.STDOUT,  # Merge stderr into stdout
    env=env,
    cwd=str(settings.BASE_DIR),
    start_new_session=True,
    text=True,  # Text mode for line-by-line reading
    bufsize=1,  # Line buffered
)
```

**Why:** This allows us to read output line-by-line while also writing to the log file.

---

### Step 2: Create Progress Parser Function

**File:** `web/tasks.py`

**Add this function before `generate_video_task()`:**

```python
def _parse_pipeline_progress(line: str, current_progress: dict) -> dict:
    """
    Parse a single line of pipeline output to detect progress updates.
    
    Args:
        line: A line from pipeline stdout/stderr
        current_progress: Current progress dict with keys:
            - progress_percent: int (0-100)
            - current_step: str or None
            - completed_steps: list of step names
    
    Returns:
        Updated progress dict, or None if no change
    """
    line_lower = line.lower()
    
    # Step completion markers
    step_markers = {
        "fetch-paper": {
            "start": "step: fetch-paper",
            "complete": "✓ complete",
            "percent": 20,
        },
        "generate-script": {
            "start": "step: generate-script",
            "complete": "✓ complete",
            "percent": 40,
        },
        "generate-audio": {
            "start": "step: generate-audio",
            "complete": "✓ complete",
            "percent": 60,
        },
        "generate-videos": {
            "start": "step: generate-videos",
            "complete": "✓ complete",
            "percent": 80,
        },
        "add-captions": {
            "start": "step: add-captions",
            "complete": "✓ complete",
            "percent": 100,
        },
    }
    
    # Check for step completions
    for step_name, markers in step_markers.items():
        if markers["start"] in line_lower and markers["complete"] in line_lower:
            # Step completed
            if step_name not in current_progress.get("completed_steps", []):
                current_progress["progress_percent"] = markers["percent"]
                current_progress["current_step"] = None
                if "completed_steps" not in current_progress:
                    current_progress["completed_steps"] = []
                current_progress["completed_steps"].append(step_name)
                return current_progress
        elif markers["start"] in line_lower:
            # Step started but not completed yet
            if step_name not in current_progress.get("completed_steps", []):
                current_progress["current_step"] = step_name
                return current_progress
    
    # Check for pipeline completion
    if "pipeline complete!" in line_lower:
        current_progress["progress_percent"] = 100
        current_progress["current_step"] = None
        return current_progress
    
    # Check for failures
    if "✗" in line or "pipelineerror" in line_lower or "failed" in line_lower:
        current_progress["status"] = "failed"
        return current_progress
    
    return None  # No progress change
```

---

### Step 3: Replace Background Thread with Real-Time Output Reading

**File:** `web/tasks.py`

**Replace the background thread code (lines 211-239) with:**

```python
# Read output line-by-line and update progress in real-time
progress_state = {
    "progress_percent": 0,
    "current_step": "starting",
    "completed_steps": [],
    "status": "running",
}

def update_progress_from_line(line: str):
    """Update progress state from a pipeline output line."""
    parsed = _parse_pipeline_progress(line, progress_state.copy())
    if parsed:
        progress_state.update(parsed)
        
        # Update database immediately
        try:
            from django.db import connections
            connections.close_all()
            
            from web.models import VideoGenerationJob
            from django.utils import timezone
            
            job = VideoGenerationJob.objects.get(task_id=self.request.id)
            
            # Only update if job is still running
            if job.status in ['pending', 'running']:
                job.progress_percent = progress_state["progress_percent"]
                job.current_step = progress_state.get("current_step")
                
                if progress_state.get("status") == "failed":
                    job.status = "failed"
                
                if progress_state["progress_percent"] == 100:
                    job.status = "completed"
                    job.current_step = None
                    job.completed_at = timezone.now()
                
                job.save(update_fields=[
                    'progress_percent', 'current_step', 'status', 
                    'completed_at', 'updated_at'
                ])
                
                logger.info(
                    f"Progress updated: {job.progress_percent}%, "
                    f"step: {job.current_step}"
                )
            
            connections.close_all()
        except Exception as e:
            logger.warning(f"Failed to update progress from line: {e}")

# Start thread to read output and update progress
def read_output_and_update_progress():
    """Read subprocess output line-by-line and update progress."""
    try:
        for line in process.stdout:
            # Write to log file
            log_file.write(line.encode('utf-8'))
            log_file.flush()
            
            # Parse for progress updates
            update_progress_from_line(line)
            
    except Exception as e:
        logger.error(f"Error reading subprocess output: {e}", exc_info=True)
    finally:
        log_file.close()

# Start output reading thread
output_thread = threading.Thread(target=read_output_and_update_progress, daemon=True)
output_thread.start()
logger.info("Started real-time output parsing thread")
```

---

### Step 4: Update Process Waiting Logic

**File:** `web/tasks.py`

**Replace the process.wait() code (around line 244-249) with:**

```python
# Wait for process to complete with timeout handling
timeout_seconds = settings.CELERY_TASK_TIME_LIMIT - 60  # Leave 60s buffer
try:
    return_code = process.wait(timeout=timeout_seconds)
    logger.info(f"Subprocess completed with return code: {return_code}")
    
    # Wait for output thread to finish reading remaining output
    output_thread.join(timeout=5)
    
    # Final progress update
    if progress_state["progress_percent"] < 100:
        # Check if final video exists
        final_video = output_path / "final_video.mp4"
        if final_video.exists():
            progress_state["progress_percent"] = 100
            progress_state["current_step"] = None
            progress_state["status"] = "completed"
            update_progress_from_line("Pipeline complete!")
    
except subprocess.TimeoutExpired:
    logger.error(f"Subprocess timed out after {timeout_seconds} seconds")
    # Try graceful termination first
    try:
        process.terminate()
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        # Force kill if it doesn't terminate
        logger.warning("Subprocess didn't terminate, forcing kill")
        process.kill()
        process.wait()
    return_code = -1
    raise Exception(f"Pipeline timed out after {timeout_seconds} seconds")
finally:
    # Ensure log file is closed
    try:
        if not log_file.closed:
            log_file.close()
    except:
        pass
```

---

### Step 5: Remove Old File-Based Progress Function

**File:** `web/tasks.py`

**You can keep `update_job_progress_from_files()` as a fallback, but it won't be used in the main flow anymore.**

**Optional:** Remove the background thread that calls `update_job_progress_from_files()` since we're now parsing output in real-time.

---

### Step 6: Test the Implementation

1. **Generate a test video:**
   - Submit a paper ID
   - Watch the status page

2. **Verify real-time updates:**
   - Progress should update immediately when each step completes
   - No 5-second delay
   - Progress bar should be smooth

3. **Check logs:**
   - Look for "Progress updated: X%, step: Y" messages
   - Should see updates as pipeline runs

4. **Test error handling:**
   - Try with invalid paper ID
   - Should detect failure immediately from log output

---

## Expected Behavior

**Before (file-based):**
- Progress updates every 5 seconds (if background thread works)
- May miss updates if files aren't immediately visible
- Unreliable on different file systems

**After (real-time parsing):**
- Progress updates **immediately** when pipeline logs step completion
- No file system timing issues
- More reliable and responsive
- Works consistently across platforms

---

## Files to Modify

1. **`web/tasks.py`**:
   - Change subprocess to use `stdout=subprocess.PIPE`
   - Add `_parse_pipeline_progress()` function
   - Replace background thread with real-time output reading
   - Update process waiting logic

**No changes needed to:**
- `web/views.py` - Still reads from database
- `web/models.py` - Model stays the same
- Pipeline code - No changes needed

---

## Troubleshooting

### Problem: Progress still not updating

**Check:**
1. Is the output thread running? Look for "Started real-time output parsing thread" in logs
2. Are pipeline log messages appearing? Check `pipeline.log` file
3. Is the database being updated? Check for "Progress updated" log messages

**Fix:**
- Ensure `PYTHONUNBUFFERED=1` is set (already done)
- Check that pipeline actually logs step completions
- Verify database connections are being closed properly

### Problem: Log file not being written

**Fix:**
- Ensure `log_file.write()` and `log_file.flush()` are called
- Check file permissions
- Verify `log_path` is correct

### Problem: Thread hanging

**Fix:**
- Ensure `output_thread.join(timeout=5)` has a timeout
- Make thread daemon=True so it doesn't block shutdown
- Check that process.stdout is being read correctly

---

## Benefits of This Approach

✅ **Real-time updates** - Progress updates immediately when steps complete  
✅ **No file system issues** - Doesn't depend on file visibility  
✅ **More reliable** - Based on actual pipeline output, not file existence  
✅ **Better error detection** - Can detect failures from log output immediately  
✅ **Works across platforms** - No file system timing differences  
✅ **No external dependencies** - Uses existing pipeline logging  

---

### 4. Celery Production Deployment
**Status:** UI exists, backend processing incomplete  
**Priority:** 🟠 High  
**Estimated Effort:** 3-4 hours

**What needs to be done:**
- Implement PDF parsing/extraction in `web/views.py`
- Add support for local file processing in pipeline
- Update `upload_paper` view to handle file uploads
- Test with various file formats (PDF, DOCX, etc.)

**Current blocker:**
```python
# Line 191 in web/views.py
# TODO: support pipeline from local file; for now, return to status page
```

**Current failure scenario:**
- When a file is uploaded, the filename stem is used as the paper ID
- Pipeline attempts to fetch from PubMed Central using filename as PMID/PMCID
- Fails with error: `PMID [filename] is not available in PubMed Central`
- Example: Uploading `kahneman-deaton-2010-high-income-improves-evaluation-of-life-but-not-emotional-well-being.pdf` tries to use the filename as a PubMed ID, causing immediate failure at the `fetch-paper` step

**Implementation approach:**
1. Extract text from uploaded PDF/DOCX
2. Convert to paper.json format (matching PubMed structure)
3. Run pipeline with extracted content
4. Handle errors gracefully
5. Add file validation (check file type, size limits)
6. Create alternative pipeline path for local files (skip PubMed fetch step)

**Action items:**
- [ ] Add PDF parsing library (PyPDF2, pdfplumber, or similar)
- [ ] Implement text extraction function for PDFs
- [ ] Create function to convert extracted text to `paper.json` format
- [ ] Update `_start_pipeline_async` to detect file uploads vs PubMed IDs
- [ ] Create new pipeline step or modify existing to handle local files
- [ ] Add file validation and error handling
- [ ] Test with various PDF formats and sizes

---

---

## 📋 Medium Priority (Feature Enhancements)

### 5. Complete File Upload Feature
**Status:** UI exists, backend processing incomplete  
**Priority:** 🟠 High  
**Estimated Effort:** 3-4 hours

**What needs to be done:**
- Implement PDF parsing/extraction in `web/views.py`
- Add support for local file processing in pipeline
- Update `upload_paper` view to handle file uploads
- Test with various file formats (PDF, DOCX, etc.)

**Current blocker:**
```python
# Line 191 in web/views.py
# TODO: support pipeline from local file; for now, return to status page
```

**Current failure scenario:**
- When a file is uploaded, the filename stem is used as the paper ID
- Pipeline attempts to fetch from PubMed Central using filename as PMID/PMCID
- Fails with error: `PMID [filename] is not available in PubMed Central`
- Example: Uploading `kahneman-deaton-2010-high-income-improves-evaluation-of-life-but-not-emotional-well-being.pdf` tries to use the filename as a PubMed ID, causing immediate failure at the `fetch-paper` step

**Implementation approach:**
1. Extract text from uploaded PDF/DOCX
2. Convert to paper.json format (matching PubMed structure)
3. Run pipeline with extracted content
4. Handle errors gracefully
5. Add file validation (check file type, size limits)
6. Create alternative pipeline path for local files (skip PubMed fetch step)

**Action items:**
- [ ] Add PDF parsing library (PyPDF2, pdfplumber, or similar)
- [ ] Implement text extraction function for PDFs
- [ ] Create function to convert extracted text to `paper.json` format
- [ ] Update `_start_pipeline_async` to detect file uploads vs PubMed IDs
- [ ] Create new pipeline step or modify existing to handle local files
- [ ] Add file validation and error handling
- [ ] Test with various PDF formats and sizes

---

### 6. Add Video Deletion to "My Videos" Page
**Status:** Not implemented  
**Priority:** 🟡 Medium  
**Estimated Effort:** 2-3 hours

**What needs to be done:**
- Add delete button to each video entry in "My Videos" page
- Implement delete view that:
  - Verifies user owns the video (security check)
  - Deletes the video file from storage
  - Deletes the `VideoGenerationJob` database record
  - Handles errors gracefully (file not found, permission errors)
- Add confirmation dialog before deletion
- Update UI after successful deletion (remove from list without page refresh)
- Show success/error messages

**Implementation Steps:**

1. **Create Delete View:**
   - File: `web/views.py`
   - Add `@login_required` decorator
   - Verify `VideoGenerationJob.user == request.user` (security)
   - Delete video file from `MEDIA_ROOT / paper_id / final_video.mp4`
   - Delete all related files (audio, clips, etc.) or just the final video
   - Delete `VideoGenerationJob` record from database
   - Return JSON response for AJAX or redirect to my_videos page

2. **Add URL Route:**
   - File: `web/urls.py`
   - Add: `path('my-videos/<str:paper_id>/delete/', delete_video, name='delete_video')`

3. **Update Template:**
   - File: `web/templates/my_videos.html`
   - Add delete button for each video entry
   - Add confirmation dialog (JavaScript)
   - Add AJAX call to delete endpoint
   - Update UI after successful deletion

4. **Handle Edge Cases:**
   - Video file doesn't exist (already deleted)
   - User tries to delete someone else's video (security check)
   - Database record doesn't exist
   - Storage errors (permissions, disk full)

**Code Example:**

```python
@login_required
def delete_video(request, paper_id: str):
    """Delete a video and its database record."""
    try:
        from web.models import VideoGenerationJob
        from pathlib import Path
        from django.conf import settings
        
        # Get job record and verify ownership
        try:
            job = VideoGenerationJob.objects.get(paper_id=paper_id, user=request.user)
        except VideoGenerationJob.DoesNotExist:
            return JsonResponse({"success": False, "error": "Video not found"}, status=404)
        
        # Delete video file
        video_path = Path(settings.MEDIA_ROOT) / paper_id / "final_video.mp4"
        if video_path.exists():
            try:
                video_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete video file: {e}")
        
        # Optionally delete entire directory
        output_dir = Path(settings.MEDIA_ROOT) / paper_id
        if output_dir.exists():
            try:
                import shutil
                shutil.rmtree(output_dir)
            except Exception as e:
                logger.warning(f"Failed to delete output directory: {e}")
        
        # Delete database record
        job.delete()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"success": True, "message": "Video deleted successfully"})
        else:
            messages.success(request, "Video deleted successfully")
            return redirect('my_videos')
            
    except Exception as e:
        logger.error(f"Error deleting video {paper_id}: {e}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"success": False, "error": str(e)}, status=500)
        else:
            messages.error(request, f"Error deleting video: {str(e)}")
            return redirect('my_videos')
```

**Files to modify:**
- `web/views.py` - Add `delete_video()` view
- `web/urls.py` - Add delete route
- `web/templates/my_videos.html` - Add delete button and JavaScript

**Testing:**
- [ ] User can delete their own video
- [ ] User cannot delete another user's video (security check)
- [ ] Video file is deleted from storage
- [ ] Database record is deleted
- [ ] UI updates after deletion
- [ ] Error handling works correctly

---

### 7. Video Management UI (Full Admin View)
**Status:** Not implemented  
**Priority:** 🟡 Medium  
**Estimated Effort:** 4-5 hours

**What needs to be done:**
- Create admin video list page showing all generated videos (all users)
- Add filtering/search by paper ID, date, status, user
- Show video metadata (duration, scenes, generation time)
- Add bulk delete functionality
- Add download links

**New endpoints needed:**
- `GET /admin/videos/` - List all videos (admin only)
- `DELETE /admin/videos/<paper_id>/` - Delete video (admin)
- `GET /admin/videos/<paper_id>/download/` - Download video (admin)

**Note:** This is separate from the user-facing "My Videos" delete feature (Task 5).

---

### 8. Error Monitoring & Logging
**Status:** Basic logging exists  
**Priority:** 🟡 Medium  
**Estimated Effort:** 3-4 hours

**What needs to be done:**
- Integrate error tracking (Sentry, Rollbar, or similar)
- Set up centralized logging
- Add structured logging with context
- Create error alerting rules
- Add performance monitoring

**Recommended tools:**
- **Sentry** - Error tracking (free tier available)
- **Railway Logs** - Built-in logging (already available)
- **Prometheus** - Metrics (if needed)

---

### 9. Rate Limiting & API Quota Management
**Status:** Not implemented  
**Priority:** 🟡 Medium  
**Estimated Effort:** 3-4 hours

**Why needed:**
- Gemini and Runway APIs have rate limits
- Need to prevent quota exhaustion
- Should queue requests when limits hit

**What needs to be done:**
- Implement rate limiting per user
- Add API quota tracking
- Queue requests when rate limit hit
- Add retry with exponential backoff
- Show rate limit status in UI

---

## 🔧 Low Priority (Nice to Have)

### 10. Email Verification
**Status:** Not implemented  
**Priority:** 🟢 Low  
**Estimated Effort:** 2-3 hours

**What needs to be done:**
- Send verification email on registration
- Add email verification endpoint
- Require verification before video generation
- Add resend verification email feature

---

### 11. Password Reset
**Status:** Not implemented  
**Priority:** 🟢 Low  
**Estimated Effort:** 2-3 hours

**What needs to be done:**
- Add "Forgot Password" link
- Implement password reset flow
- Send reset email with token
- Add reset password form

---

### 12. User Profiles
**Status:** Not implemented  
**Priority:** 🟢 Low  
**Estimated Effort:** 3-4 hours

**What needs to be done:**
- Create user profile model
- Add profile page
- Allow editing profile information
- Show user statistics (videos generated, etc.)

---

### 13. Django Admin Configuration
**Status:** Basic admin, not customized  
**Priority:** 🟢 Low  
**Estimated Effort:** 1-2 hours

**What needs to be done:**
- Register custom models in admin
- Add useful admin actions
- Customize admin interface
- Add filters and search

---

## 📚 Documentation Tasks

### 14. Deployment Guide
**Status:** Partial (Railway setup exists)  
**Priority:** 🟡 Medium  
**Estimated Effort:** 2-3 hours

**What needs to be done:**
- Complete Railway deployment guide
- Add step-by-step setup instructions
- Document environment variables
- Add troubleshooting section
- Include database migration steps

---

### 15. Architecture Documentation
**Status:** Not created  
**Priority:** 🟢 Low  
**Estimated Effort:** 2-3 hours

**What needs to be done:**
- Create system architecture diagram
- Document data flow
- Explain component interactions
- Add API design decisions

---

## 🧪 Testing & Quality

### 16. Add Unit Tests
**Status:** No tests exist  
**Priority:** 🟡 Medium  
**Estimated Effort:** 6-8 hours

**What needs to be done:**
- Set up pytest or Django test framework
- Write tests for pipeline steps
- Add API endpoint tests
- Test authentication flows
- Add integration tests

---

### 17. Real-Time Status Updates (WebSockets/SSE)
**Status:** Not implemented  
**Priority:** 🟢 Low (Nice to Have)  
**Estimated Effort:** 4-6 hours

**Current approach:**
- JavaScript polls status endpoint every 3 seconds
- Works but not optimal for real-time updates

**Better approach:**
- Use WebSockets or Server-Sent Events (SSE) for real-time updates
- Push status updates to client when they occur
- No polling needed

**What needs to be done:**
- Choose technology (WebSockets via Django Channels, or SSE)
- Implement real-time update endpoint
- Update frontend to use WebSocket/SSE connection
- Handle connection errors gracefully

**Options:**
1. **Server-Sent Events (SSE)** - Simpler, one-way (server → client)
2. **WebSockets (Django Channels)** - Full bidirectional, more complex

**Benefits:**
- ✅ Real-time updates (no delay)
- ✅ Less server load (no polling)
- ✅ Better user experience
- ✅ More efficient

**Action items:**
- [ ] Choose WebSockets vs SSE
- [ ] Implement real-time update endpoint
- [ ] Update frontend JavaScript
- [ ] Test connection handling
- [ ] Test with multiple concurrent users

---

### 18. Error Handling Improvements
**Status:** Basic error handling  
**Priority:** 🟡 Medium  
**Estimated Effort:** 3-4 hours

**What needs to be done:**
- Classify errors (transient vs. fatal)
- Implement exponential backoff
- Add better error messages
- Improve user-facing error pages

---

## 📊 Progress Tracking

### In Progress 🚧
- [ ] **Fix missing video download link on status page (CRITICAL - users can't access videos)**
- [ ] **Cloud storage integration (CRITICAL - blocking production)**
- [ ] **Fix progress tracking - implement real-time pipeline output parsing**
- [ ] Celery production deployment (Redis setup on Railway)
- [ ] File upload processing (currently fails - uses filename as PubMed ID)

### Planned 📅
- [ ] Add video deletion to "My Videos" page
- [ ] Video management UI enhancements (admin view, bulk operations)
- [ ] Error monitoring (Sentry)
- [ ] Rate limiting
- [ ] Real-time status updates (WebSockets/SSE)
- [ ] Email verification
- [ ] Password reset
- [ ] User profiles
- [ ] Comprehensive testing

---

## 🎯 Recommended Implementation Order

**Sprint 1 (Production Readiness - URGENT):**
1. 🔴 **Fix missing video download link on status page (CRITICAL - DO THIS FIRST)**
2. 🔴 **Fix progress tracking - real-time pipeline output parsing (CRITICAL)**
3. 🔴 **Cloud storage integration (CRITICAL - DO THIS NEXT)**
4. Celery production deployment (Redis setup on Railway)
5. Complete file upload feature

**Sprint 2 (Core Features):**
5. Add video deletion to "My Videos" page
6. Video management UI enhancements (admin view, bulk operations)
7. Error monitoring (Sentry)
8. Rate limiting

**Sprint 3 (Polish):**
9. Email verification
10. Password reset
11. Real-time status updates (WebSockets/SSE)
12. Comprehensive testing

---

## 📝 Notes

- **Current Branch:** `main`
- **Deployment:** Railway (configured, needs production setup)
- **Database:** SQLite locally, PostgreSQL on Railway
- **Storage:** ⚠️ **Local filesystem - CRITICAL: Videos are lost on Railway container restarts. Cloud storage must be implemented before production deployment.**

---

## 🤝 Contributing

When working on these tasks:
1. Create a feature branch
2. Implement changes
3. Test thoroughly
4. Update documentation
5. Create pull request
6. Get code review
7. Merge to `main`

---

## 📞 Questions or Issues?

If you encounter issues or have questions about any of these next steps:
- Check existing documentation in `docs/` folder
- Review code comments and TODOs
- Test locally before deploying
- Document any blockers or decisions

---

**Last Review:** Check this document monthly and update priorities based on project needs.

