"""
Celery tasks for video generation pipeline.

This module contains asynchronous tasks that run the video generation pipeline.
Tasks are executed by Celery workers and survive server restarts.
"""

import json
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="web.tasks.generate_video_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 0},  # Don't auto-retry, but catch all exceptions
    reject_on_worker_lost=False,  # Don't reject task if worker dies
)
def generate_video_task(self, pmid: str, output_dir: str, user_id: Optional[int] = None) -> Dict:
    """
    Celery task to generate video from a PubMed paper.
    
    This task runs the video generation pipeline in a subprocess and captures
    all output and errors. Errors are stored in a JSON file for retrieval
    by the status endpoint.
    
    Args:
        pmid: PubMed ID or PMC ID of the paper
        output_dir: Directory path where output files will be saved
        user_id: Optional user ID to associate with the job
        
    Returns:
        Dict with status information:
        {
            "status": "completed" | "failed",
            "pmid": str,
            "output_dir": str,
            "error": Optional[str],  # Error message if failed
            "error_type": Optional[str],  # Type of error (user-friendly)
        }
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # File to store task result/error information
    task_result_file = output_path / "task_result.json"
    log_path = output_path / "pipeline.log"
    
    # Initialize task result
    task_result = {
        "status": "running",
        "pmid": pmid,
        "output_dir": str(output_dir),
        "task_id": self.request.id,
        "error": None,
        "error_type": None,
    }
    
    # Update database job record
    job = None
    try:
        if user_id:
            from django.contrib.auth.models import User
            from web.models import VideoGenerationJob
            try:
                user = User.objects.get(pk=user_id)
                job, created = VideoGenerationJob.objects.get_or_create(
                    task_id=self.request.id,
                    defaults={
                        'user': user,
                        'paper_id': pmid,
                        'status': 'running',
                        'progress_percent': 0,
                        'current_step': 'starting',
                    }
                )
                if not created:
                    # Update existing job
                    job.status = 'running'
                    job.progress_percent = 0
                    job.current_step = 'starting'
                    job.save(update_fields=['status', 'progress_percent', 'current_step', 'updated_at'])
            except Exception as e:
                logger.warning(f"Failed to create/update job record: {e}")
    except Exception as e:
        logger.warning(f"Failed to import models for job tracking: {e}")
    
    try:
        logger.info(f"Starting video generation task for {pmid}")
        logger.info(f"Task ID: {self.request.id}")
        logger.info(f"Output directory: {output_dir}")
        
        # Check if simulation mode is enabled
        if settings.SIMULATION_MODE:
            logger.info(f"SIMULATION MODE ENABLED - Simulating pipeline progress instead of running actual pipeline")
            from web.simulation import simulate_pipeline_progress
            
            # Update task state
            self.update_state(
                state="PROGRESS",
                meta={"current_step": "starting", "pmid": pmid}
            )
            
            # Create a log file for simulation (use UTF-8 encoding)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"[SIMULATION MODE] Starting simulated pipeline for {pmid}\n")
            
            # Run simulation
            try:
                # Close any existing database connections before simulation
                from django.db import connections
                connections.close_all()
                
                simulate_pipeline_progress(pmid, output_path, self.request.id, job, delay_per_step=3.0)
                
                # Update task result to completed
                task_result["status"] = "completed"
                logger.info(f"Simulation completed successfully for {pmid}")
                
                # Save final task result
                try:
                    with open(task_result_file, "w") as f:
                        json.dump(task_result, f, indent=2)
                except Exception as e:
                    logger.warning(f"Failed to save final task result: {e}")
                
                return task_result
            except Exception as e:
                logger.exception(f"Simulation failed for {pmid}: {e}")
                task_result["status"] = "failed"
                task_result["error"] = f"Simulation error: {str(e)}"
                task_result["error_type"] = "task_error"
                
                # Save failed task result
                try:
                    with open(task_result_file, "w") as f:
                        json.dump(task_result, f, indent=2)
                except Exception as e:
                    logger.warning(f"Failed to save failed task result: {e}")
                
                # Update job record
                if job:
                    try:
                        from django.db import connections
                        connections.close_all()
                        # Refresh job from database
                        job.refresh_from_db()
                        job.status = 'failed'
                        job.error_message = task_result["error"]
                        job.error_type = task_result["error_type"]
                        job.save(update_fields=['status', 'error_message', 'error_type', 'updated_at'])
                    except Exception as db_error:
                        logger.warning(f"Failed to update job record: {db_error}")
                
                return task_result
        
        # Normal pipeline execution (not simulation)
        # Update task state
        self.update_state(
            state="PROGRESS",
            meta={"current_step": "starting", "pmid": pmid}
        )
        
        # Use the same Python interpreter
        python_exe = sys.executable
        script_path = Path(settings.BASE_DIR) / "pipeline" / "main.py"
        
        # Verify script exists
        if not script_path.exists():
            raise FileNotFoundError(f"Pipeline script not found: {script_path}")
        
        cmd = [python_exe, str(script_path), "generate-video", pmid, str(output_path)]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        logger.info(f"Working directory: {settings.BASE_DIR}")
        
        env = os.environ.copy()
        # Ensure Python doesn't buffer output so we see logs in real-time
        env["PYTHONUNBUFFERED"] = "1"
        
        # Run pipeline and capture output
        process = None
        try:
            with open(log_path, "ab") as log_file:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,  # Merge stderr into stdout
                    env=env,
                    cwd=str(settings.BASE_DIR),
                    start_new_session=True,  # Create new process group
                )
                
                logger.info(f"Started subprocess with PID: {process.pid}")
                
                # Wait for process to complete with timeout handling
                # Use Celery's time limit minus a buffer for cleanup
                timeout_seconds = settings.CELERY_TASK_TIME_LIMIT - 60  # Leave 60s buffer
                try:
                    return_code = process.wait(timeout=timeout_seconds)
                    logger.info(f"Subprocess completed with return code: {return_code}")
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
        except subprocess.SubprocessError as e:
            logger.exception(f"Subprocess error: {e}")
            return_code = -1
            # Clean up process if it exists
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    try:
                        process.kill()
                        process.wait()
                    except:
                        pass
            raise Exception(f"Failed to start or run pipeline subprocess: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error during subprocess execution: {e}")
            # Clean up process if it exists
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    try:
                        process.kill()
                        process.wait()
                    except:
                        pass
            return_code = -1
            raise
        
        # Check if pipeline succeeded
        final_video = output_path / "final_video.mp4"
        
        if return_code == 0 and final_video.exists():
            task_result["status"] = "completed"
            logger.info(f"Video generation completed successfully for {pmid}")
            
            # Update database job record
            if job:
                try:
                    job.status = 'completed'
                    job.progress_percent = 100
                    job.current_step = None
                    job.final_video_path = str(final_video)
                    job.completed_at = timezone.now()
                    job.save(update_fields=['status', 'progress_percent', 'current_step', 'final_video_path', 'completed_at', 'updated_at'])
                except Exception as e:
                    logger.warning(f"Failed to update job record on completion: {e}")
        else:
            # Pipeline failed - try to extract error from log
            error_message = _extract_error_from_log(log_path)
            error_type = _classify_error(error_message)
            
            task_result["status"] = "failed"
            task_result["error"] = error_message
            task_result["error_type"] = error_type
            
            logger.error(f"Video generation failed for {pmid}: {error_message}")
            
            # Update database job record
            if job:
                try:
                    job.status = 'failed'
                    job.error_message = error_message
                    job.error_type = error_type
                    job.save(update_fields=['status', 'error_message', 'error_type', 'updated_at'])
                except Exception as e:
                    logger.warning(f"Failed to update job record on failure: {e}")
            
            # Update task state with error (use PROGRESS state, not FAILURE, to avoid serialization issues)
            # We'll return the failed result instead of raising an exception
            self.update_state(
                state="PROGRESS",
                meta={
                    "pmid": pmid,
                    "error": error_message,
                    "error_type": error_type,
                    "status": "failed",
                }
            )
    
    except KeyboardInterrupt:
        # Handle keyboard interrupt gracefully
        logger.warning(f"Task interrupted for {pmid}")
        task_result["status"] = "failed"
        task_result["error"] = "Task was interrupted"
        task_result["error_type"] = "task_error"
        
        # Update database job record
        if job:
            try:
                job.status = 'failed'
                job.error_message = "Task was interrupted"
                job.error_type = "task_error"
                job.save(update_fields=['status', 'error_message', 'error_type', 'updated_at'])
            except Exception as e:
                logger.warning(f"Failed to update job record on interrupt: {e}")
        
        raise  # Re-raise to let Celery handle it
    except Exception as e:
        # Catch ALL other exceptions to prevent worker crash
        error_message = f"Task execution error: {str(e)}"
        task_result["status"] = "failed"
        task_result["error"] = error_message
        task_result["error_type"] = "task_error"
        
        logger.exception(f"Unexpected error in video generation task for {pmid}")
        
        # Update database job record
        if job:
            try:
                job.status = 'failed'
                job.error_message = error_message
                job.error_type = "task_error"
                job.save(update_fields=['status', 'error_message', 'error_type', 'updated_at'])
            except Exception as e:
                logger.warning(f"Failed to update job record on exception: {e}")
        
        # Update task state (use PROGRESS instead of FAILURE to avoid serialization issues)
        try:
            self.update_state(
                state="PROGRESS",
                meta={
                    "pmid": pmid,
                    "error": error_message,
                    "error_type": "task_error",
                    "status": "failed",
                }
            )
        except Exception as state_error:
            logger.error(f"Failed to update task state: {state_error}")
    
    finally:
        # Save task result to file for status endpoint to read
        try:
            with open(task_result_file, "w") as f:
                json.dump(task_result, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save task result: {e}")
    
    return task_result


def _extract_error_from_log(log_path: Path) -> str:
    """
    Extract error message from pipeline log file.
    
    Args:
        log_path: Path to pipeline.log file
        
    Returns:
        Error message string, or generic message if log can't be read
    """
    if not log_path.exists():
        return "Pipeline log file not found"
    
    try:
        # Read last 8KB of log file
        with open(log_path, "rb") as f:
            f.seek(max(0, f.tell() - 8192))
            log_content = f.read().decode(errors="replace")
        
        # Try to find error messages
        lines = log_content.split("\n")
        
        # Look for common error patterns
        error_keywords = ["Error:", "Failed:", "Exception:", "Traceback", "✗"]
        
        error_lines = []
        for line in reversed(lines):
            if any(keyword in line for keyword in error_keywords):
                error_lines.insert(0, line)
                if len(error_lines) >= 5:  # Get last 5 error lines
                    break
        
        if error_lines:
            return "\n".join(error_lines)
        
        # If no specific error found, return last few lines
        if lines:
            return "\n".join(lines[-10:])
        
        return "Pipeline failed (check log for details)"
    
    except Exception as e:
        return f"Failed to read log file: {str(e)}"


def _classify_error(error_message: str) -> str:
    """
    Classify error type from error message for user-friendly display.
    
    Args:
        error_message: Error message string
        
    Returns:
        User-friendly error type string
    """
    error_lower = error_message.lower()
    
    # Check for specific error types
    if "not available in pubmed central" in error_lower or "pmcnotfounderror" in error_lower:
        return "paper_not_found"
    
    if "api key" in error_lower or "authentication" in error_lower or "unauthorized" in error_lower:
        return "api_key_error"
    
    if "timeout" in error_lower:
        return "timeout"
    
    if "quota" in error_lower or "rate limit" in error_lower:
        return "rate_limit"
    
    if "pipeline" in error_lower and "failed" in error_lower:
        return "pipeline_error"
    
    return "unknown_error"


def get_task_status(pmid: str) -> Optional[Dict]:
    """
    Get the status of a video generation task.
    
    This reads the task result file created by the Celery task.
    
    Args:
        pmid: PubMed ID to check
        
    Returns:
        Dict with task status, or None if task not found
    """
    output_dir = Path(settings.MEDIA_ROOT) / pmid
    task_result_file = output_dir / "task_result.json"
    
    if not task_result_file.exists():
        return None
    
    try:
        with open(task_result_file, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read task result for {pmid}: {e}")
        return None


def update_job_progress_from_files(pmid: str, task_id: Optional[str] = None) -> None:
    """
    Update job progress in database based on file existence checks.
    
    This function checks which pipeline steps have completed by looking for
    output files, and updates the database job record accordingly.
    
    Args:
        pmid: PubMed ID
        task_id: Optional task ID to find the job record
    """
    try:
        from web.models import VideoGenerationJob
        
        # Find job by paper_id and optionally task_id
        if task_id:
            try:
                job = VideoGenerationJob.objects.get(task_id=task_id)
            except VideoGenerationJob.DoesNotExist:
                return
        else:
            # Try to find most recent job for this paper_id
            try:
                job = VideoGenerationJob.objects.filter(paper_id=pmid).order_by('-created_at').first()
                if not job:
                    return
            except Exception:
                return
        
        # Only update if job is still running
        if job.status not in ['pending', 'running']:
            return
        
        output_dir = Path(settings.MEDIA_ROOT) / pmid
        
        # Check pipeline steps
        steps = [
            ("fetch-paper", 20, lambda d: (d / "paper.json").exists()),
            ("generate-script", 40, lambda d: (d / "script.json").exists()),
            ("generate-audio", 60, lambda d: (d / "audio.wav").exists() and (d / "audio_metadata.json").exists()),
            ("generate-videos", 80, lambda d: (d / "clips" / ".videos_complete").exists()),
            ("add-captions", 100, lambda d: (d / "final_video.mp4").exists()),
        ]
        
        current_step = None
        progress_percent = 0
        
        for step_name, step_percent, check_func in steps:
            if check_func(output_dir):
                progress_percent = step_percent
            else:
                if current_step is None:
                    current_step = step_name
                break
        
        # Update job if progress changed
        if job.progress_percent != progress_percent or job.current_step != current_step:
            job.progress_percent = progress_percent
            job.current_step = current_step
            if progress_percent == 100:
                final_video = output_dir / "final_video.mp4"
                if final_video.exists():
                    job.status = 'completed'
                    job.final_video_path = str(final_video)
                    job.completed_at = timezone.now()
                    job.current_step = None
            job.save(update_fields=['progress_percent', 'current_step', 'status', 'final_video_path', 'completed_at', 'updated_at'])
    except Exception as e:
        logger.warning(f"Failed to update job progress from files: {e}")

