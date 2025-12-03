# Hidden Hill - Next Steps & Roadmap

**Last Updated:** 2025-01-28  
**Project Status:** Core Pipeline Complete, Missing Key Sprint 1 Features  
**Focus:** Complete Sprint 1 MVP Scope per Design Sprint Document

---

## 🎯 Project Overview

Hidden Hill is a Django web application that converts scientific papers into engaging social media videos (TikTok/Instagram Reels format). The system uses AI (Gemini for text/audio, Runway for video) to automatically generate educational content from PubMed papers.

**Current Status:**
- ✅ Core pipeline fully functional (fetch-paper → generate-script → generate-audio → generate-videos)
- ✅ Web UI and REST API working
- ✅ User authentication implemented
- ✅ Celery task queue integrated
- ✅ Database models for job tracking implemented
- ✅ "My Videos" archive page implemented
- ✅ Research Ingestion (PubMed Central) working
- ✅ Progress tracking with real-time pipeline output parsing
- ✅ Video download link on status page
- ✅ Cloud storage (Cloudflare R2) implemented
- ❌ **MISSING:** Editing & Review Interface (Sprint 1 - 16 story points)
- ❌ **MISSING:** Analytics Dashboard (Sprint 1 - 8 story points)
- ❌ **MISSING:** Admin & System Monitoring (Sprint 1 - 8 story points)
- ❌ **MISSING:** File Upload Processing (part of Research Ingestion - 12 story points)

---

## 🚀 Sprint 1 Critical Features (Per Design Sprint Document)

### 1. 🎯 SPRINT 1: Editing & Review Interface
**Status:** Not implemented  
**Priority:** 🎯 **SPRINT 1 CORE FEATURE - 16 Story Points**  
**Estimated Effort:** 4-6 hours  
**Sprint 1 Alignment:** Key MVP feature from Design Sprint

**REQUIREMENT FROM SPRINT 1:**
> "As a user, I can edit and refine the generated script before exporting."

**Current State:**
- Script is generated automatically in `script.json` format
- Users have no way to review or edit the script before video generation
- Script is passed directly to video generation pipeline

**What Needs to be Done:**

1. **Create Script Review Page**
   - Display generated script in readable format
   - Show script structure (scenes, captions, visual descriptions)
   - Allow inline editing of script content
   - Save edited script back to `script.json`

2. **Add Review Step to Pipeline Flow**
   - After "generate-script" step completes, pause pipeline
   - Redirect user to review/edit page
   - Wait for user approval before continuing to "generate-audio" step
   - Allow user to skip review (auto-approve)

3. **Update Pipeline to Support Manual Script**
   - Modify pipeline to accept pre-generated `script.json`
   - Skip script generation if script already exists
   - Validate script format before proceeding

4. **UI Components Needed:**
   - Script review page (`/review/<pmid>/`)
   - Script editor (rich text or structured form)
   - "Approve & Continue" button
   - "Edit Script" button
   - "Skip Review" option

**Implementation Steps:**

1. **Create Review View** (`web/views.py`)
   ```python
   @login_required
   def review_script(request, pmid: str):
       """Display and allow editing of generated script."""
       # Load script.json
       # Display in editable format
       # Save edits on submit
       # Update job status to continue pipeline
   ```

2. **Add Review URL Route** (`web/urls.py`)
   ```python
   path("review/<str:pmid>/", review_script, name="review_script"),
   ```

3. **Create Review Template** (`web/templates/review.html`)
   - Display script structure
   - Allow editing of scenes, captions, descriptions
   - Show preview of changes
   - Submit button to continue pipeline

4. **Update Pipeline Task** (`web/tasks.py`)
   - Check if script needs review
   - Pause after script generation
   - Wait for user approval before continuing
   - Resume pipeline when approved

5. **Update Status Page** (`web/templates/status.html`)
   - Show "Review Script" button when script is ready
   - Link to review page

**Files to Create/Modify:**
- `web/views.py` - Add `review_script()` view
- `web/urls.py` - Add review route
- `web/templates/review.html` - Create review page
- `web/tasks.py` - Add review step handling
- `web/models.py` - Add `needs_review` flag to VideoGenerationJob (optional)

**Testing Checklist:**
- [ ] Script is displayed after generation
- [ ] User can edit script content
- [ ] Edited script is saved correctly
- [ ] Pipeline continues after approval
- [ ] Pipeline skips review if user chooses
- [ ] Script validation works correctly

---

### 2. 🎯 File Upload Feature (REMOVED)
**Status:** Feature removed - only PubMed ID/PMCID input is supported

---

### 3. 🎯 SPRINT 1: Analytics Dashboard
**Status:** Not implemented  
**Priority:** 🎯 **SPRINT 1 CORE FEATURE - 8 Story Points**  
**Estimated Effort:** 3-4 hours  
**Sprint 1 Alignment:** Key MVP feature from Design Sprint

**REQUIREMENT FROM SPRINT 1:**
> "As a user, I can view insights such as time saved, total outputs, and engagement metrics."

**What Needs to be Done:**

1. **Create Analytics Dashboard Page**
   - Display user statistics:
     - Total videos generated
     - Time saved (estimated based on manual video creation time)
     - Success rate (completed vs failed)
     - Average generation time
     - Most recent videos
   - Show visual charts/graphs (optional but nice)

2. **Calculate Metrics**
   - Time saved: Estimate manual video creation time (e.g., 2 hours per video)
   - Total outputs: Count completed VideoGenerationJob records
   - Success rate: Completed / (Completed + Failed)
   - Average generation time: Calculate from job timestamps

3. **Add Analytics View** (`web/views.py`)
   ```python
   @login_required
   def analytics_dashboard(request):
       """Display user analytics and insights."""
       # Calculate metrics
       # Return to template
   ```

4. **Create Analytics Template** (`web/templates/analytics.html`)
   - Display statistics cards
   - Show recent activity
   - Optional: Add charts using Chart.js or similar

5. **Add Navigation Link**
   - Add "Analytics" link to navigation menu
   - Accessible from "My Videos" page

**Implementation Steps:**

1. **Create Analytics View** (`web/views.py`)
   - Query user's VideoGenerationJob records
   - Calculate metrics:
     - Total videos: `jobs.filter(status='completed').count()`
     - Time saved: `total_videos * 2` hours (estimate)
     - Success rate: `completed / (completed + failed) * 100`
     - Average time: Calculate from `created_at` to `completed_at`
   - Return context to template

2. **Add Analytics URL** (`web/urls.py`)
   ```python
   path("analytics/", analytics_dashboard, name="analytics"),
   ```

3. **Create Analytics Template** (`web/templates/analytics.html`)
   - Display metrics in cards
   - Show recent videos list
   - Add navigation back to "My Videos"

4. **Update Navigation** (`web/templates/base.html`)
   - Add "Analytics" link for authenticated users

**Files to Create/Modify:**
- `web/views.py` - Add `analytics_dashboard()` view
- `web/urls.py` - Add analytics route
- `web/templates/analytics.html` - Create analytics page
- `web/templates/base.html` - Add navigation link

**Metrics to Display:**
- 📊 Total Videos Generated
- ⏱️ Time Saved (estimated hours)
- ✅ Success Rate (%)
- ⚡ Average Generation Time
- 📅 Recent Activity (last 10 videos)

**Testing Checklist:**
- [ ] Analytics page displays correctly
- [ ] Metrics are calculated accurately
- [ ] Time saved calculation works
- [ ] Success rate is correct
- [ ] Recent videos list shows correctly
- [ ] Navigation link works

---

### 4. 🎯 SPRINT 1: Admin & System Monitoring
**Status:** Not implemented  
**Priority:** 🎯 **SPRINT 1 CORE FEATURE - 8 Story Points**  
**Estimated Effort:** 4-5 hours  
**Sprint 1 Alignment:** Key MVP feature from Design Sprint

**REQUIREMENT FROM SPRINT 1:**
> "As an admin, I can monitor usage, storage, and task queue performance."

**What Needs to be Done:**

1. **Create Admin Dashboard Page**
   - Display system-wide statistics:
     - Total users
     - Total videos generated (all users)
     - Total storage used
     - Task queue status (pending, running, completed, failed)
     - Recent activity (last 24 hours)
     - Error rate
     - Average generation time

2. **Add Admin-Only Access Control**
   - Restrict to superuser/admin users only
   - Add `@staff_member_required` or `@user_passes_test(lambda u: u.is_superuser)` decorator

3. **Display Task Queue Status**
   - Show Celery task queue statistics
   - Pending tasks count
   - Running tasks count
   - Failed tasks (with error details)
   - Queue performance metrics

4. **Storage Monitoring**
   - Calculate total storage used (if using cloud storage)
   - Show storage breakdown by user (optional)
   - Display storage limits/warnings

5. **System Health Indicators**
   - Database connection status
   - Celery worker status
   - Cloud storage connection status
   - API key status (if applicable)

**Implementation Steps:**

1. **Create Admin Dashboard View** (`web/views.py`)
   ```python
   @user_passes_test(lambda u: u.is_superuser)
   def admin_dashboard(request):
       """Admin dashboard with system monitoring."""
       # Calculate system metrics
       # Get task queue status
       # Return to template
   ```

2. **Add Admin URL** (`web/urls.py`)
   ```python
   path("admin/dashboard/", admin_dashboard, name="admin_dashboard"),
   ```

3. **Create Admin Template** (`web/templates/admin/dashboard.html`)
   - Display system statistics
   - Show task queue status
   - Display recent activity
   - Add system health indicators

4. **Add Celery Task Status Check**
   - Query Celery for active tasks
   - Count pending/running/failed tasks
   - Display in dashboard

5. **Add Storage Monitoring**
   - Calculate storage from VideoGenerationJob records
   - If using R2, query storage usage (if API available)
   - Display storage metrics

6. **Update Django Admin** (optional)
   - Customize Django admin interface
   - Add useful admin actions
   - Add filters and search

**Files to Create/Modify:**
- `web/views.py` - Add `admin_dashboard()` view
- `web/urls.py` - Add admin dashboard route
- `web/templates/admin/dashboard.html` - Create admin dashboard
- `web/admin.py` - Customize Django admin (optional)

**Metrics to Display:**
- 👥 Total Users
- 🎬 Total Videos Generated
- 💾 Storage Used
- 📊 Task Queue Status (Pending/Running/Completed/Failed)
- ⚠️ Error Rate
- ⚡ Average Generation Time
- 🏥 System Health (Database, Celery, Storage)

**Testing Checklist:**
- [ ] Admin dashboard is accessible only to superusers
- [ ] System metrics are calculated correctly
- [ ] Task queue status is accurate
- [ ] Storage monitoring works
- [ ] System health indicators are correct
- [ ] Recent activity displays correctly

---

## 📊 Recommended Implementation Order

### Sprint 1 (Core Features)

**Week 1: Core Sprint 1 Features**
1. 🎯 **Complete file upload feature** (3-4 hours)
2. 🎯 **Editing & Review Interface** (4-6 hours)
3. 🎯 **Analytics Dashboard** (3-4 hours)
4. 🎯 **Admin & System Monitoring** (4-5 hours)

**Total Estimated Effort:** 14-19 hours

---

## 📝 Notes

- **Current Branch:** `dev_1`
- **Deployment:** Railway (configured, needs production setup)
- **Database:** SQLite locally, PostgreSQL on Railway
- **Storage:** ⚠️ **Local filesystem - CRITICAL: Videos are lost on Railway container restarts. Cloudflare R2 cloud storage must be implemented before production deployment.**

---

## ✅ Completed Features (Not in Next Steps)

The following features are already implemented and working:
- ✅ User Authentication & Profiles
- ✅ Research Ingestion (PubMed Central)
- ✅ Summarization Pipeline
- ✅ Storyboard Generation (part of pipeline)
- ✅ Rendering Preparation (part of pipeline)
- ✅ "My Videos" archive page
- ✅ Celery task queue integration
- ✅ Database models for job tracking
- ✅ Access control (access code required)
- ✅ Video download link on status page
- ✅ Cloud storage (Cloudflare R2) implementation
- ✅ Real-time progress tracking with pipeline output parsing

---

**Last Review:** 2025-01-28  
**Next Review:** After Sprint 1 completion
