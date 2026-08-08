from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.router import api_router
from app.config import get_settings
from app.limiter import limiter

settings = get_settings()

app = FastAPI(title="AI CFO Manager", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = [
    o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()
]
if (
    settings.ENVIRONMENT == "development"
    and "http://localhost:3000" not in allowed_origins
):
    allowed_origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT == "production":
        response.headers["Content-Security-Policy"] = "default-src 'self'"
    # Strict-Transport-Security is host-scoped, not port-scoped: once a browser sees
    # it for a host it forces HTTPS for EVERY request to that host, on every port.
    # This deployment is plain HTTP (IP or Cloudflare non-HTTPS proxy port like 8080),
    # so sending HSTS here breaks the site. Only enable it (HSTS_ENABLED=true) once the
    # site is served over real end-to-end HTTPS (domain + SSL).
    if settings.HSTS_ENABLED:
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
    return response


app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
