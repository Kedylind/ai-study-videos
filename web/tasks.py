"""
Celery tasks for video generation pipeline.

This module contains asynchronous tasks that run the video generation pipeline.
Tasks are executed by Celery workers and survive server restarts.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="web.tasks.generate_video_task")
def generate_video_task(self, pmid: str, output_dir: str) -> Dict:
    """
    Celery task to generate video from a PubMed paper.
    
    This task runs the kyle-code pipeline in a subprocess and captures
    all output and errors. Errors are stored in a JSON file for retrieval
    by the status endpoint.
    
    Args:
        pmid: PubMed ID or PMC ID of the paper
        output_dir: Directory path where output files will be saved
        
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
    
    try:
        logger.info(f"Starting video generation task for {pmid}")
        logger.info(f"Task ID: {self.request.id}")
        logger.info(f"Output directory: {output_dir}")
        
        # Update task state
        self.update_state(
            state="PROGRESS",
            meta={"current_step": "starting", "pmid": pmid}
        )
        
        # Use the same Python interpreter
        python_exe = sys.executable
        script_path = Path(settings.BASE_DIR) / "kyle-code" / "main.py"
        
        cmd = [python_exe, str(script_path), "generate-video", pmid, str(output_path)]
        
        env = os.environ.copy()
        
        # Run pipeline and capture output
        with open(log_path, "ab") as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                env=env,
                cwd=str(settings.BASE_DIR),
            )
            
            # Wait for process to complete
            return_code = process.wait()
        
        # Check if pipeline succeeded
        final_video = output_path / "final_video.mp4"
        
        if return_code == 0 and final_video.exists():
            task_result["status"] = "completed"
            logger.info(f"Video generation completed successfully for {pmid}")
        else:
            # Pipeline failed - try to extract error from log
            error_message = _extract_error_from_log(log_path)
            error_type = _classify_error(error_message)
            
            task_result["status"] = "failed"
            task_result["error"] = error_message
            task_result["error_type"] = error_type
            
            logger.error(f"Video generation failed for {pmid}: {error_message}")
            
            # Update task state with error
            self.update_state(
                state="FAILURE",
                meta={
                    "pmid": pmid,
                    "error": error_message,
                    "error_type": error_type,
                }
            )
    
    except Exception as e:
        # Unexpected error in task execution itself
        error_message = f"Task execution error: {str(e)}"
        task_result["status"] = "failed"
        task_result["error"] = error_message
        task_result["error_type"] = "task_error"
        
        logger.exception(f"Unexpected error in video generation task for {pmid}")
        
        # Update task state
        self.update_state(
            state="FAILURE",
            meta={
                "pmid": pmid,
                "error": error_message,
                "error_type": "task_error",
            }
        )
    
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

