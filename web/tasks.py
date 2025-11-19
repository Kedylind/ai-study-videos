import logging
from pathlib import Path
import os

from celery import shared_task

from kyle_code import orchestrate_pipeline, PipelineError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, soft_time_limit=60 * 60, time_limit=60 * 60 + 30, acks_late=True)
def run_pipeline_task(
    self,
    pmid: str,
    output_dir: str,
    skip_existing: bool = True,
    voice: str = "Kore",
    max_workers: int = 2,
    merge: bool = True,
):
    """Run the end-to-end pipeline in a Celery worker.

    This wrapper is intentionally thin: the heavy work lives in
    `kyle-code/pipeline.py`, which already has idempotency checks.

    Retries are performed for transient exceptions. We avoid retrying on
    explicit PipelineError types that should be handled by the pipeline itself.
    """

    out_path = Path(output_dir)

    # Basic sanity checks
    if orchestrate_pipeline is None:
        msg = "orchestrate_pipeline is not available - check kyle-code import"
        logger.error(msg)
        raise RuntimeError(msg)

    # Prepare a file handler so the web UI (which reads output_dir/pipeline.log)
    # can show task progress. We attach a temporary FileHandler for the
    # duration of the task and remove it afterwards to avoid leaking handlers.
    out_path.mkdir(parents=True, exist_ok=True)
    log_path = out_path / "pipeline.log"

    file_handler = None
    try:
        file_handler = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)

        logger.info("Starting pipeline task for %s -> %s", pmid, out_path)

        # Call into the orchestration function
        orchestrate_pipeline(
            pmid=pmid,
            output_dir=out_path,
            skip_existing=skip_existing,
            stop_after=None,
            voice=voice,
            max_workers=max_workers,
            merge=merge,
        )

        logger.info("Pipeline task complete for %s", pmid)
        return {"status": "success", "output_dir": str(out_path)}

    except PipelineError as e:
        # PipelineError indicates failure in pipeline step; retry may help but avoid infinite loops
        logger.error("PipelineError for %s: %s", pmid, e, exc_info=True)
        try:
            raise self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            logger.exception("Max retries exceeded for pipeline task %s", pmid)
            raise

    except Exception as e:
        # For unexpected exceptions, retry a few times. Celery will record traceback.
        logger.exception("Unexpected error running pipeline for %s: %s", pmid, e)
        try:
            raise self.retry(exc=e, countdown=30)
        except self.MaxRetriesExceededError:
            logger.exception("Max retries exceeded for pipeline task %s", pmid)
            raise
    finally:
        # Ensure file handler is removed and flushed
        if file_handler is not None:
            try:
                file_handler.flush()
                logger.removeHandler(file_handler)
                file_handler.close()
            except Exception:
                logger.exception("Error closing pipeline file handler for %s", pmid)


@shared_task(bind=True, max_retries=2)
def write_marker_task(self, marker_path: str = "/tmp/celery_test_marker.txt", content: str = "OK") -> dict:
    """Write a small marker file (used for smoke tests).

    This task is intentionally simple and idempotent (overwrites the file).
    It returns a dict with the marker path and size written.
    """
    try:
        p = Path(marker_path)
        # Ensure parent exists
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

        size = p.stat().st_size
        logger.info("Wrote marker file %s (size=%d)", p, size)
        return {"marker": str(p), "size": size}
    except Exception as e:
        logger.exception("Failed to write marker file %s: %s", marker_path, e)
        # Retry a couple of times for transient filesystem issues
        try:
            raise self.retry(exc=e, countdown=5)
        except self.MaxRetriesExceededError:
            logger.exception("Max retries exceeded for write_marker_task %s", marker_path)
            raise
