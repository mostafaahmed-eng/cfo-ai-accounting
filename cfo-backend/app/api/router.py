from fastapi import APIRouter
from app.api.v1 import auth, companies, accounts, intake, documents, vendors, draft_transactions, approval, journal, telegram, integrations, budgets, exchange_rates, reports, notifications, audit, ai_extraction

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(intake.router, prefix="/intake", tags=["intake"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["vendors"])
api_router.include_router(draft_transactions.router, prefix="/draft-transactions", tags=["draft-transactions"])
api_router.include_router(approval.router, prefix="/approval", tags=["approval"])
api_router.include_router(journal.router, prefix="/journal", tags=["journal"])
api_router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(budgets.router, prefix="/budgets", tags=["budgets"])
api_router.include_router(exchange_rates.router, prefix="/exchange-rates", tags=["exchange-rates"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(ai_extraction.router, prefix="/ai-extraction", tags=["ai-extraction"])
