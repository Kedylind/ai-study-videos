import os
import json
from pathlib import Path
from typing import Dict, Optional

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .forms import PaperUploadForm
from .tasks import generate_video_task, get_task_status


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


def _validate_access_code(access_code: str) -> bool:
    """Validate the provided access code against the configured code.
    
    Args:
        access_code: The access code to validate
        
    Returns:
        True if the access code is valid, False otherwise
        
    Raises:
        ValueError: If VIDEO_ACCESS_CODE is not configured (server misconfiguration)
    """
    expected_code = os.getenv("VIDEO_ACCESS_CODE")
    
    # Require access code to be configured for security
    if not expected_code:
        raise ValueError(
            "VIDEO_ACCESS_CODE is not configured. "
            "Please set VIDEO_ACCESS_CODE environment variable for security."
        )
    
    # Require access code to be provided
    if not access_code or not access_code.strip():
        return False
    
    # Compare codes (case-sensitive)
    return access_code.strip() == expected_code.strip()


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
        
        return JsonResponse(info, indent=2)
    except Exception as e:
        return JsonResponse({"error": str(e), "type": type(e).__name__}, status=500)


def home(request):
    # Render a small landing page with a link to the upload UI
    return render(request, "index.html")


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
    
    # Check Celery task status for error information
    task_result = None
    if output_dir.exists():
        pmid = output_dir.name
        task_result = get_task_status(pmid)
    
    # Check if pipeline failed (has log but no final video and not currently running)
    log_path = output_dir / "pipeline.log"
    final_video = output_dir / "final_video.mp4"
    
    error = None
    error_type = None
    
    if final_video.exists():
        status = "completed"
    elif task_result and task_result.get("status") == "failed":
        # Task explicitly failed
        status = "failed"
        error = task_result.get("error")
        error_type = task_result.get("error_type")
    elif log_path.exists() and current_step is None and completed_count < total_steps:
        # Check if process is still running by looking for recent log activity
        try:
            import time
            mtime = log_path.stat().st_mtime
            if time.time() - mtime < 60:  # Log updated in last minute
                status = "running"
            else:
                status = "failed"
                # Try to get error from task result
                if task_result:
                    error = task_result.get("error")
                    error_type = task_result.get("error_type")
        except:
            status = "running"
    elif current_step:
        status = "running"
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


def _start_pipeline_async(pmid: str, output_dir: Path):
    """Start the kyle-code pipeline using Celery task queue.

    This uses Celery to run the pipeline asynchronously, which allows
    tasks to survive server restarts and provides better error handling.
    """
    # Start Celery task
    task = generate_video_task.delay(pmid, str(output_dir))
    
    # Task is now queued and will be processed by a Celery worker
    # Status can be checked via the task ID or by reading the task_result.json file


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

            # Start pipeline asynchronously and redirect to status page
            output_dir = Path(settings.MEDIA_ROOT) / pmid
            _start_pipeline_async(pmid, output_dir)

            return HttpResponseRedirect(reverse("pipeline_status", args=[pmid]))
    else:
        form = PaperUploadForm()

    return render(request, "upload.html", {"form": form})


def pipeline_status(request, pmid: str):
    """Return a small status page for a running pipeline and a JSON status endpoint."""
    output_dir = Path(settings.MEDIA_ROOT) / pmid
    final_video = output_dir / "final_video.mp4"
    log_path = output_dir / "pipeline.log"

    if request.GET.get("_json"):
        # JSON status endpoint - use the new progress tracking
        progress = _get_pipeline_progress(output_dir)
        
        status = {
            "pmid": pmid,
            "exists": output_dir.exists(),
            "final_video": final_video.exists(),
            "final_video_url": (
                f"{settings.MEDIA_URL}{pmid}/final_video.mp4" if final_video.exists() else None
            ),
            "status": progress["status"],
            "current_step": progress["current_step"],
            "completed_steps": progress["completed_steps"],
            "progress_percent": progress["progress_percent"],
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
    progress = _get_pipeline_progress(output_dir)
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

    context = {
        "pmid": pmid,
        "final_video_exists": final_video.exists(),
        "final_video_url": f"{settings.MEDIA_URL}{pmid}/final_video.mp4",
        "log_tail": log_tail,
        "progress": progress,
        "error_message": error_message,
    }

    return render(request, "status.html", context)


def pipeline_result(request, pmid: str):
    output_dir = Path(settings.MEDIA_ROOT) / pmid
    final_video = output_dir / "final_video.mp4"
    if final_video.exists():
        return render(request, "result.html", {"pmid": pmid, "video_url": f"{settings.MEDIA_URL}{pmid}/final_video.mp4"})
    else:
        return HttpResponseRedirect(reverse("pipeline_status", args=[pmid]))


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
            paper_id = data.get("paper_id", "").strip()
            access_code = data.get("access_code", "").strip()
        else:
            paper_id = request.POST.get("paper_id", "").strip()
            access_code = request.POST.get("access_code", "").strip()
        
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
        
        # Start the pipeline
        _start_pipeline_async(paper_id, output_dir)
        
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
