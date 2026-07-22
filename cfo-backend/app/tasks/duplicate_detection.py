from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def detect_duplicates(self, company_id: str, draft_transaction_id: str):
    try:
        pass  # Check for duplicate amount/vendor/date within company
    except Exception as exc:
        self.retry(exc=exc)
