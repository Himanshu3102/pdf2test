import os
import time
import uuid
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            traces_sample_rate=0.2,
            profiles_sample_rate=0.1,
            environment=os.getenv("ENV", "production"),
        )
except ImportError:
    pass
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.db import Base, engine
from app.logging_config import setup_logging, get_logger, log_event
from app.routers import health, exams, attempts, chat, auth, gate

setup_logging("DEBUG" if settings.DEBUG else "INFO")
logger = get_logger("app")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    rid = str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - start) * 1000, 1)
    # try to get user from auth header (best effort)
    user_id = None
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            from app.security import decode_access_token
            user_id = decode_access_token(auth[7:])
        except Exception:
            pass
    log_event(logger, "request", method=request.method, path=request.url.path,
              status=response.status_code, duration_ms=elapsed, user_id=user_id,
              client=request.client.host if request.client else None, rid=rid)
    response.headers["X-Request-ID"] = rid
    return response

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# create tables (migrations preferred)
Base.metadata.create_all(bind=engine)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(exams.router, prefix="/api/v1", tags=["exams"])
app.include_router(attempts.router, prefix="/api/v1", tags=["attempts"])
app.include_router(gate.router, prefix="/api/v1", tags=["gate"])

# In-memory error log for debugging (last 50 errors)
_error_log: list[dict] = []

@app.get("/api/v1/debug/errors")
def recent_errors():
    return {"errors": _error_log[-20:], "count": len(_error_log)}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "path": str(request.url.path),
        "method": request.method,
        "error": str(exc),
        "traceback": traceback.format_exc()[-500:],
    }
    _error_log.append(entry)
    if len(_error_log) > 50:
        _error_log.pop(0)
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "status": "ok"}
