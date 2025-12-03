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

