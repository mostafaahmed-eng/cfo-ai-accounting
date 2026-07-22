from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2)
def generate_monthly_report(self, company_id: str, year: int, month: int):
    try:
        pass  # Generate P&L, balance sheet, cash flow for a month
    except Exception as exc:
        self.retry(exc=exc)
