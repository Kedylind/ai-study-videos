"""
Lightweight compatibility package to expose the existing `kyle-code` scripts
as importable modules (Python package name uses underscore). This file adds
the `kyle-code` directory to `sys.path` at runtime so we can import `pipeline`
and other modules from Django/Celery tasks without renaming the original folder.

This keeps the on-disk layout unchanged while providing a clean import path
(`import kyle_code.pipeline`).
"""
from pathlib import Path
import sys
import logging

logger = logging.getLogger(__name__)

# Insert the repo root/kyle-code into sys.path so `import pipeline` works
BASE_DIR = Path(__file__).resolve().parent.parent
external = BASE_DIR / "kyle-code"
if str(external) not in sys.path:
    sys.path.insert(0, str(external))
    logger.debug("Inserted kyle-code path into sys.path: %s", external)

# Re-export commonly used pipeline functions for convenience
try:
    from pipeline import orchestrate_pipeline, PipelineError  # type: ignore
except Exception:
    # If imports fail, keep module importable; errors will be raised when tasks run.
    orchestrate_pipeline = None  # type: ignore
    PipelineError = Exception  # type: ignore

__all__ = ["orchestrate_pipeline", "PipelineError"]
