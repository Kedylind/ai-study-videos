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
- ✅ Real-time progress tracking working
- 🔴 **BLOCKER:** Cloud storage not implemented - videos lost on Railway container restarts

---

## 🚀 High Priority (Production Readiness)

### 1. ⚠️ CRITICAL: Implement Persistent Video Storage with Railway Volumes
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

### 2. ✅ COMPLETED: Database Models for Job Tracking + User Video Archive
**Status:** ✅ **COMPLETED**  
**Priority:** ~~🔴 Critical~~ (Done!)

**What was implemented:**
- ✅ `VideoGenerationJob` model created in `web/models.py`
- ✅ Database migrations created and run
- ✅ Celery task updates database with progress (`web/tasks.py`)
- ✅ Views use database for status checking (`web/views.py`)
- ✅ "My Videos" page implemented (`/my-videos/`)
- ✅ Real-time progress bar working
- ✅ User-specific video archive working

**Files created/modified:**
- ✅ `web/models.py` - VideoGenerationJob model
- ✅ `web/tasks.py` - Database updates during pipeline execution
- ✅ `web/views.py` - Database queries, my_videos() view
- ✅ `web/templates/my_videos.html` - User video archive template
- ✅ `web/urls.py` - Added my-videos route

**Result:**
- Progress bar now updates reliably from database
- Users can see all their generated videos at `/my-videos/`
- Status checking is simple and fast (database queries)
- User history tracking working

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

### 3. Celery Production Deployment
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

### 4. Complete File Upload Feature
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

### 5. Secrets Management
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
- [x] Basic error handling
- [x] Railway deployment configuration
- [x] Celery task queue integration (local testing complete)
- [x] Access control with access code validation
- [x] Error handling and user feedback in Celery tasks
- [x] Secrets management documentation (.env.example)
- [x] **Database models for job tracking (VideoGenerationJob model)**
- [x] **Real-time progress tracking from database**
- [x] **"My Videos" archive page (/my-videos/)**
- [x] **User-specific video history**

### In Progress 🚧
- [ ] **Cloud storage integration (CRITICAL - blocking production)**
- [ ] Celery production deployment (Redis setup on Railway)
- [ ] File upload processing (currently fails - uses filename as PubMed ID)

### Planned 📅
- [ ] Cloud storage integration (must be done before production)
- [ ] Video management UI enhancements (delete, download, search)
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
1. ✅ Database models for job tracking (DONE)
2. 🔴 **Cloud storage integration (CRITICAL - DO THIS NEXT)**
3. Celery production deployment (Redis setup on Railway)
4. Complete file upload feature
5. ✅ Secrets management (mostly complete)

**Sprint 2 (Core Features):**
6. Video management UI enhancements (delete, download, search)
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

