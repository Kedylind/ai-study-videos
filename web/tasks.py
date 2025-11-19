import logging
from pathlib import Path
import os

from celery import shared_task

from kyle_code import orchestrate_pipeline, PipelineError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, soft_time_limit=60 * 60)
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

    try:
        logger.info("Starting pipeline task for %s -> %s", pmid, out_path)

        # Ensure output directory exists and is writable
        out_path.mkdir(parents=True, exist_ok=True)

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
