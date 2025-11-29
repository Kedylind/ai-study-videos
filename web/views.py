import os
import logging
from pathlib import Path
from typing import Dict, Optional
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from django.conf import settings

logger = logging.getLogger(__name__)
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .forms import PaperUploadForm
from .tasks import generate_video_task, get_task_status, update_job_progress_from_files, test_volume_write_task
from celery.result import AsyncResult
from config.celery import app as celery_app


def _get_user_friendly_error(error_type: str, error_detail: str = "") -> str:
    """Convert error type to user-friendly error message.
    
    Args:
        error_type: Error type from task classification
        error_detail: Detailed error message
        
    Returns:
        User-friendly error message
    """
    error_messages = {
        "paper_not_found": "Paper not found in PubMed Central. Please check the PubMed ID or PMC ID and ensure the paper is open-access.",
        "api_key_error": "API key invalid or expired. Please contact the administrator.",
        "timeout": "Pipeline timeout. The video generation took too long. Please try again or contact support.",
        "rate_limit": "API rate limit exceeded. Please wait a few minutes and try again.",
        "pipeline_error": f"Video generation failed: {error_detail[:200] if error_detail else 'Unknown error'}",
        "task_error": "Task execution error. Please try again or contact support.",
        "unknown_error": f"An error occurred during video generation: {error_detail[:200] if error_detail else 'Unknown error'}",
    }
    
    return error_messages.get(error_type, error_messages["unknown_error"])


def _validate_access_code(access_code: str | None) -> bool:
    """Validate the provided access code against the configured code.
    
    Args:
        access_code: The access code to validate (can be None)
        
    Returns:
        True if the access code is valid, False otherwise
        
    Raises:
        ValueError: If VIDEO_ACCESS_CODE is not configured (server misconfiguration)
    """
    # Get expected code from Django settings (which loads from environment variable)
    expected_code = settings.VIDEO_ACCESS_CODE
    
    # Require access code to be configured for security
    if not expected_code:
        raise ValueError(
            "VIDEO_ACCESS_CODE is not configured. "
            "Please set VIDEO_ACCESS_CODE environment variable for security."
        )
    
    # Require access code to be provided and not just whitespace
    if not access_code:
        return False
    
    # Convert to string and strip whitespace
    access_code_str = str(access_code).strip()
    expected_code_str = str(expected_code).strip()
    
    if not access_code_str:
        return False
    
    # Compare codes (case-sensitive)
    return access_code_str == expected_code_str


def _validate_paper_id(paper_id: str) -> tuple[bool, str]:
    """
    Validate that a paper ID (PMID or PMCID) exists and is available in PubMed Central.
    
    Args:
        paper_id: PubMed ID (e.g., "12345678") or PMC ID (e.g., "PMC10979640")
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if paper exists and is in PMC, False otherwise
        - error_message: Error message if invalid, empty string if valid
    """
    paper_id = paper_id.strip()
    
    if not paper_id:
        return False, "Please provide a PubMed ID or PMC ID."
    
    try:
        # Determine if input is PMID or PMCID
        if paper_id.upper().startswith("PMC"):
            # It's a PMCID - try to fetch it directly
            pmcid = paper_id.upper()
            pmc_number = pmcid.replace("PMC", "")
            url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmc_number}&retmode=xml"
            
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    xml_data = response.read()
                    # Check if we got valid XML (not an error)
                    root = ET.fromstring(xml_data)
                    # If we can parse it and it has content, it's valid
                    if root is not None:
                        return True, ""
            except urllib.error.HTTPError as e:
                if e.code == 400 or e.code == 404:
                    return False, f"PMC ID '{paper_id}' not found in PubMed Central. Please check the ID and ensure the paper is open-access."
                return False, f"Error checking PMC ID: {e}"
            except ET.ParseError:
                return False, f"PMC ID '{paper_id}' not found or not available in PubMed Central."
            except Exception as e:
                return False, f"Error validating PMC ID: {str(e)}"
        else:
            # It's a PMID - look up the PMCID
            url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={paper_id}&retmode=xml"
            
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    xml_data = response.read()
                    root = ET.fromstring(xml_data)
                    
                    # Look for PMC ID in ArticleIdList
                    pmcid = None
                    for article_id in root.findall(".//ArticleId"):
                        if article_id.get("IdType") == "pmc":
                            pmc_id = article_id.text
                            if not pmc_id.startswith("PMC"):
                                pmc_id = f"PMC{pmc_id}"
                            pmcid = pmc_id
                            break
                    
                    if not pmcid:
                        return False, f"PubMed ID '{paper_id}' is not available in PubMed Central. This tool only works with open-access papers in PMC."
                    
                    # Verify the PMCID is accessible
                    pmc_number = pmcid.replace("PMC", "")
                    pmc_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmc_number}&retmode=xml"
                    
                    try:
                        with urllib.request.urlopen(pmc_url, timeout=10) as pmc_response:
                            pmc_xml = pmc_response.read()
                            ET.fromstring(pmc_xml)  # Verify it's valid XML
                            return True, ""
                    except urllib.error.HTTPError:
                        return False, f"PubMed ID '{paper_id}' is not available in PubMed Central. This tool only works with open-access papers in PMC."
                    except Exception:
                        return False, f"PubMed ID '{paper_id}' is not available in PubMed Central. This tool only works with open-access papers in PMC."
            except urllib.error.HTTPError as e:
                if e.code == 400 or e.code == 404:
                    return False, f"PubMed ID '{paper_id}' not found. Please check the ID and try again."
                return False, f"Error checking PubMed ID: {e}"
            except ET.ParseError:
                return False, f"PubMed ID '{paper_id}' not found or invalid."
            except Exception as e:
                return False, f"Error validating PubMed ID: {str(e)}"
    except Exception as e:
        return False, f"Error validating paper ID: {str(e)}"


def health(request):
    return JsonResponse({"status": "ok"})


def static_debug(request):
    """Debug endpoint to check static files configuration"""
    from django.conf import settings
    from pathlib import Path
    
    try:
        static_root = Path(settings.STATIC_ROOT)
        css_file = static_root / "web" / "css" / "style.css"
        
        info = {
            "STATIC_URL": settings.STATIC_URL,
            "STATIC_ROOT": str(settings.STATIC_ROOT),
            "STATIC_ROOT_exists": static_root.exists(),
            "css_file_path": str(css_file),
            "css_file_exists": css_file.exists(),
            "STATICFILES_STORAGE": settings.STATICFILES_STORAGE,
            "DEBUG": settings.DEBUG,
            "whitenoise_in_middleware": "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE,
        }
        
        # Try to read the file if it exists
        if css_file.exists():
            try:
                info["css_file_size"] = css_file.stat().st_size
                info["css_file_readable"] = True
            except Exception as e:
                info["css_file_readable"] = False
                info["css_file_error"] = str(e)
        
        # List files in staticfiles directory
        if static_root.exists():
            try:
                info["staticfiles_contents"] = [str(p.relative_to(static_root)) for p in static_root.rglob("*") if p.is_file()][:20]
            except Exception as e:
                info["staticfiles_list_error"] = str(e)
        else:
            info["error"] = f"STATIC_ROOT directory does not exist at {static_root}"
            # Try to create it
            try:
                static_root.mkdir(parents=True, exist_ok=True)
                info["created_directory"] = True
            except Exception as e:
                info["create_directory_error"] = str(e)
        
        import json
        response = JsonResponse(info)
        response.content = json.dumps(info, indent=2)
        return response
    except Exception as e:
        return JsonResponse({"error": str(e), "type": type(e).__name__}, status=500)


def debug_media_path(request):
    """
    Debug endpoint to verify Railway volume mounting for persistent storage.
    
    This endpoint checks if MEDIA_ROOT exists, is writable, and shows information
    about the media directory. Use this to verify that Railway volumes are
    mounted correctly.
    
    Access: /debug-media/
    """
    import os
    from pathlib import Path
    from django.conf import settings
    
    try:
        media_root = Path(settings.MEDIA_ROOT)
        base_dir = Path(settings.BASE_DIR)
        
        # Get basic info
        info = {
            "BASE_DIR": str(base_dir),
            "MEDIA_ROOT": str(media_root),
            "MEDIA_URL": settings.MEDIA_URL,
            "MEDIA_ROOT_exists": media_root.exists(),
            "MEDIA_ROOT_is_dir": media_root.is_dir() if media_root.exists() else False,
            "MEDIA_ROOT_writable": os.access(media_root, os.W_OK) if media_root.exists() else False,
            "MEDIA_ROOT_readable": os.access(media_root, os.R_OK) if media_root.exists() else False,
        }
        
        # Check if MEDIA_ROOT is expected path for Railway
        expected_railway_path = "/app/media"
        info["expected_railway_path"] = expected_railway_path
        info["matches_railway_path"] = str(media_root) == expected_railway_path
        
        # Try to list files in media directory
        if media_root.exists():
            try:
                files = list(media_root.iterdir())
                info["files_count"] = len(files)
                info["files_in_media"] = [
                    {
                        "name": f.name,
                        "is_dir": f.is_dir(),
                        "size": f.stat().st_size if f.is_file() else None,
                    }
                    for f in files[:20]  # Limit to first 20 items
                ]
                
                # Check for video directories
                video_dirs = [f.name for f in files if f.is_dir()]
                info["video_directories"] = video_dirs[:10]
                
            except Exception as e:
                info["list_files_error"] = str(e)
        else:
            info["warning"] = "MEDIA_ROOT directory does not exist. This may indicate the Railway volume is not mounted."
            # Try to create it (this will fail if volume isn't mounted, which is useful info)
            try:
                media_root.mkdir(parents=True, exist_ok=True)
                info["created_directory"] = True
                info["created_directory_writable"] = os.access(media_root, os.W_OK)
            except Exception as e:
                info["create_directory_error"] = str(e)
                info["create_directory_error_type"] = type(e).__name__
        
        # Check if we can write a test file
        if media_root.exists() and os.access(media_root, os.W_OK):
            try:
                test_file = media_root / ".test_write"
                test_file.write_text("test")
                test_file.unlink()
                info["test_write_successful"] = True
            except Exception as e:
                info["test_write_successful"] = False
                info["test_write_error"] = str(e)
        
        # Volume mounting verification
        info["volume_mounting_status"] = "OK" if (
            media_root.exists() and 
            os.access(media_root, os.W_OK) and 
            os.access(media_root, os.R_OK)
        ) else "ISSUES DETECTED"
        
        if info["volume_mounting_status"] == "ISSUES DETECTED":
            info["recommendations"] = [
                "Check Railway dashboard → Volumes → Verify mount path is '/app/media'",
                "Verify service is using the volume (should show in service settings)",
                "Check that BASE_DIR resolves to '/app' in Railway",
                "Ensure MEDIA_ROOT = BASE_DIR / 'media' in settings.py",
            ]
        
        import json
        response = JsonResponse(info)
        # Format JSON for readability
        response.content = json.dumps(info, indent=2)
        return response
    except Exception as e:
        import json
        error_data = {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": str(e.__traceback__) if hasattr(e, '__traceback__') else None
        }
        response = JsonResponse(error_data, status=500)
        response.content = json.dumps(error_data, indent=2)
        return response


def test_volume_write(request):
    """
    Test endpoint to verify Railway volume is writable.
    
    This creates a test file in MEDIA_ROOT to verify the volume is working.
    This can be called from the Server service to test if it can access the volume.
    
    Access: /test-volume-write/
    
    Also tests Celery access if ?test_celery=1 is provided.
    """
    import os
    import traceback
    from pathlib import Path
    from django.conf import settings
    from django.utils import timezone
    
    result = {
        "server_test": {},
        "celery_test": {},
    }
    
    # Test Server (Django) access
    try:
        # Ensure MEDIA_ROOT is a Path object
        media_root_str = str(settings.MEDIA_ROOT)
        media_root = Path(media_root_str)
        
        # Create test directory if needed
        test_dir = media_root / ".volume_test"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Write a test file with timestamp
        test_file = test_dir / "test_write_server.txt"
        test_content = f"Volume test - {timezone.now().isoformat()}\nService: Server (Django)\nMEDIA_ROOT: {media_root}"
        test_file.write_text(test_content)
        
        # Verify we can read it back
        read_back = test_file.read_text()
        
        # Get file stats
        file_stats = test_file.stat()
        
        result["server_test"] = {
            "success": True,
            "message": "Volume write test successful",
            "service": "Server (Django)",
            "MEDIA_ROOT": str(media_root),
            "MEDIA_ROOT_type": type(settings.MEDIA_ROOT).__name__,
            "test_file_path": str(test_file),
            "test_file_exists": test_file.exists(),
            "test_file_size": file_stats.st_size,
            "test_file_readable": True,
            "test_content_matches": read_back == test_content,
            "timestamp": timezone.now().isoformat(),
        }
    except Exception as e:
        import sys
        exc_type, exc_value, exc_traceback = sys.exc_info()
        result["server_test"] = {
            "success": False,
            "error": str(e),
            "type": type(e).__name__,
            "service": "Server (Django)",
            "MEDIA_ROOT": str(settings.MEDIA_ROOT) if hasattr(settings, 'MEDIA_ROOT') else "unknown",
            "MEDIA_ROOT_type": type(settings.MEDIA_ROOT).__name__ if hasattr(settings, 'MEDIA_ROOT') else "unknown",
            "traceback": ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            "recommendation": "If this fails, the volume may only be mounted on Celery. You may need to mount it on Server as well.",
        }
    
    # Test Celery access if requested
    if request.GET.get("test_celery") == "1":
        try:
            celery_task = test_volume_write_task.delay()
            celery_result = celery_task.get(timeout=10)
            result["celery_test"] = celery_result
        except Exception as e:
            result["celery_test"] = {
                "success": False,
                "error": str(e),
                "type": type(e).__name__,
                "service": "Celery Worker",
                "recommendation": "Check that Celery worker is running and volume is mounted on Celery service.",
            }
    
    # Overall status
    try:
        server_ok = result.get("server_test", {}).get("success", False)
        celery_test_result = result.get("celery_test", {})
        celery_ok = celery_test_result.get("success", False) if celery_test_result else None
        
        if celery_ok is None:
            # Only tested server
            result["overall_status"] = "OK" if server_ok else "FAILED"
            result["recommendation"] = "Server can access volume" if server_ok else "Server cannot access volume. Mount volume on Server service in Railway."
        else:
            # Tested both
            if server_ok and celery_ok:
                result["overall_status"] = "OK"
                result["recommendation"] = "Both Server and Celery can access the volume. Setup is correct!"
            elif not server_ok and celery_ok:
                result["overall_status"] = "PARTIAL"
                result["recommendation"] = "Celery can write, but Server cannot read. Mount the same volume on Server service in Railway."
            elif server_ok and not celery_ok:
                result["overall_status"] = "PARTIAL"
                result["recommendation"] = "Server can access, but Celery cannot write. Check Celery volume mount in Railway."
            else:
                result["overall_status"] = "FAILED"
                result["recommendation"] = "Neither service can access the volume. Check volume mount configuration in Railway."
        
        status_code = 200 if result.get("overall_status") == "OK" else 500
    except Exception as e:
        result["overall_status"] = "ERROR"
        result["status_calculation_error"] = str(e)
        result["recommendation"] = "Error calculating overall status. Check individual test results."
        status_code = 500
    
    import json
    response = JsonResponse(result, status=status_code)
    response.content = json.dumps(result, indent=2)
    return response


def home(request):
    # Render the beautiful landing page
    return render(request, "landing.html")


def _get_completed_steps_from_progress(progress_percent: int) -> list:
    """Convert progress percent to list of completed step names."""
    steps = [
        ("fetch-paper", 20),
        ("generate-script", 40),
        ("generate-audio", 60),
        ("generate-videos", 80),
        ("add-captions", 100),
    ]
    
    completed_steps = []
    for step_name, step_percent in steps:
        if progress_percent >= step_percent:
            completed_steps.append(step_name)
    
    return completed_steps


def _get_pipeline_progress(output_dir: Path) -> Dict:
    """Check pipeline progress by examining output directory for step completion markers.
    
    Also checks Celery task status for error information.
    
    Returns a dict with:
    - current_step: name of current step or None if complete
    - completed_steps: list of completed step names
    - progress_percent: 0-100
    - status: 'pending', 'running', 'completed', 'failed'
    - error: error message if failed (from Celery task)
    - error_type: user-friendly error type
    """
    steps = [
        ("fetch-paper", lambda d: (d / "paper.json").exists()),
        ("generate-script", lambda d: (d / "script.json").exists()),
        ("generate-audio", lambda d: (d / "audio.wav").exists() and (d / "audio_metadata.json").exists()),
        ("generate-videos", lambda d: (d / "clips" / ".videos_complete").exists()),
        ("add-captions", lambda d: (d / "final_video.mp4").exists()),
    ]
    
    completed_steps = []
    current_step = None
    
    for step_name, check_func in steps:
        if check_func(output_dir):
            completed_steps.append(step_name)
        else:
            if current_step is None:
                current_step = step_name
            break
    
    total_steps = len(steps)
    completed_count = len(completed_steps)
    progress_percent = int((completed_count / total_steps) * 100)
    
    # Check if pipeline failed (has log but no final video and not currently running)
    log_path = output_dir / "pipeline.log"
    final_video = output_dir / "final_video.mp4"
    
    error = None
    error_type = None
    status = "pending"  # Initialize status
    
    # Priority 0: Check if final video exists (completed) - this is the most definitive check
    # Check this FIRST before anything else - if video exists, we're done
    if output_dir.exists() and final_video.exists():
        status = "completed"
        return {
            "current_step": None,
            "completed_steps": completed_steps,
            "progress_percent": 100,
            "status": "completed",
            "total_steps": total_steps,
        }
    
    # Check Celery task status for error information FIRST (most reliable)
    # Method 1: Try to get task status directly from Celery's result backend
    task_result = None
    pmid = output_dir.name
    task_id_file = output_dir / "task_id.txt"
    
    # Try to get task status from Celery result backend first (most reliable)
    if task_id_file.exists():
        try:
            with open(task_id_file, "r") as f:
                task_id = f.read().strip()
            if task_id:
                async_result = AsyncResult(task_id, app=celery_app)
                if async_result.ready():
                    # Task has completed (success or failure)
                    try:
                        result = async_result.get(timeout=1)  # Quick timeout
                        if isinstance(result, dict):
                            task_result = result
                            # Ensure status is set correctly
                            if async_result.failed():
                                task_result["status"] = "failed"
                            elif async_result.successful() and result.get("status") == "failed":
                                # Task succeeded from Celery's perspective but pipeline failed
                                task_result["status"] = "failed"
                    except Exception as e:
                        # If we can't get result, check if task failed
                        if async_result.failed():
                            try:
                                task_result = {
                                    "status": "failed",
                                    "error": str(async_result.info) if async_result.info else "Task failed",
                                    "error_type": "task_error"
                                }
                            except:
                                pass
        except Exception:
            pass  # Fall through to file-based check
    
    # Method 2: Fall back to reading task_result.json file
    if not task_result:
        task_result = get_task_status(pmid)
    
    # Priority 1: Check task result FIRST (most reliable source of truth)
    # This should be checked before anything else to catch failures immediately
    if task_result:
        task_status = task_result.get("status")
        if task_status == "failed":
            status = "failed"
            error = task_result.get("error")
            error_type = task_result.get("error_type")
            # Don't check anything else - task result is definitive
        elif task_status == "completed":
            # Verify final video exists to confirm completion
            if final_video.exists():
                status = "completed"
            else:
                # Task says completed but video doesn't exist - might still be processing
                status = "running"
        elif task_status == "running":
            # Task says running, but check log for failure indicators (task might have failed but not updated status yet)
            if log_path.exists():
                try:
                    with open(log_path, "rb") as f:
                        f.seek(max(0, f.tell() - 8192))
                        log_content = f.read().decode(errors="replace")
                        # Check for various failure indicators in log
                        log_lower = log_content.lower()
                        if ("pipeline failed" in log_lower or 
                            ("✗" in log_content and "failed" in log_lower) or
                            "http error" in log_lower or
                            "bad request" in log_lower or
                            "step 'fetch-paper' failed" in log_lower):
                            # Log shows failure even though task says running - trust the log
                            status = "failed"
                            # Extract error from log
                            lines = log_content.split("\n")
                            for line in reversed(lines):
                                if (("✗" in line or "failed" in line.lower() or "error" in line.lower()) and 
                                    line.strip() and 
                                    not line.strip().startswith("2025-")):  # Skip timestamp-only lines
                                    if not error:
                                        error = line.strip()
                                    break
                            if not error_type and error:
                                error_lower = error.lower()
                                if "not available in pubmed central" in error_lower:
                                    error_type = "paper_not_found"
                                elif "http error 400" in error_lower or "bad request" in error_lower:
                                    error_type = "pipeline_error"
                                elif "http error 400" in error_lower or "bad request" in error_lower:
                                    error_type = "pipeline_error"
                except:
                    pass
            if status != "failed":
                status = "running"
        else:
            # Task result exists but status is unclear, check other indicators
            if current_step:
                status = "running"
            elif log_path.exists():
                # Check log for failure indicators first
                try:
                    with open(log_path, "rb") as f:
                        f.seek(max(0, f.tell() - 8192))
                        log_content = f.read().decode(errors="replace")
                        if "pipeline failed" in log_content.lower() or ("✗" in log_content and "failed" in log_content.lower()):
                            status = "failed"
                            # Extract error
                            lines = log_content.split("\n")
                            for line in reversed(lines):
                                if ("✗" in line or "failed" in line.lower()) and line.strip():
                                    if not error:
                                        error = line.strip()
                                    break
                except:
                    pass
                
                # If still not failed, check timestamp
                if status != "failed":
                    try:
                        import time
                        mtime = log_path.stat().st_mtime
                        if time.time() - mtime < 120:  # Recent activity
                            status = "running"
                        else:
                            status = "failed"
                            error = task_result.get("error")
                            error_type = task_result.get("error_type")
                    except:
                        status = "running"
            else:
                status = "pending"
    # Priority 2: Check if final video exists (completed)
    elif final_video.exists():
        status = "completed"
    # Priority 3: Check if log exists and determine if still running or failed
    elif log_path.exists():
        try:
            import time
            mtime = log_path.stat().st_mtime
            time_since_update = time.time() - mtime
            
            # Check log content for failure indicators first
            log_has_error = False
            try:
                with open(log_path, "rb") as f:
                    f.seek(max(0, f.tell() - 8192))
                    log_content = f.read().decode(errors="replace")
                    # Check for explicit failure messages
                    log_lower = log_content.lower()
                    if ("pipeline failed" in log_lower or 
                        "✗" in log_content or
                        "http error" in log_lower or
                        "bad request" in log_lower or
                        "step 'fetch-paper' failed" in log_lower):
                        log_has_error = True
                        # Extract error message
                        lines = log_content.split("\n")
                        for line in reversed(lines):
                            if (("✗" in line or "failed" in line.lower() or "error" in line.lower()) and 
                                line.strip() and
                                not line.strip().startswith("2025-")):  # Skip timestamp-only lines
                                if not error:  # Only set if we don't already have error from task_result
                                    error = line.strip()
                                    # Classify error type
                                    if "not available in pubmed central" in line.lower():
                                        error_type = "paper_not_found"
                                    elif "http error 400" in line.lower() or "bad request" in line.lower():
                                        error_type = "pipeline_error"
                                break
            except:
                pass
            
            # If log was updated recently (within 2 minutes)
            if time_since_update < 120:
                # But if log shows an error, it's failed (even if recent)
                if log_has_error:
                    status = "failed"
                    if not error_type and error:
                        # Classify error if we haven't already
                        error_lower = error.lower()
                        if "not available in pubmed central" in error_lower:
                            error_type = "paper_not_found"
                        elif "api key" in error_lower:
                            error_type = "api_key_error"
                elif current_step:
                    status = "running"
                else:
                    status = "pending"
            else:
                # Log hasn't been updated in 2+ minutes and no final video = likely failed
                status = "failed"
                # Use error from log if we found one
                if not error and log_has_error:
                    # Try to extract error from log again
                    try:
                        with open(log_path, "rb") as f:
                            f.seek(max(0, f.tell() - 8192))
                            log_content = f.read().decode(errors="replace")
                            lines = log_content.split("\n")
                            for line in reversed(lines):
                                if ("✗" in line or "failed" in line.lower()) and line.strip():
                                    error = line.strip()
                                    break
                    except:
                        pass
        except Exception:
            # If we can't check log, default based on current step
            status = "running" if current_step else "pending"
    # Priority 4: If there's a current step, it's running
    elif current_step:
        status = "running"
    # Priority 5: Otherwise pending
    else:
        status = "pending"
    
    result = {
        "current_step": current_step,
        "completed_steps": completed_steps,
        "progress_percent": progress_percent,
        "status": status,
        "total_steps": total_steps,
    }
    
    # Add error information if available
    if error:
        result["error"] = error
    if error_type:
        result["error_type"] = error_type
    
    return result


def _start_pipeline_async(pmid: str, output_dir: Path, user_id: Optional[int] = None):
    """Start the video generation pipeline using Celery task queue.

    This uses Celery to run the pipeline asynchronously, which allows
    tasks to survive server restarts and provides better error handling.
    
    Args:
        pmid: PubMed ID or paper identifier
        output_dir: Output directory path
        user_id: Optional user ID to associate with the job
    """
    # Start Celery task
    task = generate_video_task.delay(pmid, str(output_dir), user_id)
    
    # Store task ID in a file so we can check status via Celery's result backend
    task_id_file = output_dir / "task_id.txt"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(task_id_file, "w") as f:
        f.write(task.id)
    
    # Create or update database job record
    # This ensures the job exists in the database immediately, even before the Celery task starts
    if user_id:
        try:
            from django.contrib.auth.models import User
            from web.models import VideoGenerationJob
            try:
                user = User.objects.get(pk=user_id)
                job, created = VideoGenerationJob.objects.get_or_create(
                    task_id=task.id,
                    defaults={
                        'user': user,
                        'paper_id': pmid,
                        'status': 'pending',
                        'progress_percent': 0,
                        'current_step': None,
                    }
                )
                if not created:
                    # Update existing job (shouldn't happen, but handle it gracefully)
                    job.status = 'pending'
                    job.progress_percent = 0
                    job.current_step = None
                    job.paper_id = pmid  # Update paper_id in case it changed
                    job.save(update_fields=['status', 'progress_percent', 'current_step', 'paper_id', 'updated_at'])
                logger.info(f"Created/updated job record for {pmid} with task_id {task.id}")
            except User.DoesNotExist:
                logger.warning(f"User {user_id} does not exist, skipping database job tracking")
            except Exception as db_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to create/update job record in database: {db_error}", exc_info=True)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create job record: {e}", exc_info=True)
    
    # Task is now queued and will be processed by a Celery worker
    # Status can be checked via the task ID (Celery result backend) or by reading the task_result.json file


@login_required
def upload_paper(request):
    """Simple UI to accept a PubMed ID/PMCID and start the pipeline."""
    if request.method == "POST":
        form = PaperUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Validate access code
            access_code = form.cleaned_data.get("access_code", "")
            try:
                if not _validate_access_code(access_code):
                    form.add_error("access_code", "Invalid access code. Please check and try again.")
                    return render(request, "upload.html", {"form": form})
            except ValueError as e:
                # Server misconfiguration - access code not set
                form.add_error(None, f"Server configuration error: {e}")
                return render(request, "upload.html", {"form": form})
            
            pmid = form.cleaned_data.get("paper_id")
            # If a file is uploaded we save it and use a folder named by filename
            uploaded = form.cleaned_data.get("file")

            if uploaded:
                # Save uploaded file into media/<basename>/uploaded_file
                name = Path(uploaded.name).stem
                out_dir = Path(settings.MEDIA_ROOT) / name
                out_dir.mkdir(parents=True, exist_ok=True)
                file_path = out_dir / uploaded.name
                with open(file_path, "wb") as f:
                    for chunk in uploaded.chunks():
                        f.write(chunk)

                # TODO: support pipeline from local file; for now, return to status page
                # We'll treat 'name' as an identifier
                pmid = name
            else:
                if not pmid:
                    form.add_error(None, "Provide a PubMed ID or upload a file")
                    return render(request, "upload.html", {"form": form})

                # Normalize pmid
                pmid = pmid.strip()
                
                # Skip validation for test IDs in simulation mode (e.g., TEST123, TEST456)
                # This allows testing the upload flow without validating against PubMed
                if settings.SIMULATION_MODE and pmid.upper().startswith("TEST"):
                    logger.info(f"Simulation mode: Skipping paper ID validation for test ID: {pmid}")
                else:
                    # Validate paper ID before starting pipeline
                    is_valid, error_message = _validate_paper_id(pmid)
                    if not is_valid:
                        form.add_error("paper_id", error_message)
                        return render(request, "upload.html", {"form": form})

            # Start pipeline asynchronously and redirect to status page
            output_dir = Path(settings.MEDIA_ROOT) / pmid
            user_id = request.user.id if request.user.is_authenticated else None
            _start_pipeline_async(pmid, output_dir, user_id)

            return HttpResponseRedirect(reverse("pipeline_status", args=[pmid]))
    else:
        form = PaperUploadForm()

    return render(request, "upload.html", {"form": form})


def pipeline_status(request, pmid: str):
    """Return a small status page for a running pipeline and a JSON status endpoint."""
    output_dir = Path(settings.MEDIA_ROOT) / pmid
    final_video = output_dir / "final_video.mp4"
    log_path = output_dir / "pipeline.log"

    # Try to get progress from database first
    progress = None
    try:
        from web.models import VideoGenerationJob
        
        # Try to find job for this paper_id and user (if authenticated)
        if request.user.is_authenticated:
            try:
                job = VideoGenerationJob.objects.get(paper_id=pmid, user=request.user)
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
                    update_job_progress_from_files(pmid, task_id)
                    job.refresh_from_db()
                
                # Convert job to progress dict
                completed_steps = _get_completed_steps_from_progress(job.progress_percent)
                progress = {
                    "status": job.status,
                    "current_step": job.current_step,
                    "completed_steps": completed_steps,
                    "progress_percent": job.progress_percent,
                    "total_steps": 5,
                }
                if job.status == 'failed':
                    progress["error"] = job.error_message
                    progress["error_type"] = job.error_type
            except VideoGenerationJob.DoesNotExist:
                pass  # Fall through to file-based check
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error getting progress from database: {e}")

    # Fallback to file-based progress if database doesn't have it
    if progress is None:
        try:
            progress = _get_pipeline_progress(output_dir)
        except Exception as e:
            # Fallback progress dict if _get_pipeline_progress fails
            import logging
            logger = logging.getLogger(__name__)
            logger.exception(f"Error getting pipeline progress for {pmid}: {e}")
            progress = {
                "status": "pending",
                "current_step": None,
                "completed_steps": [],
                "progress_percent": 0,
                "total_steps": 5,
            }

    if request.GET.get("_json"):
        # JSON status endpoint - use the new progress tracking
        status = {
            "pmid": pmid,
            "exists": output_dir.exists(),
            "final_video": final_video.exists(),
            "final_video_url": (
                f"{settings.MEDIA_URL}{pmid}/final_video.mp4" if final_video.exists() else None
            ),
            "status": progress.get("status", "pending"),
            "current_step": progress.get("current_step"),
            "completed_steps": progress.get("completed_steps", []),
            "progress_percent": progress.get("progress_percent", 0),
        }
        
        # Add error information if available
        if "error" in progress:
            status["error"] = progress["error"]
        if "error_type" in progress:
            status["error_type"] = progress["error_type"]
            # Add user-friendly error message
            status["error_message"] = _get_user_friendly_error(progress["error_type"], progress.get("error", ""))
        
        # include tail of log if present
        if log_path.exists():
            try:
                with open(log_path, "rb") as f:
                    f.seek(max(0, f.tell() - 8192))
                    data = f.read().decode(errors="replace")
            except Exception:
                data = ""
            status["log_tail"] = data

        return JsonResponse(status)

    # Render an HTML status page
    log_tail = ""
    if log_path.exists():
        try:
            with open(log_path, "rb") as f:
                f.seek(max(0, f.tell() - 8192))
                log_tail = f.read().decode(errors="replace")
        except Exception:
            log_tail = "(could not read log)"
    
    # Get user-friendly error message
    error_message = None
    if progress.get("error_type"):
        error_message = _get_user_friendly_error(progress["error_type"], progress.get("error", ""))

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

    return render(request, "status.html", context)


def pipeline_result(request, pmid: str):
    output_dir = Path(settings.MEDIA_ROOT) / pmid
    final_video = output_dir / "final_video.mp4"
    if final_video.exists():
        # Use dedicated video endpoint
        video_url = reverse("serve_video", args=[pmid])
        return render(request, "result.html", {"pmid": pmid, "video_url": video_url})
    else:
        return HttpResponseRedirect(reverse("pipeline_status", args=[pmid]))


@login_required
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
        logger.error(f"Error serving video for {pmid}: {e}")
        return HttpResponse("Error serving video", status=500)


@login_required
def my_videos(request):
    """Display all videos generated by the current user."""
    try:
        from web.models import VideoGenerationJob
        
        # Get all jobs for the current user
        jobs = VideoGenerationJob.objects.filter(user=request.user).order_by('-created_at')
        
        # Add video URL and metadata for each job
        videos = []
        for job in jobs:
            try:
                video_data = {
                    'job': job,
                    'paper_id': job.paper_id or 'Unknown',
                    'status': job.status or 'pending',
                    'progress_percent': job.progress_percent or 0,
                    'current_step': job.current_step,
                    'created_at': job.created_at,
                    'completed_at': job.completed_at,
                    'error_message': job.error_message if job.status == 'failed' else None,
                    'error_type': job.error_type if job.status == 'failed' else None,
                    'video_url': None,
                    'has_video': False,
                }
                
                # Check if video file exists
                if job.status == 'completed' and job.paper_id:
                    try:
                        video_path = Path(settings.MEDIA_ROOT) / job.paper_id / "final_video.mp4"
                        if video_path.exists():
                            video_data['has_video'] = True
                            video_data['video_url'] = reverse('serve_video', args=[job.paper_id])
                    except Exception as e:
                        logger.warning(f"Error checking video file for job {job.id}: {e}")
                
                videos.append(video_data)
            except Exception as e:
                logger.error(f"Error processing job {job.id if hasattr(job, 'id') else 'unknown'}: {e}")
                # Skip this job and continue with others
                continue
        
        return render(request, 'my_videos.html', {'videos': videos})
    except Exception as e:
        logger.exception(f"Error in my_videos view: {e}")
        # Return a user-friendly error page
        from django.http import HttpResponseServerError
        return render(request, 'my_videos.html', {
            'videos': [],
            'error': 'An error occurred while loading your videos. Please try again later.'
        })


def register(request):
    """User registration view."""
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = UserCreationForm()
    return render(request, "registration/register.html", {"form": form})


# ============================================================================
# API ENDPOINTS
# ============================================================================

@require_http_methods(["POST"])
@csrf_exempt  # For API usage, you may want to use proper API authentication instead
def api_start_generation(request):
    """API endpoint to start video generation from a PubMed ID.
    
    POST /api/generate/
    Body (JSON):
    {
        "paper_id": "PMC10979640",  # or PMID like "33963468"
        "access_code": "your-access-code"  # Required access code
    }
    
    Returns:
    {
        "success": true,
        "paper_id": "PMC10979640",
        "status_url": "/api/status/PMC10979640/",
        "message": "Pipeline started"
    }
    """
    try:
        if request.content_type == 'application/json':
            import json
            data = json.loads(request.body)
            paper_id = (data.get("paper_id") or "").strip()
            access_code = data.get("access_code") or ""
        else:
            paper_id = (request.POST.get("paper_id") or "").strip()
            access_code = request.POST.get("access_code") or ""
        
        if not paper_id:
            return JsonResponse(
                {"success": False, "error": "paper_id is required"},
                status=400
            )
        
        # Validate access code
        try:
            if not _validate_access_code(access_code):
                return JsonResponse(
                    {"success": False, "error": "Invalid or missing access_code"},
                    status=403  # Forbidden
                )
        except ValueError as e:
            # Server misconfiguration - access code not set
            return JsonResponse(
                {"success": False, "error": f"Server configuration error: {str(e)}"},
                status=500  # Internal Server Error
            )
        
        # Validate API keys are set
        if not os.getenv("GEMINI_API_KEY"):
            return JsonResponse(
                {"success": False, "error": "GEMINI_API_KEY environment variable not set"},
                status=500
            )
        
        if not os.getenv("RUNWAYML_API_SECRET"):
            return JsonResponse(
                {"success": False, "error": "RUNWAYML_API_SECRET environment variable not set"},
                status=500
            )
        
        # Start pipeline
        output_dir = Path(settings.MEDIA_ROOT) / paper_id
        
        # Check if already running or completed
        progress = _get_pipeline_progress(output_dir)
        if progress["status"] == "running":
            return JsonResponse(
                {
                    "success": False,
                    "error": "Pipeline already running for this paper_id",
                    "status_url": f"/api/status/{paper_id}/"
                },
                status=409  # Conflict
            )
        
        # Don't restart if already completed
        if progress["status"] == "completed":
            return JsonResponse(
                {
                    "success": True,
                    "paper_id": paper_id,
                    "status_url": f"/api/status/{paper_id}/",
                    "result_url": f"/api/result/{paper_id}/",
                    "message": "Video already generated"
                }
            )
        
        # Get user ID if authenticated (API may not require auth, so this is optional)
        user_id = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = request.user.id
        
        # Start the pipeline
        _start_pipeline_async(paper_id, output_dir, user_id)
        
        return JsonResponse({
            "success": True,
            "paper_id": paper_id,
            "status_url": f"/api/status/{paper_id}/",
            "result_url": f"/api/result/{paper_id}/",
            "message": "Pipeline started successfully"
        })
        
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON in request body"},
            status=400
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": str(e)},
            status=500
        )


@require_http_methods(["GET"])
def api_status(request, paper_id: str):
    """API endpoint to check pipeline status.
    
    GET /api/status/<paper_id>/
    
    Returns:
    {
        "paper_id": "PMC10979640",
        "status": "running",  # pending, running, completed, failed
        "current_step": "generate-videos",
        "completed_steps": ["fetch-paper", "generate-script", "generate-audio"],
        "progress_percent": 60,
        "final_video_url": "/media/PMC10979640/final_video.mp4" or null,
        "log_tail": "last 8KB of log file"
    }
    """
    output_dir = Path(settings.MEDIA_ROOT) / paper_id
    
    # Try to get progress from database first
    progress = None
    try:
        from web.models import VideoGenerationJob
        
        # Try to find most recent job for this paper_id
        # If user is authenticated, prefer their job
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                job = VideoGenerationJob.objects.filter(paper_id=paper_id, user=request.user).order_by('-created_at').first()
            except:
                job = None
        else:
            job = None
        
        if not job:
            # Try to find any job for this paper_id
            try:
                job = VideoGenerationJob.objects.filter(paper_id=paper_id).order_by('-created_at').first()
            except:
                job = None
        
        if job:
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
                update_job_progress_from_files(paper_id, task_id)
                job.refresh_from_db()
            
            # Convert job to progress dict
            completed_steps = _get_completed_steps_from_progress(job.progress_percent)
            progress = {
                "status": job.status,
                "current_step": job.current_step,
                "completed_steps": completed_steps,
                "progress_percent": job.progress_percent,
            }
            if job.status == 'failed':
                progress["error"] = job.error_message
                progress["error_type"] = job.error_type
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error getting progress from database in API: {e}")
    
    # Fallback to file-based progress
    if progress is None:
        progress = _get_pipeline_progress(output_dir)
    
    final_video = output_dir / "final_video.mp4"
    final_video_url = None
    if final_video.exists():
        final_video_url = f"{settings.MEDIA_URL}{paper_id}/final_video.mp4"
    
    # Get log tail
    log_path = output_dir / "pipeline.log"
    log_tail = ""
    if log_path.exists():
        try:
            with open(log_path, "rb") as f:
                f.seek(max(0, f.tell() - 8192))
                log_tail = f.read().decode(errors="replace")
        except Exception:
            log_tail = "(could not read log)"
    
    response = {
        "paper_id": paper_id,
        "status": progress["status"],
        "current_step": progress["current_step"],
        "completed_steps": progress["completed_steps"],
        "progress_percent": progress["progress_percent"],
        "final_video_url": final_video_url,
        "log_tail": log_tail,
    }
    
    return JsonResponse(response)


@require_http_methods(["GET"])
def api_result(request, paper_id: str):
    """API endpoint to get the final video result.
    
    GET /api/result/<paper_id>/
    
    Returns:
    {
        "paper_id": "PMC10979640",
        "success": true,
        "video_url": "/media/PMC10979640/final_video.mp4",
        "status": "completed"
    }
    or
    {
        "paper_id": "PMC10979640",
        "success": false,
        "error": "Video not ready yet",
        "status": "running",
        "status_url": "/api/status/PMC10979640/"
    }
    """
    output_dir = Path(settings.MEDIA_ROOT) / paper_id
    final_video = output_dir / "final_video.mp4"
    
    progress = _get_pipeline_progress(output_dir)
    
    if final_video.exists():
        return JsonResponse({
            "paper_id": paper_id,
            "success": True,
            "video_url": f"{settings.MEDIA_URL}{paper_id}/final_video.mp4",
            "status": "completed",
            "progress_percent": 100,
        })
    else:
        return JsonResponse({
            "paper_id": paper_id,
            "success": False,
            "error": "Video not ready yet",
            "status": progress["status"],
            "progress_percent": progress["progress_percent"],
            "status_url": f"/api/status/{paper_id}/",
        }, status=202)  # Accepted but not ready
