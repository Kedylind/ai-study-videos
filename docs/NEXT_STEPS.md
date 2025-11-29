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
- 🔴 **BLOCKER:** Cloud storage (Cloudflare R2) not implemented - videos lost on Railway container restarts

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

### 2. 🔴 CRITICAL: Implement Cloud Storage with Cloudflare R2
**Status:** Not implemented  
**Priority:** 🔴 **CRITICAL - BLOCKING PRODUCTION**  
**Estimated Effort:** 3-4 hours

**WHY THIS IS CRITICAL:**
- **Current Problem:** Videos are saved to local filesystem (`MEDIA_ROOT = BASE_DIR / "media"`)
- **Railway Issue:** Railway uses **ephemeral filesystem** - all files are **LOST** on:
  - Container restart
  - Deployment
  - Service restart
  - Scaling events
- **Impact:** Users generate videos → videos disappear after any restart → **unusable in production**
- **This must be fixed before deploying to production!**

**Why Cloudflare R2:**
- ✅ **No egress fees** - Free downloads (perfect for video hosting)
- ✅ **S3-compatible API** - Works with `django-storages` out of the box
- ✅ **Free tier:** 10 GB storage, 1M operations/month
- ✅ **Low cost:** $0.015/GB/month storage
- ✅ **Fast global CDN** - Videos load quickly worldwide
- ✅ **Simple setup** - Minimal code changes required

---

## Step-by-Step Implementation Guide

### Step 1: Set Up Cloudflare R2 Account and Bucket

1. **Create Cloudflare Account:**
   - Go to https://dash.cloudflare.com/sign-up
   - Sign up for a free account (or log in if you have one)

2. **Enable R2:**
   - In Cloudflare dashboard, go to **R2** (in left sidebar)
   - Click **"Create bucket"**
   - Name it: `hidden-hill-videos` (or your preferred name)
   - Choose a location (closest to your users)
   - Click **"Create bucket"**

3. **Create API Token:**
   - Go to **R2** → **Manage R2 API Tokens**
   - Click **"Create API token"**
   - Name it: `hidden-hill-storage`
   - Permissions: **Object Read & Write**
   - Bucket: Select your bucket (`hidden-hill-videos`)
   - Click **"Create API token"**
   - **IMPORTANT:** Copy the **Access Key ID** and **Secret Access Key** - you'll need these!

4. **Get Your Account ID:**
   - In Cloudflare dashboard, go to **R2** → **Overview**
   - Your **Account ID** is shown at the top
   - Note this down - you'll need it for the endpoint URL

5. **Get Endpoint URL:**
   - Format: `https://<account-id>.r2.cloudflarestorage.com`
   - Example: `https://abc123def456.r2.cloudflarestorage.com`
   - Replace `<account-id>` with your actual Account ID

---

### Step 2: Install Required Dependencies

**File:** `requirements.txt`

**Add these lines:**
```
django-storages[boto3]==1.14.2
boto3==1.34.0
```

**Then run:**
```bash
pip install django-storages[boto3] boto3
```

---

### Step 3: Update Django Settings

**File:** `config/settings.py`

**Find the media files section (around line 147-152) and replace it with:**

```python
# Media files for generated outputs (videos, audio, metadata)
# Cloud Storage Configuration (Cloudflare R2)
USE_CLOUD_STORAGE = os.getenv("USE_CLOUD_STORAGE", "False") == "True"

if USE_CLOUD_STORAGE:
    # Cloudflare R2 (S3-compatible)
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")  # R2 endpoint
    AWS_S3_REGION_NAME = "auto"  # R2 uses "auto"
    
    # Storage settings
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    
    # Security & performance
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = "public-read"  # Videos are public (or use "private" for signed URLs)
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",  # 1 day cache
    }
    
    # Media files will be stored in R2
    # MEDIA_URL will be automatically set to R2 URL
    MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.r2.cloudflarestorage.com/"
else:
    # Fallback to local storage (for development)
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"
```

**Important Notes:**
- The `USE_CLOUD_STORAGE` flag allows you to toggle between local and cloud storage
- In development, set `USE_CLOUD_STORAGE=False` (or don't set it) to use local storage
- In production (Railway), set `USE_CLOUD_STORAGE=True` to use R2

---

### Step 4: Update Model to Use FileField

**File:** `web/models.py`

**Find the `VideoGenerationJob` model and update the `final_video_path` field:**

**Current code (around line 23):**
```python
final_video_path = models.CharField(max_length=500, blank=True)
```

**Replace with:**
```python
from django.core.files.storage import default_storage

class VideoGenerationJob(models.Model):
    # ... existing fields ...
    
    # Store video in cloud storage (R2) or local filesystem
    final_video = models.FileField(
        upload_to='videos/%Y/%m/%d/',  # Organize by date: videos/2025/01/28/
        blank=True,
        null=True,
        storage=default_storage,  # Will use R2 if USE_CLOUD_STORAGE=True, else local
    )
    
    # Keep final_video_path for backward compatibility during migration
    # This will store the storage path (e.g., "videos/2025/01/28/final_video.mp4")
    final_video_path = models.CharField(max_length=500, blank=True)
```

**Why both fields?**
- `final_video` (FileField) - Django's proper way to handle files, works with cloud storage
- `final_video_path` (CharField) - Keep for backward compatibility, stores the storage path

---

### Step 5: Update Celery Task to Upload to Cloud Storage

**File:** `web/tasks.py`

**Find the completion logic in `generate_video_task()` (around line 518-535) and update it:**

**Current code:**
```python
final_video = output_path / "final_video.mp4"

if return_code == 0 and final_video.exists():
    task_result["status"] = "completed"
    logger.info(f"Video generation completed successfully for {pmid}")
    
    # Update job record
    try:
        job.final_video_path = str(final_video)
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'progress_percent', 'current_step', 'final_video_path', 'completed_at', 'updated_at'])
    except Exception as e:
        logger.warning(f"Failed to update job record on completion: {e}")
```

**Replace with:**
```python
from django.core.files import File
from django.core.files.storage import default_storage

final_video = output_path / "final_video.mp4"

if return_code == 0 and final_video.exists():
    task_result["status"] = "completed"
    logger.info(f"Video generation completed successfully for {pmid}")
    
    # Upload to cloud storage (R2) or save locally
    try:
        # Generate unique filename with date organization
        from datetime import datetime
        date_path = datetime.now().strftime('%Y/%m/%d')
        video_filename = f"{pmid}/final_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        # Open the local file and upload to cloud storage
        with open(final_video, 'rb') as f:
            django_file = File(f, name=video_filename)
            job.final_video.save(video_filename, django_file, save=False)
            job.final_video_path = job.final_video.name  # Store the storage path
            job.status = 'completed'
            job.completed_at = timezone.now()
            job.save(update_fields=['final_video', 'final_video_path', 'status', 'progress_percent', 'current_step', 'completed_at', 'updated_at'])
        
        logger.info(f"Video uploaded to cloud storage: {job.final_video.name}")
        
    except Exception as e:
        logger.error(f"Failed to upload video to cloud storage: {e}", exc_info=True)
        # Fallback: keep local path if cloud upload fails
        try:
            job.final_video_path = str(final_video)
            job.status = 'completed'
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'progress_percent', 'current_step', 'final_video_path', 'completed_at', 'updated_at'])
            logger.warning(f"Saved local path as fallback: {job.final_video_path}")
        except Exception as e2:
            logger.error(f"Failed to update job record on completion: {e2}", exc_info=True)
```

---

### Step 6: Update Views to Serve from Cloud Storage

**File:** `web/views.py`

**Find the `serve_video()` function (around line 1409) and update it:**

**Current code:**
```python
def serve_video(request, pmid: str):
    """Serve video file directly with proper headers."""
    output_dir = Path(settings.MEDIA_ROOT) / pmid
    final_video = output_dir / "final_video.mp4"
    
    if not final_video.exists():
        return HttpResponse("Video not found", status=404)
    
    try:
        with open(final_video, 'rb') as f:
            response = HttpResponse(f.read(), content_type='video/mp4')
            response['Content-Disposition'] = f'inline; filename="final_video.mp4"'
            response['Content-Length'] = final_video.stat().st_size
            return response
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error serving video: {e}", exc_info=True)
        return HttpResponse("Error serving video", status=500)
```

**Replace with:**
```python
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404

def serve_video(request, pmid: str):
    """Serve video file from cloud storage (R2) or local filesystem."""
    try:
        # Try to get from database first (cloud storage)
        from web.models import VideoGenerationJob
        
        # Get job record
        if request.user.is_authenticated:
            job = VideoGenerationJob.objects.filter(
                paper_id=pmid, 
                user=request.user
            ).first()
        else:
            job = VideoGenerationJob.objects.filter(paper_id=pmid).first()
        
        # If job has final_video FileField, serve from cloud storage
        if job and job.final_video:
            try:
                return FileResponse(
                    job.final_video.open('rb'),
                    content_type='video/mp4',
                    filename='final_video.mp4'
                )
            except Exception as e:
                logger.error(f"Error opening cloud storage file: {e}", exc_info=True)
        
        # Fallback: check local filesystem (for development or migration period)
        if settings.USE_CLOUD_STORAGE:
            # In production with cloud storage, if file not in cloud, it doesn't exist
            raise Http404("Video not found in cloud storage")
        else:
            # Local development fallback
            output_dir = Path(settings.MEDIA_ROOT) / pmid
            final_video = output_dir / "final_video.mp4"
            
            if final_video.exists():
                return FileResponse(
                    open(final_video, 'rb'),
                    content_type='video/mp4',
                    filename='final_video.mp4'
                )
        
        raise Http404("Video not found")
        
    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error serving video: {e}", exc_info=True)
        return HttpResponse("Error serving video", status=500)
```

---

### Step 7: Update Other Views That Check File Existence

**File:** `web/views.py`

**Update `pipeline_status()` and other functions that check `final_video.exists()`:**

**Find all instances of:**
```python
final_video = output_dir / "final_video.mp4"
if final_video.exists():
```

**Replace with:**
```python
# Check if video exists in cloud storage or local filesystem
final_video_exists = False
if settings.USE_CLOUD_STORAGE:
    # Check database for cloud storage
    try:
        from web.models import VideoGenerationJob
        job = VideoGenerationJob.objects.filter(paper_id=pmid).first()
        if job and job.final_video:
            final_video_exists = True
    except Exception:
        pass
else:
    # Check local filesystem
    final_video = output_dir / "final_video.mp4"
    final_video_exists = final_video.exists()
```

**Apply this pattern to:**
- `pipeline_status()` function
- `pipeline_result()` function
- `my_videos()` function
- Any other functions that check for video file existence

---

### Step 8: Set Railway Environment Variables

**In Railway Dashboard:**

1. Go to your project → **Variables** tab
2. Add these environment variables:

```
USE_CLOUD_STORAGE=True
AWS_ACCESS_KEY_ID=your_r2_access_key_id_here
AWS_SECRET_ACCESS_KEY=your_r2_secret_access_key_here
AWS_STORAGE_BUCKET_NAME=hidden-hill-videos
AWS_S3_ENDPOINT_URL=https://<your-account-id>.r2.cloudflarestorage.com
```

**Important:**
- Replace `<your-account-id>` with your actual Cloudflare Account ID
- Replace `hidden-hill-videos` with your actual bucket name
- Keep these values secret - never commit them to git!

---

### Step 9: Create and Run Database Migration

**Run these commands:**

```bash
# Create migration for model changes
python manage.py makemigrations

# Review the migration (should add final_video FileField)
# Then apply it
python manage.py migrate
```

**Migration will:**
- Add `final_video` FileField to `VideoGenerationJob` model
- Keep `final_video_path` for backward compatibility

---

### Step 10: Clean Up Railway Volume Code (IMPORTANT!)

**Delete all Railway volume-related code:**

1. **Delete from `web/views.py`:**
   - Remove `debug_media_path()` function (entire function, around line 231-315)
   - Remove `test_volume_write()` function (entire function, around line 339-545)
   - Remove import: `test_volume_write_task` from line 22

2. **Delete from `web/tasks.py`:**
   - Remove `test_volume_write_task()` function (entire function, around line 738-797)

3. **Delete from `web/urls.py`:**
   - Remove: `debug_media_path, test_volume_write` from imports (line 4)
   - Remove: `path("debug-media/", debug_media_path, name="debug_media"),` (line 12)
   - Remove: `path("test-volume-write/", test_volume_write, name="test_volume_write"),` (line 13)

4. **Delete documentation file:**
   - Delete: `docs/RAILWAY_VOLUMES_SETUP.md` (if it exists)

5. **Update `config/settings.py`:**
   - Remove comments about Railway volumes (around line 149-151)
   - Keep the media configuration clean

**After cleanup, verify:**
- No references to "railway", "volume", "test_volume" in code
- All imports are correct
- URLs file doesn't have broken routes

---

## Testing Instructions

### Test 1: Local Development (Cloud Storage Disabled)

1. **Set environment:**
   ```bash
   # In .env file or environment
   USE_CLOUD_STORAGE=False
   ```

2. **Generate a video:**
   - Start Django server: `python manage.py runserver`
   - Log in and generate a video
   - Wait for completion

3. **Verify:**
   - Video should be saved to `media/<pmid>/final_video.mp4` (local)
   - Video should be accessible via `/video/<pmid>/`
   - Database should have `final_video_path` set

### Test 2: Local Development (Cloud Storage Enabled)

1. **Set environment:**
   ```bash
   USE_CLOUD_STORAGE=True
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   AWS_STORAGE_BUCKET_NAME=your-bucket
   AWS_S3_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
   ```

2. **Generate a video:**
   - Start Django server
   - Log in and generate a video
   - Wait for completion

3. **Verify:**
   - Check Cloudflare R2 dashboard - video should be in bucket
   - Video should be accessible via `/video/<pmid>/`
   - Database should have `final_video` FileField populated
   - `final_video_path` should contain the storage path

### Test 3: Production (Railway with R2)

1. **Set Railway environment variables** (Step 8)

2. **Deploy to Railway:**
   - Push code to git
   - Railway will auto-deploy

3. **Generate a video:**
   - Go to Railway app URL
   - Log in and generate a video
   - Wait for completion

4. **Verify:**
   - Check Cloudflare R2 dashboard - video should be in bucket
   - Video should be accessible via `/video/<pmid>/`
   - Restart Railway service - video should still be accessible ✅
   - Database should have `final_video` FileField populated

### Test 4: Video Recovery (Optional)

If you have videos on the Celery volume that need to be recovered:

1. **Create recovery task** (temporary):
   ```python
   @shared_task
   def recover_videos_to_r2(pmid: str = None):
       """Recover videos from local filesystem to R2."""
       from django.core.files import File
       from web.models import VideoGenerationJob
       
       media_root = Path(settings.MEDIA_ROOT)
       if pmid:
           video_dirs = [media_root / pmid] if (media_root / pmid).exists() else []
       else:
           video_dirs = [d for d in media_root.iterdir() 
                        if d.is_dir() and (d / "final_video.mp4").exists()]
       
       for video_dir in video_dirs:
           final_video = video_dir / "final_video.mp4"
           if not final_video.exists():
               continue
           
           try:
               job = VideoGenerationJob.objects.filter(paper_id=video_dir.name).first()
               if job and not job.final_video:
                   video_filename = f"{video_dir.name}/final_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                   with open(final_video, 'rb') as f:
                       django_file = File(f, name=video_filename)
                       job.final_video.save(video_filename, django_file, save=False)
                       job.final_video_path = job.final_video.name
                       job.save()
           except Exception as e:
               logger.error(f"Failed to recover {video_dir.name}: {e}")
   ```

2. **Run recovery:**
   ```python
   from web.tasks import recover_videos_to_r2
   recover_videos_to_r2.delay()  # Recover all videos
   # Or: recover_videos_to_r2.delay("PMC10979640")  # Recover specific video
   ```

---

## Testing Checklist

- [ ] Installed `django-storages[boto3]` and `boto3`
- [ ] Created Cloudflare R2 bucket
- [ ] Created R2 API token
- [ ] Updated `config/settings.py` with R2 configuration
- [ ] Updated `web/models.py` to add `final_video` FileField
- [ ] Updated `web/tasks.py` to upload videos to R2
- [ ] Updated `web/views.py` to serve videos from R2
- [ ] Created and ran database migration
- [ ] Set Railway environment variables
- [ ] Deleted all Railway volume code (debug endpoints, test functions)
- [ ] Tested locally with `USE_CLOUD_STORAGE=False` (local storage)
- [ ] Tested locally with `USE_CLOUD_STORAGE=True` (R2 storage)
- [ ] Tested on Railway production
- [ ] Verified video persists after Railway service restart
- [ ] Verified video is accessible via `/video/<pmid>/`
- [ ] Verified "My Videos" page shows videos correctly
- [ ] Checked Cloudflare R2 dashboard - videos are in bucket
- [ ] Verified database has `final_video` FileField populated

---

## Troubleshooting

### Problem: "No module named 'storages'"

**Fix:**
```bash
pip install django-storages[boto3] boto3
# Add to requirements.txt and redeploy
```

### Problem: "Access Denied" or "Invalid credentials"

**Fix:**
- Verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are correct
- Check that API token has "Object Read & Write" permissions
- Verify bucket name matches `AWS_STORAGE_BUCKET_NAME`

### Problem: "Endpoint URL incorrect"

**Fix:**
- Verify `AWS_S3_ENDPOINT_URL` format: `https://<account-id>.r2.cloudflarestorage.com`
- Replace `<account-id>` with your actual Cloudflare Account ID
- No trailing slash!

### Problem: Videos not uploading to R2

**Check:**
1. Is `USE_CLOUD_STORAGE=True` set?
2. Are all environment variables set correctly?
3. Check Celery worker logs for upload errors
4. Verify bucket name and permissions

### Problem: Videos not accessible after upload

**Check:**
1. Is `AWS_DEFAULT_ACL = "public-read"` set? (for public videos)
2. Or use signed URLs if videos should be private
3. Check that `serve_video()` function is updated correctly

---

## Expected Result

After completing these steps:

✅ Videos are uploaded to Cloudflare R2 automatically  
✅ Videos persist across container restarts (stored in cloud)  
✅ Videos persist across deployments  
✅ Videos are accessible via `/video/<pmid>/` endpoint  
✅ Database records have `final_video` FileField populated  
✅ "My Videos" page shows accessible videos  
✅ No Railway volume code remaining  
✅ Works in both development (local) and production (R2)  

---

## Cost Estimate

**For 100 videos (~5 GB total):**
- Storage: ~$0.075/month
- Operations: Free (within free tier)
- Egress: **FREE** (no download fees!)
- **Total: ~$0.075/month** 🎉

**For 1000 videos (~50 GB total):**
- Storage: ~$0.75/month
- Operations: Free (within free tier)
- Egress: **FREE**
- **Total: ~$0.75/month** 🎉

---

## Files Modified

1. **`requirements.txt`** - Add `django-storages[boto3]` and `boto3`
2. **`config/settings.py`** - Add R2 configuration
3. **`web/models.py`** - Add `final_video` FileField
4. **`web/tasks.py`** - Update to upload to R2
5. **`web/views.py`** - Update to serve from R2, remove volume test code
6. **`web/urls.py`** - Remove volume test routes
7. **Database migration** - Add `final_video` field

**Files Deleted:**
- `docs/RAILWAY_VOLUMES_SETUP.md` (if exists)

---

## Next Steps After Implementation

1. **Monitor R2 usage:**
   - Check Cloudflare dashboard for storage usage
   - Monitor API operations
   - Set up billing alerts if needed

2. **Consider cleanup strategy:**
   - Videos will accumulate in R2
   - May want to implement video deletion feature
   - Or set up automatic cleanup of old videos

3. **Optional: Custom domain:**
   - R2 supports custom domains
   - Can set up `videos.yourdomain.com` for video URLs
   - Requires Cloudflare DNS setup

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
- **Storage:** ⚠️ **Local filesystem - CRITICAL: Videos are lost on Railway container restarts. Cloudflare R2 cloud storage must be implemented before production deployment.**

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

