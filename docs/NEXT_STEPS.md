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

### 1. Make Video Generation Survive Server Restarts (Celery)
**Status:** ✅ Implemented (needs testing in production)  
**Priority:** 🟡 Medium (testing/deployment)  
**Estimated Effort:** 1 hour (testing and deployment verification)

**Problem:**
- Current implementation uses daemon thread that dies on server restart
- Pipeline stops if user closes browser or server restarts
- No persistence of running jobs
- No error messages shown to users when pipeline fails

**Solution: Celery Task Queue**
- Use Celery workers to run video generation tasks
- Tasks stored in Redis/RabbitMQ broker
- Tasks survive server restarts and browser closes
- Automatic retries on failures
- Better monitoring and error tracking

**What needs to be done:**

1. **Install Celery dependencies:**
   - Add `celery`, `redis` (or `kombu` for RabbitMQ) to `requirements.txt`
   - Install Redis service on Railway (or use RabbitMQ)

2. **Create Celery configuration:**
   - Create `config/celery.py` with Celery app setup
   - Configure broker URL from environment variable
   - Set up result backend

3. **Create Celery task:**
   - Create `web/tasks.py` with `generate_video_task` function
   - Move pipeline execution logic to Celery task
   - Add error handling and logging

4. **Update views to use Celery:**
   - Replace `_start_pipeline_async()` with Celery task call
   - Update status endpoint to check Celery task status
   - Add error message handling for failed tasks

5. **Add error handling and user feedback:**
   - Capture pipeline errors (paper not found, API failures, etc.)
   - Store error messages in task result or log file
   - Display clear error messages in status page
   - Show specific error types (e.g., "Paper not found in PubMed Central", "API key invalid", "Video generation failed")

6. **Update deployment:**
   - Add Celery worker process to `Procfile`
   - Configure Redis/RabbitMQ service on Railway
   - Set `CELERY_BROKER_URL` environment variable

**Code changes needed:**
- `requirements.txt`: Add `celery` and `redis` (or `kombu`)
- `config/celery.py`: Create Celery app configuration (new file)
- `web/tasks.py`: Create `generate_video_task` Celery task (new file)
- `web/views.py`: Replace `_start_pipeline_async()` with Celery task call
- `web/views.py`: Update `pipeline_status()` to check Celery task status and show errors
- `Procfile`: Add `worker: celery -A config worker --loglevel=info`

**Error handling requirements:**
- Catch and log all pipeline exceptions
- Store error messages in task result or readable log format
- Display user-friendly error messages in status page:
  - "Paper not found in PubMed Central" (for invalid PMID/PMCID)
  - "API key invalid or expired" (for API authentication errors)
  - "Video generation failed: [specific error]" (for other failures)
  - "Pipeline timeout" (if task takes too long)
- Show error details in status JSON endpoint for debugging
- Update status page template to display error messages clearly

**Benefits:**
- ✅ Tasks survive server restarts
- ✅ Tasks survive browser close
- ✅ Automatic retries on failures
- ✅ Better monitoring and scalability
- ✅ Production-ready reliability
- ✅ Clear error messages for users

**Action items:**
- [x] Install Celery and Redis dependencies
- [x] Create `config/celery.py` configuration
- [x] Create `web/tasks.py` with video generation task
- [x] Update `web/views.py` to use Celery task
- [x] Add error handling and user feedback
- [x] Update status endpoint to show errors
- [x] Update `Procfile` for Celery worker
- [ ] Set up Redis service on Railway
- [ ] Configure `CELERY_BROKER_URL` environment variable
- [ ] Test that tasks survive server restart (production)
- [ ] Test error handling with invalid inputs (production)

---

### 2. Complete File Upload Feature
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

### 3. Access Control & Secrets Management
**Status:** Basic environment variables, needs hardening + access control  
**Priority:** 🟠 High  
**Estimated Effort:** 2-3 hours (1 hour for access control + 1-2 hours for secrets)

**Part A: Access Control for Video Generation**
**Status:** ✅ Completed  
**Priority:** ✅ Done  
**Estimated Effort:** Completed

**What needs to be done:**
- Implement access code validation to prevent unauthorized API usage
- Add access code field to upload form (web UI)
- Add access code validation to API endpoint
- Store access code in environment variable
- Update error messages for invalid codes

**Implementation (Option 1 - Per-Request Access Code):**
1. Add `access_code` field to `PaperUploadForm` in `web/forms.py`
2. Validate access code in `upload_paper` view before starting pipeline
3. Validate access code in `api_start_generation` API endpoint
4. Update `upload.html` template to include access code input field
5. Set `VIDEO_ACCESS_CODE` environment variable in Railway

**Code changes needed:**
- `web/forms.py`: Add `access_code = forms.CharField(...)` to `PaperUploadForm`
- `web/views.py`: Validate code against `os.getenv("VIDEO_ACCESS_CODE")` before pipeline start
- `web/templates/upload.html`: Add access code input field with label
- `config/settings.py`: Document `VIDEO_ACCESS_CODE` in comments

**Benefits:**
- Prevents unauthorized users from using expensive API calls
- Easy to rotate codes by changing environment variable
- No database changes required
- Works immediately after deployment

**Action items:**
- [x] Add access code field to upload form
- [x] Implement validation in web view
- [x] Implement validation in API endpoint
- [x] Update upload template
- [x] Set `VIDEO_ACCESS_CODE` in Railway environment variables
- [x] Test with valid/invalid codes
- [x] Document code distribution process (in .env.example)

---

**Part B: Secrets Management**
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

### 4. Cloud Storage Integration (S3/GCS)
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

### 5. Video Management UI
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

### 6. Error Monitoring & Logging
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

### 7. Rate Limiting & API Quota Management
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

### 8. Email Verification
**Status:** Not implemented  
**Priority:** 🟢 Low  
**Estimated Effort:** 2-3 hours

**What needs to be done:**
- Send verification email on registration
- Add email verification endpoint
- Require verification before video generation
- Add resend verification email feature

---

### 9. Password Reset
**Status:** Not implemented  
**Priority:** 🟢 Low  
**Estimated Effort:** 2-3 hours

**What needs to be done:**
- Add "Forgot Password" link
- Implement password reset flow
- Send reset email with token
- Add reset password form

---

### 10. User Profiles
**Status:** Not implemented  
**Priority:** 🟢 Low  
**Estimated Effort:** 3-4 hours

**What needs to be done:**
- Create user profile model
- Add profile page
- Allow editing profile information
- Show user statistics (videos generated, etc.)

---

### 11. Django Admin Configuration
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

### 12. Deployment Guide
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

### 13. Architecture Documentation
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

### 14. Add Unit Tests
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

### 15. Error Handling Improvements
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
- [ ] Celery production deployment (Redis setup on Railway)
- [ ] File upload processing (currently fails - uses filename as PubMed ID)

### Planned 📅
- [ ] Cloud storage integration
- [ ] Video management UI
- [ ] Error monitoring
- [ ] Rate limiting
- [ ] Email verification
- [ ] Password reset
- [ ] User profiles
- [ ] Comprehensive testing

---

## 🎯 Recommended Implementation Order

**Sprint 1 (Production Readiness):**
1. ✅ Integrate Celery task queue (local complete, needs production deployment)
2. Complete file upload feature
3. ✅ Secrets management & security (mostly complete)

**Sprint 2 (Core Features):**
4. Cloud storage integration
5. Video management UI
6. Error monitoring

**Sprint 3 (Polish):**
7. Rate limiting
8. Email verification
9. Password reset
10. Testing

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

