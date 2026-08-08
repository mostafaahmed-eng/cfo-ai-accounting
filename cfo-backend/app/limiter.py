from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

# Limits are stored in Redis so all uvicorn workers / Celery workers share one
# counter. If Redis is unavailable the limiter degrades gracefully (fail-open)
# instead of breaking requests, and automatically recovers once Redis returns.
# Rate limit headers (X-RateLimit-*, Retry-After) are enabled on all responses.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    in_memory_fallback_enabled=True,
    swallow_errors=True,
    headers_enabled=True,
    retry_after="http-date",
    key_prefix="ai-cfo-ratelimit",
)


def ai_company_key(request: Request) -> str:
    """Per-company key for AI endpoint limits so tenants cannot block each other."""
    company = request.headers.get("X-Company-ID")
    return f"ai:{company}" if company else "ai:unknown"
