from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2)
def post_journal_entry(self, journal_entry_id: str):
    try:
        pass  # Validate balanced, post entry, update draft status
    except Exception as exc:
        self.retry(exc=exc)
