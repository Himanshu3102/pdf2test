import os
import time
import uuid
from fastapi import FastAPI, Request
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


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "status": "ok"}
