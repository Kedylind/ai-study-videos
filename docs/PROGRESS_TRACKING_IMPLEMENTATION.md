# Progress Tracking System - Advanced Implementation Plan

**Feature:** Real-Time Progress Tracking for Video Generation Pipeline  
**Priority:** 🔴 **CRITICAL - Current system not working reliably**  
**Estimated Effort:** 4-6 hours  
**Status:** Ready for Implementation

---

## 📋 Table of Contents

1. [Problem Analysis](#problem-analysis)
2. [Current System Issues](#current-system-issues)
3. [Proposed Solution](#proposed-solution)
4. [Architecture Design](#architecture-design)
5. [Detailed Implementation Steps](#detailed-implementation-steps)
6. [Code Implementation](#code-implementation)
7. [Testing Strategy](#testing-strategy)
8. [Migration Plan](#migration-plan)

---

## Problem Analysis

### Current Symptoms

Based on the screenshots and logs:

1. **Database Updates Are Happening:**
   - Logs show: `"Updating job progress: 0% -> 60%, step: fetch-paper -> generate-videos"`
   - Database records are being updated successfully

2. **Status Page Shows Stale Data:**
   - Status page displays: `"0% complete (0 of 5 steps)"`
   - Current step stuck at: `"fetch-paper"`
   - Progress bar not updating

3. **JavaScript Polling:**
   - Frontend polls `/status/${pmid}/?_json=1` every 3 seconds
   - But receives stale/cached data

### Root Causes Identified

1. **Race Condition in Status Endpoint:**
   - `pipeline_status()` calls `update_job_progress_from_files()` which may overwrite real-time updates
   - File-based fallback logic conflicts with database updates

2. **Database Transaction Isolation:**
   - Celery worker updates database in one transaction
   - Django view reads in another transaction
   - May not see uncommitted changes (depending on isolation level)

3. **Multiple Progress Update Sources:**
   - Real-time parser updates database
   - File-based fallback updates database
   - Status endpoint calls file-based update again
   - Creates race conditions and overwrites

4. **No Progress Update Timestamp:**
   - Can't determine if progress is stale
   - Can't detect if updates stopped

5. **Inefficient Database Queries:**
   - Status endpoint refreshes job from DB but may get stale data
   - No cache invalidation mechanism

---

## Current System Issues

### Issue 1: Conflicting Update Sources

**Location:** `web/views.py:pipeline_status()` lines 1347-1356

```python
if job.status in ['pending', 'running']:
    update_job_progress_from_files(pmid, task_id)  # ❌ Overwrites real-time updates!
    job.refresh_from_db()
```

**Problem:** 
- Real-time parser updates database with accurate progress
- Status endpoint calls `update_job_progress_from_files()` which checks file existence
- File-based check may return 0% if files aren't immediately visible
- Overwrites the accurate real-time progress

### Issue 2: Database Connection Pooling

**Location:** `web/tasks.py:update_progress_from_line()` lines 333-378

```python
from django.db import connections
connections.close_all()  # Closes all connections
# ... update database ...
connections.close_all()  # Closes again
```

**Problem:**
- Closing connections may cause transaction issues
- May not see updates from other connections
- No explicit transaction management

### Issue 3: No Progress Update Validation

**Location:** `web/tasks.py:update_progress_from_line()` line 349

```python
if job.status in ['pending', 'running']:
    job.progress_percent = progress_state["progress_percent"]
    # No validation that progress is increasing
```

**Problem:**
- No check if progress is regressing (e.g., 60% -> 0%)
- No validation that update is newer than current value
- Can overwrite with stale data

### Issue 4: File-Based Fallback Logic

**Location:** `web/tasks.py:update_job_progress_from_files()` lines 846-940

**Problem:**
- Checks file existence which is unreliable
- May return 0% if files aren't immediately visible
- Called from multiple places, creating race conditions

---

## Proposed Solution

### Solution Overview

Implement a **single source of truth** progress tracking system with:

1. **Real-Time Progress Updates Only:**
   - Remove file-based fallback from status endpoint
   - Use only real-time parser updates
   - Add progress update timestamp to detect stale data

2. **Database Transaction Management:**
   - Use `select_for_update()` to prevent race conditions
   - Explicit transaction boundaries
   - Proper connection handling

3. **Progress Update Validation:**
   - Only update if new progress is >= current progress
   - Track update timestamps
   - Detect and log stale updates

4. **Status Endpoint Optimization:**
   - Read directly from database (no file checks)
   - Add cache headers to prevent browser caching
   - Return progress with timestamp

5. **Progress Update Queue:**
   - Queue progress updates to prevent overwhelming database
   - Batch updates if needed
   - Handle update failures gracefully

---

## Architecture Design

### Component Overview

```
┌─────────────────┐
│  Pipeline       │
│  (subprocess)   │
└────────┬────────┘
         │ stdout/stderr
         ▼
┌─────────────────┐
│  Real-Time      │
│  Parser         │
│  (web/tasks.py) │
└────────┬────────┘
         │ Parse lines
         │ Detect progress
         ▼
┌─────────────────┐
│  Progress       │
│  Update Queue   │
│  (in-memory)    │
└────────┬────────┘
         │ Batch updates
         ▼
┌─────────────────┐
│  Database       │
│  (VideoGenJob)  │
│  - progress_%   │
│  - current_step │
│  - updated_at   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Status         │
│  Endpoint       │
│  (web/views.py) │
└────────┬────────┘
         │ JSON response
         ▼
┌─────────────────┐
│  Frontend       │
│  (JavaScript)   │
│  - Polls /status│
│  - Updates UI   │
└─────────────────┘
```

### Data Flow

1. **Pipeline Output** → Real-time parser reads stdout/stderr line-by-line
2. **Progress Detection** → Parser detects step completions from log patterns
3. **Update Queue** → Progress updates queued (prevents DB overload)
4. **Database Update** → Updates written with transaction locking
5. **Status Endpoint** → Reads directly from database (no file checks)
6. **Frontend** → Polls status endpoint, updates UI

### Key Design Decisions

1. **Single Source of Truth:**
   - Database is the only source of progress
   - No file-based fallback in status endpoint
   - Real-time parser is the only writer

2. **Progress Update Validation:**
   - Only update if new progress >= current progress
   - Track `progress_updated_at` timestamp
   - Detect stale updates (no update in 60 seconds = warning)

3. **Transaction Management:**
   - Use `select_for_update()` to lock row during update
   - Explicit transaction boundaries
   - Proper error handling

4. **Update Batching:**
   - Queue updates to prevent DB overload
   - Batch multiple updates if queue grows
   - Max 1 update per second per job

---

## Detailed Implementation Steps

### Step 1: Add Progress Update Timestamp to Model

**File:** `web/models.py`

**Add field to `VideoGenerationJob` model:**

```python
class VideoGenerationJob(models.Model):
    # ... existing fields ...
    progress_percent = models.IntegerField(default=0)
    current_step = models.CharField(max_length=100, null=True, blank=True)
    progress_updated_at = models.DateTimeField(null=True, blank=True)  # NEW FIELD
    # ... rest of fields ...
```

**Create migration:**
```bash
python manage.py makemigrations
python manage.py migrate
```

---

### Step 2: Create Progress Update Manager

**File:** `web/progress_manager.py` (NEW FILE)

**Purpose:** Centralized progress update logic with validation and queuing

**Functions:**
1. `update_progress()` - Main update function with validation
2. `queue_progress_update()` - Queue updates to prevent DB overload
3. `process_update_queue()` - Process queued updates
4. `is_progress_stale()` - Check if progress hasn't updated recently

**See Code Implementation section for complete code.**

---

### Step 3: Update Real-Time Parser to Use Progress Manager

**File:** `web/tasks.py`

**Replace `update_progress_from_line()` function:**

**Current code (lines 326-378):**
```python
def update_progress_from_line(line: str):
    """Update progress state from a pipeline output line."""
    parsed = _parse_pipeline_progress(line, progress_state)
    if parsed:
        progress_state.update(parsed)
        
        # Update database immediately
        try:
            from django.db import connections
            connections.close_all()
            # ... database update code ...
```

**Updated code:**
```python
def update_progress_from_line(line: str):
    """Update progress state from a pipeline output line."""
    parsed = _parse_pipeline_progress(line, progress_state)
    if parsed:
        progress_state.update(parsed)
        
        # Use progress manager to update database
        try:
            from web.progress_manager import update_progress
            update_progress(
                task_id=self.request.id,
                progress_percent=progress_state["progress_percent"],
                current_step=progress_state.get("current_step"),
                status=progress_state.get("status", "running")
            )
        except Exception as e:
            logger.warning(f"Failed to update progress: {e}", exc_info=True)
```

---

### Step 4: Remove File-Based Updates from Status Endpoint

**File:** `web/views.py`

**Remove file-based update calls from `pipeline_status()`:**

**Current code (lines 1347-1356):**
```python
if job.status in ['pending', 'running']:
    task_id_file = output_dir / "task_id.txt"
    task_id = None
    if task_id_file.exists():
        try:
            with open(task_id_file, "r") as f:
                task_id = f.read().strip()
        except:
            pass
    update_job_progress_from_files(pmid, task_id)  # ❌ REMOVE THIS
    job.refresh_from_db()
```

**Updated code:**
```python
if job.status in ['pending', 'running']:
    # Just refresh from database - real-time parser handles updates
    job.refresh_from_db()
    
    # Check if progress is stale (no update in 60 seconds)
    from web.progress_manager import is_progress_stale
    if is_progress_stale(job):
        logger.warning(f"Progress appears stale for job {job.id}, last update: {job.progress_updated_at}")
```

---

### Step 5: Add Cache Headers to Status Endpoint

**File:** `web/views.py`

**Add cache prevention headers to JSON response:**

**Current code (line 1490):**
```python
response = JsonResponse(status)
response.content = json.dumps(status, indent=2)
return response
```

**Updated code:**
```python
response = JsonResponse(status)
response.content = json.dumps(status, indent=2)

# Prevent browser caching of progress updates
response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
response['Pragma'] = 'no-cache'
response['Expires'] = '0'

return response
```

---

### Step 6: Update Frontend to Handle Timestamps

**File:** `web/templates/status.html`

**Add timestamp checking to detect stale updates:**

**Current code (line 118):**
```javascript
function updateStatus() {
  fetch(`/status/${pmid}/?_json=1`)
    .then(response => response.json())
    .then(data => {
      // Update progress bar
      // ...
```

**Updated code:**
```javascript
let lastProgressTimestamp = null;
let staleUpdateCount = 0;

function updateStatus() {
  fetch(`/status/${pmid}/?_json=1`, {
    cache: 'no-store',  // Prevent browser caching
    headers: {
      'Cache-Control': 'no-cache'
    }
  })
    .then(response => response.json())
    .then(data => {
      // Check if progress timestamp is newer
      if (data.progress_updated_at) {
        const updateTime = new Date(data.progress_updated_at);
        if (lastProgressTimestamp && updateTime <= lastProgressTimestamp) {
          staleUpdateCount++;
          if (staleUpdateCount > 3) {
            console.warn('Progress updates appear stale');
            // Could show warning to user
          }
        } else {
          staleUpdateCount = 0;
          lastProgressTimestamp = updateTime;
        }
      }
      
      // Update progress bar
      // ... rest of existing code ...
```

---

## Code Implementation

### Complete Progress Manager Module

**File:** `web/progress_manager.py` (NEW FILE)

```python
"""
Progress update manager for video generation jobs.

Provides centralized progress update logic with validation, queuing,
and stale detection to prevent race conditions and ensure reliable updates.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Update queue to prevent database overload
_update_queue = {}
_queue_lock = False


def update_progress(
    task_id: str,
    progress_percent: int,
    current_step: Optional[str] = None,
    status: str = "running",
    force: bool = False
) -> bool:
    """
    Update job progress in database with validation and transaction locking.
    
    Args:
        task_id: Celery task ID
        progress_percent: Progress percentage (0-100)
        current_step: Current pipeline step name
        status: Job status (pending, running, completed, failed)
        force: If True, allow progress to decrease (for recovery)
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        from web.models import VideoGenerationJob
        
        with transaction.atomic():
            # Lock the row to prevent race conditions
            try:
                job = VideoGenerationJob.objects.select_for_update().get(task_id=task_id)
            except VideoGenerationJob.DoesNotExist:
                logger.debug(f"Job not found for task_id {task_id}, skipping progress update")
                return False
            
            # Validate progress is not regressing (unless forced)
            if not force:
                if progress_percent < job.progress_percent:
                    logger.warning(
                        f"Progress regression detected for job {job.id}: "
                        f"{job.progress_percent}% -> {progress_percent}%. Ignoring update."
                    )
                    return False
            
            # Only update if values actually changed
            needs_update = (
                job.progress_percent != progress_percent or
                job.current_step != current_step or
                job.status != status
            )
            
            if not needs_update:
                # Update timestamp even if values unchanged (shows activity)
                job.progress_updated_at = timezone.now()
                job.save(update_fields=['progress_updated_at', 'updated_at'])
                return True
            
            # Update progress
            old_progress = job.progress_percent
            old_step = job.current_step
            
            job.progress_percent = progress_percent
            job.current_step = current_step
            job.progress_updated_at = timezone.now()
            
            # Update status if provided
            if status in ['pending', 'running', 'completed', 'failed']:
                job.status = status
            
            # Set completion time if progress is 100%
            if progress_percent >= 100 and job.status == 'running':
                job.status = 'completed'
                if not job.completed_at:
                    job.completed_at = timezone.now()
                job.current_step = None
            
            # Save update
            job.save(update_fields=[
                'progress_percent', 'current_step', 'status',
                'progress_updated_at', 'completed_at', 'updated_at'
            ])
            
            logger.info(
                f"Progress updated for job {job.id}: "
                f"{old_progress}% -> {progress_percent}%, "
                f"step: {old_step} -> {current_step}"
            )
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to update progress for task {task_id}: {e}", exc_info=True)
        return False


def queue_progress_update(
    task_id: str,
    progress_percent: int,
    current_step: Optional[str] = None,
    status: str = "running"
) -> None:
    """
    Queue a progress update to prevent database overload.
    
    Updates are queued and processed in batches. If queue grows too large,
    updates are processed immediately.
    
    Args:
        task_id: Celery task ID
        progress_percent: Progress percentage (0-100)
        current_step: Current pipeline step name
        status: Job status
    """
    global _update_queue
    
    # Add to queue
    if task_id not in _update_queue:
        _update_queue[task_id] = {
            'last_update': 0,
            'pending': None
        }
    
    # Store latest update
    _update_queue[task_id]['pending'] = {
        'progress_percent': progress_percent,
        'current_step': current_step,
        'status': status,
        'timestamp': time.time()
    }
    
    # Process immediately if queue is getting large or enough time has passed
    last_update_time = _update_queue[task_id]['last_update']
    time_since_last = time.time() - last_update_time
    
    # Process if:
    # - More than 1 second since last update (rate limiting)
    # - Or queue has more than 10 pending updates (prevent overflow)
    if time_since_last >= 1.0 or len(_update_queue) > 10:
        process_update_queue()


def process_update_queue() -> None:
    """
    Process all pending progress updates in the queue.
    """
    global _update_queue
    
    for task_id, queue_data in list(_update_queue.items()):
        if queue_data['pending']:
            update = queue_data['pending']
            success = update_progress(
                task_id=task_id,
                progress_percent=update['progress_percent'],
                current_step=update['current_step'],
                status=update['status']
            )
            
            if success:
                queue_data['last_update'] = time.time()
                queue_data['pending'] = None
            else:
                # Keep pending update if it failed
                pass


def is_progress_stale(job) -> bool:
    """
    Check if progress appears stale (no update in last 60 seconds).
    
    Args:
        job: VideoGenerationJob instance
        
    Returns:
        True if progress is stale, False otherwise
    """
    if not job.progress_updated_at:
        # No updates yet - not stale if job just started
        if job.status in ['pending', 'running']:
            # Check if job was created recently (within 5 minutes)
            if job.created_at:
                age = timezone.now() - job.created_at
                return age.total_seconds() > 300  # 5 minutes
        return False
    
    # Check time since last update
    time_since_update = timezone.now() - job.progress_updated_at
    
    # Consider stale if no update in 60 seconds and job is running
    if job.status in ['pending', 'running']:
        return time_since_update.total_seconds() > 60
    
    return False


def get_progress_summary(job) -> dict:
    """
    Get progress summary with staleness information.
    
    Args:
        job: VideoGenerationJob instance
        
    Returns:
        Dict with progress information including staleness flag
    """
    summary = {
        'progress_percent': job.progress_percent,
        'current_step': job.current_step,
        'status': job.status,
        'progress_updated_at': job.progress_updated_at.isoformat() if job.progress_updated_at else None,
        'is_stale': is_progress_stale(job)
    }
    
    return summary
```

---

### Updated Real-Time Parser

**File:** `web/tasks.py`

**Replace `update_progress_from_line()` function (lines 326-378):**

```python
def update_progress_from_line(line: str):
    """Update progress state from a pipeline output line."""
    parsed = _parse_pipeline_progress(line, progress_state)
    if parsed:
        progress_state.update(parsed)
        
        # Use progress manager to update database (with queuing)
        try:
            from web.progress_manager import queue_progress_update
            
            queue_progress_update(
                task_id=self.request.id,
                progress_percent=progress_state["progress_percent"],
                current_step=progress_state.get("current_step"),
                status=progress_state.get("status", "running")
            )
        except Exception as e:
            logger.warning(f"Failed to queue progress update: {e}", exc_info=True)
```

---

### Updated Status Endpoint

**File:** `web/views.py`

**Update `pipeline_status()` function:**

**Replace lines 1346-1357:**
```python
else:
    # Update progress from files if job is running
    if job.status in ['pending', 'running']:
        task_id_file = output_dir / "task_id.txt"
        task_id = None
        if task_id_file.exists():
            try:
                with open(task_id_file, "r") as f:
                    task_id = f.read().strip()
            except:
                pass
        update_job_progress_from_files(pmid, task_id)  # ❌ REMOVE
        job.refresh_from_db()
    
    # Convert job to progress dict
    completed_steps = _get_completed_steps_from_progress(job.progress_percent)
```

**With:**
```python
else:
    # Just refresh from database - real-time parser handles updates
    job.refresh_from_db()
    
    # Check if progress is stale (for logging/debugging)
    if job.status in ['pending', 'running']:
        from web.progress_manager import is_progress_stale
        if is_progress_stale(job):
            logger.warning(
                f"Progress appears stale for job {job.id} (paper {pmid}), "
                f"last update: {job.progress_updated_at}"
            )
    
    # Convert job to progress dict
    completed_steps = _get_completed_steps_from_progress(job.progress_percent)
```

**Update JSON response (around line 1452):**
```python
status = {
    "pmid": pmid,
    "exists": output_dir.exists(),
    "final_video": final_video_exists,
    "final_video_url": final_video_url,
    "status": progress.get("status", "pending"),
    "current_step": progress.get("current_step"),
    "completed_steps": progress.get("completed_steps", []),
    "progress_percent": progress.get("progress_percent", 0),
    "progress_updated_at": None,  # Add timestamp
}

# Add progress timestamp if available
if job and job.progress_updated_at:
    status["progress_updated_at"] = job.progress_updated_at.isoformat()
```

**Add cache headers (around line 1490):**
```python
response = JsonResponse(status)
response.content = json.dumps(status, indent=2)

# Prevent browser caching of progress updates
response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
response['Pragma'] = 'no-cache'
response['Expires'] = '0'

return response
```

---

### Updated Frontend JavaScript

**File:** `web/templates/status.html`

**Update `updateStatus()` function (around line 117):**

```javascript
let lastProgressTimestamp = null;
let staleUpdateCount = 0;

function updateStatus() {
  fetch(`/status/${pmid}/?_json=1`, {
    cache: 'no-store',  // Prevent browser caching
    headers: {
      'Cache-Control': 'no-cache',
      'Pragma': 'no-cache'
    }
  })
    .then(response => {
      // Check if response is from cache
      if (response.headers.get('X-From-Cache')) {
        console.warn('Response was cached, forcing refresh');
        return updateStatus();  // Retry
      }
      return response.json();
    })
    .then(data => {
      // Check if progress timestamp is newer
      if (data.progress_updated_at) {
        const updateTime = new Date(data.progress_updated_at);
        if (lastProgressTimestamp && updateTime <= lastProgressTimestamp) {
          staleUpdateCount++;
          if (staleUpdateCount > 5) {
            console.warn('Progress updates appear stale, last update:', lastProgressTimestamp);
            // Could show warning to user: "Progress updates may be delayed"
          }
        } else {
          staleUpdateCount = 0;
          lastProgressTimestamp = updateTime;
        }
      }
      
      // Update progress bar
      const progressBar = document.getElementById('progress-bar');
      const progressText = document.getElementById('progress-text');
      // ... rest of existing update code ...
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_progress_manager.py` (NEW FILE)

```python
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from web.models import VideoGenerationJob
from web.progress_manager import (
    update_progress,
    is_progress_stale,
    queue_progress_update,
    process_update_queue
)

@pytest.mark.django_db
class TestProgressManager(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user("testuser", "test@example.com", "password")
        self.job = VideoGenerationJob.objects.create(
            user=self.user,
            paper_id="TEST123",
            task_id="test-task-123",
            status="running",
            progress_percent=0
        )
    
    def test_update_progress_increases(self):
        """Test that progress can increase."""
        result = update_progress(
            task_id="test-task-123",
            progress_percent=50,
            current_step="generate-script"
        )
        self.assertTrue(result)
        
        self.job.refresh_from_db()
        self.assertEqual(self.job.progress_percent, 50)
        self.assertEqual(self.job.current_step, "generate-script")
    
    def test_update_progress_prevents_regression(self):
        """Test that progress cannot decrease."""
        self.job.progress_percent = 60
        self.job.save()
        
        result = update_progress(
            task_id="test-task-123",
            progress_percent=40,  # Trying to go backwards
            current_step="generate-script"
        )
        self.assertFalse(result)  # Should reject
        
        self.job.refresh_from_db()
        self.assertEqual(self.job.progress_percent, 60)  # Unchanged
    
    def test_update_progress_allows_force(self):
        """Test that force=True allows regression."""
        self.job.progress_percent = 60
        self.job.save()
        
        result = update_progress(
            task_id="test-task-123",
            progress_percent=40,
            current_step="generate-script",
            force=True
        )
        self.assertTrue(result)
        
        self.job.refresh_from_db()
        self.assertEqual(self.job.progress_percent, 40)
    
    def test_is_progress_stale(self):
        """Test stale progress detection."""
        # Recent update - not stale
        self.job.progress_updated_at = timezone.now()
        self.job.save()
        self.assertFalse(is_progress_stale(self.job))
        
        # Old update - stale
        self.job.progress_updated_at = timezone.now() - timedelta(seconds=120)
        self.job.save()
        self.assertTrue(is_progress_stale(self.job))
```

### Integration Tests

**File:** `tests/test_progress_tracking_integration.py` (NEW FILE)

```python
import pytest
from django.test import Client
from django.contrib.auth.models import User
from web.models import VideoGenerationJob
from web.tasks import generate_video_task

@pytest.mark.django_db
def test_progress_updates_in_real_time(client):
    """Test that progress updates are visible in status endpoint."""
    # Create user and job
    user = User.objects.create_user("testuser", "test@example.com", "password")
    client.force_login(user)
    
    # Start pipeline (simulation mode)
    # ... start task ...
    
    # Poll status endpoint
    response = client.get(f"/status/TEST123/?_json=1")
    assert response.status_code == 200
    
    data = response.json()
    assert "progress_percent" in data
    assert "progress_updated_at" in data
    
    # Verify progress increases over time
    # ...
```

### Manual Testing Checklist

- [ ] Start video generation
- [ ] Check status page - progress should update in real-time
- [ ] Verify progress bar moves smoothly
- [ ] Verify current step updates correctly
- [ ] Check browser console - no stale update warnings
- [ ] Verify progress doesn't regress (60% -> 40%)
- [ ] Check database - `progress_updated_at` should update
- [ ] Test with slow network - progress should still update
- [ ] Test with multiple concurrent jobs - no conflicts
- [ ] Verify cache headers prevent browser caching

---

## Migration Plan

### Phase 1: Add New Fields (Non-Breaking)

1. Add `progress_updated_at` field to model
2. Create and run migration
3. Deploy (existing code continues to work)

### Phase 2: Deploy Progress Manager (Backward Compatible)

1. Deploy `progress_manager.py`
2. Update real-time parser to use progress manager
3. Keep old `update_job_progress_from_files()` for now
4. Deploy and test

### Phase 3: Update Status Endpoint (Breaking Change)

1. Remove file-based updates from status endpoint
2. Add cache headers
3. Add timestamp to JSON response
4. Deploy and monitor

### Phase 4: Update Frontend (Non-Breaking)

1. Add timestamp checking to JavaScript
2. Add cache prevention headers
3. Deploy and test

### Phase 5: Cleanup (Optional)

1. Remove `update_job_progress_from_files()` if no longer needed
2. Remove file-based fallback logic
3. Clean up old code

---

## Expected Results

After implementation:

✅ **Progress updates in real-time** - Status page shows current progress immediately  
✅ **No progress regression** - Progress never decreases (unless forced)  
✅ **No stale updates** - Status endpoint always returns latest progress  
✅ **No browser caching** - Cache headers prevent stale cached responses  
✅ **Reliable updates** - Transaction locking prevents race conditions  
✅ **Better debugging** - Timestamps show when progress was last updated  
✅ **Performance** - Update queuing prevents database overload  

---

## Troubleshooting

### Problem: Progress still not updating

**Check:**
1. Is `progress_manager.py` imported correctly?
2. Are there errors in Celery worker logs?
3. Is `progress_updated_at` being set in database?
4. Check browser console for JavaScript errors

### Problem: Progress regresses

**Check:**
1. Is `force=True` being used incorrectly?
2. Are multiple update sources still active?
3. Check logs for "Progress regression detected" warnings

### Problem: Status endpoint returns stale data

**Check:**
1. Are cache headers set correctly?
2. Is browser caching responses?
3. Check `progress_updated_at` timestamp in database
4. Verify database connection pooling settings

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-28  
**Status:** Ready for Implementation

