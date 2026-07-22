from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_receipt(self, inbox_item_id: str, document_id: str):
    try:
        pass  # Process receipt: download from S3, detect MIME, validate, queue AI extraction
    except Exception as exc:
        self.retry(exc=exc)
