import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.db import Base, engine
from app.routers import health, exams, attempts, chat, auth

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "status": "ok"}
