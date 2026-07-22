from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def send_notification(self, notification_id: str):
    try:
        pass  # Send via configured channel (in_app, telegram, email)
    except Exception as exc:
        self.retry(exc=exc)
