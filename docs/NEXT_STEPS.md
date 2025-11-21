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

### 1. Add Database Models for Job Tracking
**Status:** Not implemented  
**Priority:** 🔴 Critical  
**Estimated Effort:** 2-3 hours

**Problem:**
- Current implementation uses file-based status tracking (checking file existence)
- Complex status checking logic with multiple fallback methods
- No way to query all videos or track user history
- Doesn't scale to multiple servers
- No user association with generated videos

**Solution: Database Models**
- Create `VideoGenerationJob` model to track each generation
- Store status, progress, errors in database
- Link jobs to users for history tracking
- Single source of truth for status

**What needs to be done:**

1. **Create database models:**
   - `VideoGenerationJob` model with fields:
     - `user` (ForeignKey to User)
     - `paper_id` (CharField, indexed)
     - `status` (CharField: pending, running, completed, failed)
     - `progress_percent` (IntegerField)
     - `current_step` (CharField, nullable)
     - `error_message` (TextField, blank)
     - `error_type` (CharField, blank)
     - `task_id` (CharField for Celery task ID)
     - `final_video_path` (CharField)
     - `created_at`, `updated_at`, `completed_at` (DateTimeFields)

2. **Create and run migrations:**
   - `python manage.py makemigrations`
   - `python manage.py migrate`

3. **Update Celery task to save to database:**
   - Create/update `VideoGenerationJob` record when task starts
   - Update status and progress as pipeline runs
   - Save error information on failure
   - Mark as completed when video is ready

4. **Simplify status checking:**
   - Replace complex `_get_pipeline_progress()` with simple database query
   - Remove file-based status checks (keep as fallback initially)
   - Update `pipeline_status()` view to read from database

5. **Update views:**
   - Create `VideoGenerationJob` when user submits paper
   - Link job to current user
   - Store Celery task ID in job record

**Code changes needed:**
- `web/models.py`: Create `VideoGenerationJob` model (new file or add to existing)
- `web/tasks.py`: Update `generate_video_task()` to save status to database
- `web/views.py`: Create job record in `upload_paper()` view
- `web/views.py`: Simplify `_get_pipeline_progress()` to query database
- `web/views.py`: Update `pipeline_status()` to use database

**Benefits:**
- ✅ Single source of truth for status
- ✅ Simple, reliable status checking
- ✅ User history tracking
- ✅ Scalable to multiple servers
- ✅ Easy to query and filter videos
- ✅ Enables video management UI
- ✅ Better for analytics and monitoring

**Action items:**
- [ ] Create `VideoGenerationJob` model
- [ ] Create and run database migrations
- [ ] Update Celery task to save status to database
- [ ] Simplify status checking to use database
- [ ] Update views to create/update job records
- [ ] Test status updates work correctly
- [ ] Test user association works
- [ ] (Optional) Add `Paper` model for paper metadata

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

