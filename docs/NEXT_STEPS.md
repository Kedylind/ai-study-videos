# Hidden Hill - Next Steps & Roadmap

**Last Updated:** 2025-01-27  
**Project Status:** Development Complete, Production-Ready Improvements Needed

---

## 🎯 Project Overview

Hidden Hill is a Django web application that converts scientific papers into engaging social media videos (TikTok/Instagram Reels format). The system uses AI (Gemini for text/audio, Runway for video) to automatically generate educational content from PubMed papers.

**Current Status:**
- ✅ Core pipeline fully functional
- ✅ Web UI and REST API working
- ✅ User authentication implemented
- ✅ Celery task queue integrated (tasks survive server restarts)
- ✅ Access control implemented (access code required)
- ⚠️ Production deployment needs improvements

---

## 🚀 High Priority (Production Readiness)

### 1. Add Database Models for Job Tracking + User Video Archive
**Status:** Not implemented  
**Priority:** 🔴 Critical  
**Estimated Effort:** 4-5 hours

**GOAL:** 
1. Show a **reliable, real-time progress bar** while Celery processes video generation in the background
2. Create a **"My Videos" archive page** where each logged-in user can see all videos they've generated (user-specific, private to them)

**Problem:**
- Current implementation uses file-based status tracking (checking file existence)
- Complex status checking logic with multiple fallback methods (400+ lines in `_get_pipeline_progress()`)
- No way to query all videos or track user history
- Doesn't scale to multiple servers
- No user association with generated videos
- Progress bar is unreliable because it depends on file system checks
- Users cannot see their video generation history

**Solution: Database Models + Real-Time Progress Updates**
- Create `VideoGenerationJob` model to track each generation in the database
- Store status, progress, errors in database (single source of truth)
- Link jobs to users for history tracking
- Update progress in real-time as Celery task runs
- Create "My Videos" page showing user's video history

---

## Implementation Steps

### Step 1: Create Database Model

**File:** `web/models.py` (create this file if it doesn't exist)

Create a `VideoGenerationJob` model with these exact fields:

```python
from django.db import models
from django.contrib.auth.models import User

class VideoGenerationJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_jobs')
    paper_id = models.CharField(max_length=255, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percent = models.IntegerField(default=0)
    current_step = models.CharField(max_length=100, null=True, blank=True)
    error_message = models.TextField(blank=True)
    error_type = models.CharField(max_length=50, blank=True)
    task_id = models.CharField(max_length=255, unique=True)  # Celery task ID
    final_video_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.paper_id} - {self.status}"
```

**Action:** Create `web/models.py` with the model above, then run:
```bash
python manage.py makemigrations
python manage.py migrate
```

---

### Step 2: Update Celery Task to Save Progress to Database

**File:** `web/tasks.py`

**What to do:**
1. Import the model: `from web.models import VideoGenerationJob`
2. At the START of `generate_video_task()`:
   - Get or create the `VideoGenerationJob` record
   - Set initial status to 'running', progress_percent=0
   - Save the task_id from `self.request.id`
   - Link to user (you'll need to pass user_id as a parameter - see Step 3)

3. As the pipeline runs, update the job record with progress:
   - When each step completes, update `current_step` and `progress_percent`
   - Pipeline steps are: `fetch-paper` (20%), `generate-script` (40%), `generate-audio` (60%), `generate-videos` (80%), `add-captions` (100%)
   - Use `VideoGenerationJob.objects.filter(task_id=task_id).update(...)` to update

4. On SUCCESS:
   - Set `status='completed'`, `progress_percent=100`, `completed_at=now()`
   - Set `final_video_path` to the video file path

5. On FAILURE:
   - Set `status='failed'`
   - Save `error_message` and `error_type` from error classification

**Key requirement:** Update progress at least once per pipeline step. The frontend polls every 3 seconds, so updates should happen frequently enough for smooth progress bar updates.

**Example update pattern:**
```python
# In generate_video_task(), after each pipeline step:
job = VideoGenerationJob.objects.get(task_id=self.request.id)
job.current_step = "generate-script"
job.progress_percent = 40
job.save(update_fields=['current_step', 'progress_percent', 'updated_at'])
```

---

### Step 3: Update Views to Create Job Record

**File:** `web/views.py`

**In `upload_paper()` view:**
1. When user submits paper (after access code validation):
   - Create `VideoGenerationJob` record BEFORE starting Celery task
   - Set `user=request.user`, `paper_id=pmid`, `status='pending'`
   - Save the job to get the ID
   - Pass `user_id=request.user.id` to the Celery task

2. Update `_start_pipeline_async()` to accept `user_id` parameter:
   ```python
   def _start_pipeline_async(pmid: str, output_dir: Path, user_id: int):
       task = generate_video_task.delay(pmid, str(output_dir), user_id)
       # ... rest of function
   ```

**In `pipeline_status()` view:**
1. Replace the complex `_get_pipeline_progress()` logic with a simple database query:
   ```python
   try:
       job = VideoGenerationJob.objects.get(paper_id=pmid, user=request.user)
       progress = {
           "status": job.status,
           "current_step": job.current_step,
           "progress_percent": job.progress_percent,
           "completed_steps": _get_completed_steps_from_progress(job.progress_percent),
           "error": job.error_message if job.status == 'failed' else None,
           "error_type": job.error_type if job.status == 'failed' else None,
       }
   except VideoGenerationJob.DoesNotExist:
       # Fallback to old file-based method (for backwards compatibility)
       progress = _get_pipeline_progress(output_dir)
   ```

2. Keep `_get_pipeline_progress()` as a fallback for old jobs, but mark it as deprecated.

**In `api_start_generation()` view:**
- Similar changes: create job record, pass user_id to task
- For API calls, you may need to handle anonymous users differently (or require authentication)

---

### Step 4: Create "My Videos" Archive Page

**New view:** `web/views.py`

Add a new view function:
```python
@login_required
def my_videos(request):
    """Display all videos generated by the current user."""
    jobs = VideoGenerationJob.objects.filter(user=request.user).order_by('-created_at')
    
    # Add video URL and metadata for each job
    videos = []
    for job in jobs:
        video_data = {
            'job': job,
            'paper_id': job.paper_id,
            'status': job.status,
            'progress_percent': job.progress_percent,
            'created_at': job.created_at,
            'completed_at': job.completed_at,
            'video_url': None,
            'has_video': False,
        }
        
        # Check if video file exists
        if job.status == 'completed' and job.final_video_path:
            video_path = Path(settings.MEDIA_ROOT) / job.paper_id / "final_video.mp4"
            if video_path.exists():
                video_data['has_video'] = True
                video_data['video_url'] = reverse('serve_video', args=[job.paper_id])
        
        videos.append(video_data)
    
    return render(request, 'my_videos.html', {'videos': videos})
```

**New template:** `web/templates/my_videos.html`

Create a template that:
- Shows a list/grid of all user's videos
- Displays paper_id, status, creation date
- Shows progress bar for in-progress videos
- Shows video thumbnail/player for completed videos
- Links to status page for running videos
- Links to result page for completed videos
- Shows error message for failed videos
- Has a "Generate New Video" button linking to `/upload/`

**New URL:** `web/urls.py`

Add:
```python
path('my-videos/', my_videos, name='my_videos'),
```

**Add navigation link:** Update base template or navigation to include "My Videos" link (only visible when logged in).

---

### Step 5: Update API Endpoints

**File:** `web/views.py`

Update `api_start_generation()`:
- Create `VideoGenerationJob` record (may need to handle API authentication differently)
- Pass user info to Celery task

Update `api_status()`:
- Query database instead of file system
- Return same JSON format for backwards compatibility

---

## Testing Checklist

After implementation, verify:

- [ ] **Progress Bar Works:**
  - Start a video generation
  - Watch the status page - progress bar should update smoothly (every 3 seconds)
  - Progress should go: 0% → 20% → 40% → 60% → 80% → 100%
  - Each step name should appear as it progresses

- [ ] **Database Updates:**
  - Check database after starting a job - record should exist
  - Check database during processing - progress_percent should update
  - Check database after completion - status should be 'completed', completed_at set

- [ ] **My Videos Page:**
  - Log in as User A, generate a video
  - Log in as User B, generate a different video
  - User A's "My Videos" should only show User A's video
  - User B's "My Videos" should only show User B's video
  - Both users should see their own videos, not each other's

- [ ] **Error Handling:**
  - Test with invalid PubMed ID - should show error in database
  - Failed jobs should appear in "My Videos" with error message
  - Status should be 'failed' in database

- [ ] **Backwards Compatibility:**
  - Old file-based jobs should still work (fallback)
  - New jobs use database, old jobs use file system

---

## Files to Modify

1. **`web/models.py`** - Create new file with `VideoGenerationJob` model
2. **`web/tasks.py`** - Update `generate_video_task()` to save/update database records
3. **`web/views.py`** - Update `upload_paper()`, `pipeline_status()`, `api_start_generation()`, add `my_videos()` view
4. **`web/urls.py`** - Add route for `my_videos`
5. **`web/templates/my_videos.html`** - Create new template
6. **`web/templates/base.html`** or navigation template - Add "My Videos" link

---

## Expected End Result

**For Progress Bar:**
- User submits paper → redirected to status page
- Status page shows progress bar that updates every 3 seconds
- Progress bar shows: "20% - Fetching paper..." → "40% - Generating script..." → etc.
- When complete, automatically redirects to result page
- All progress data comes from database (fast, reliable)

**For My Videos Archive:**
- User can navigate to `/my-videos/` (link in navigation)
- Page shows all videos they've generated, newest first
- Each video shows: paper_id, status, date created, thumbnail/preview
- Clicking a video takes them to the result/status page
- Only shows videos for the logged-in user (private)
- Shows in-progress videos with live progress
- Shows failed videos with error messages

---

### 2. Celery Production Deployment
**Status:** ✅ Implemented locally (needs production setup)  
**Priority:** 🟠 High  
**Estimated Effort:** 1 hour

**What needs to be done:**
- Set up Redis service on Railway
- Configure `CELERY_BROKER_URL` environment variable
- Test that tasks survive server restart in production
- Verify error handling works in production

**Action items:**
- [ ] Set up Redis service on Railway
- [ ] Configure `CELERY_BROKER_URL` environment variable
- [ ] Test that tasks survive server restart (production)
- [ ] Test error handling with invalid inputs (production)

---

### 3. Complete File Upload Feature
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

### 4. Secrets Management
**Status:** Mostly complete (needs production verification)  
**Priority:** 🟡 Medium  
**Estimated Effort:** 30 minutes (verification)

**What needs to be done:**
- Create `.env.example` template file
- Document all required environment variables
- Set up secure secret storage for production (Railway secrets manager)
- Remove any hardcoded secrets (if any)
- Add secret rotation documentation

**Required secrets:**
- `GEMINI_API_KEY` - Google Gemini API
- `RUNWAYML_API_SECRET` - Runway ML API
- `SECRET_KEY` - Django secret key
- `DATABASE_URL` - PostgreSQL connection string (production)
- `CELERY_BROKER_URL` - Redis connection (when Celery is integrated)
- `VIDEO_ACCESS_CODE` - Access code for video generation (new)

**Action items:**
- [x] Create `.env.example` with all required variables
- [x] Document secret management in deployment guide (in .env.example)
- [ ] Verify no secrets in code or git history
- [ ] Set up Railway environment variables
- [x] Document code distribution process for `VIDEO_ACCESS_CODE` (in .env.example)

---

## 📋 Medium Priority (Feature Enhancements)

### 5. Cloud Storage Integration (S3/GCS)
**Status:** Not implemented  
**Priority:** 🟡 Medium  
**Estimated Effort:** 4-6 hours

**Why needed:**
- Current setup uses local filesystem (`media/` directory)
- Won't work in multi-host deployments
- Files lost on container restart

**What needs to be done:**
- Choose storage provider (AWS S3, Google Cloud Storage, or Railway volumes)
- Implement storage backend for Django media files
- Update pipeline to upload artifacts to cloud storage
- Update status/result endpoints to use signed URLs
- Add storage configuration to settings

**Options:**
1. **Railway Volumes** (easiest) - Persistent storage on Railway
2. **AWS S3** - Most flexible, requires AWS account
3. **Google Cloud Storage** - Good if already using GCP

---

### 6. Video Management UI
**Status:** Not implemented  
**Priority:** 🟡 Medium  
**Estimated Effort:** 4-5 hours

**What needs to be done:**
- Create video list page showing all generated videos
- Add user association (who generated which video)
- Implement delete functionality
- Add download links
- Add filtering/search by paper ID, date, status
- Show video metadata (duration, scenes, generation time)

**New endpoints needed:**
- `GET /videos/` - List all videos
- `DELETE /videos/<paper_id>/` - Delete video
- `GET /videos/<paper_id>/download/` - Download video

---

### 7. Error Monitoring & Logging
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

### 8. Rate Limiting & API Quota Management
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

### 9. Email Verification
**Status:** Not implemented  
**Priority:** 🟢 Low  
**Estimated Effort:** 2-3 hours

**What needs to be done:**
- Send verification email on registration
- Add email verification endpoint
- Require verification before video generation
- Add resend verification email feature

---

### 10. Password Reset
**Status:** Not implemented  
**Priority:** 🟢 Low  
**Estimated Effort:** 2-3 hours

**What needs to be done:**
- Add "Forgot Password" link
- Implement password reset flow
- Send reset email with token
- Add reset password form

---

### 11. User Profiles
**Status:** Not implemented  
**Priority:** 🟢 Low  
**Estimated Effort:** 3-4 hours

**What needs to be done:**
- Create user profile model
- Add profile page
- Allow editing profile information
- Show user statistics (videos generated, etc.)

---

### 12. Django Admin Configuration
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

### 13. Deployment Guide
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

### 14. Architecture Documentation
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

### 15. Add Unit Tests
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

### 16. Real-Time Status Updates (WebSockets/SSE)
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

### 17. Error Handling Improvements
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

### Completed ✅
- [x] Core video generation pipeline
- [x] Django web application
- [x] User authentication
- [x] REST API endpoints
- [x] Progress tracking
- [x] Basic error handling
- [x] Railway deployment configuration
- [x] Celery task queue integration (local testing complete)
- [x] Access control with access code validation
- [x] Error handling and user feedback in Celery tasks
- [x] Secrets management documentation (.env.example)

### In Progress 🚧
- [ ] Database models for job tracking
- [ ] Celery production deployment (Redis setup on Railway)
- [ ] File upload processing (currently fails - uses filename as PubMed ID)

### Planned 📅
- [ ] Database models for job tracking
- [ ] Cloud storage integration
- [ ] Video management UI
- [ ] Error monitoring
- [ ] Rate limiting
- [ ] Real-time status updates (WebSockets/SSE)
- [ ] Email verification
- [ ] Password reset
- [ ] User profiles
- [ ] Comprehensive testing

---

## 🎯 Recommended Implementation Order

**Sprint 1 (Production Readiness):**
1. Add database models for job tracking (critical for scalability)
2. ✅ Celery production deployment (Redis setup)
3. Complete file upload feature
4. ✅ Secrets management (mostly complete)

**Sprint 2 (Core Features):**
5. Cloud storage integration
6. Video management UI (enabled by database models)
7. Error monitoring

**Sprint 3 (Polish):**
8. Rate limiting
9. Email verification
10. Password reset
11. Real-time status updates (WebSockets/SSE)
12. Testing

---

## 📝 Notes

- **Current Branch:** `main`
- **Deployment:** Railway (configured, needs production setup)
- **Database:** SQLite locally, PostgreSQL on Railway
- **Storage:** Local filesystem (needs cloud storage for production)

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

