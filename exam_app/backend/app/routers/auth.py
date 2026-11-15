from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Exam, User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.security import create_access_token, get_current_user, hash_password, verify_password
from app.logging_config import get_logger, log_event
import logging

logger = get_logger("auth")

router = APIRouter()


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, created_at=user.created_at)


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(user.id), user=_user_out(user))


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    if not username:
        raise HTTPException(status_code=422, detail="Username is required.")
    if db.query(User).filter(User.username == username).first():
        log_event(logger, "auth_register_failed", level=logging.WARNING, username=username, reason="duplicate")
        raise HTTPException(status_code=409, detail="That username is already taken.")

    user = User(username=username, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()

    db.query(Exam).filter(Exam.owner_id.is_(None)).update({Exam.owner_id: user.id}, synchronize_session=False)

    db.commit()
    db.refresh(user)
    log_event(logger, "auth_register", username=username, user_id=user.id)
    return _token_response(user)


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    user = db.query(User).filter(User.username == username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        log_event(logger, "auth_login_failed", level=logging.WARNING, username=username, reason="bad_credentials")
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    log_event(logger, "auth_login", username=username, user_id=user.id)
    return _token_response(user)


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@router.post("/auth/logout")
def logout():
    return {"ok": True}
