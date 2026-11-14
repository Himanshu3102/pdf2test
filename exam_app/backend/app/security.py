import base64
import hashlib
import hmac
import os
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Exam, User

PBKDF2_ITERATIONS = 210_000
_HASH_PREFIX = "pbkdf2_sha256"

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{_HASH_PREFIX}${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        prefix, iterations, salt_hex, hash_hex = stored.split("$")
        if prefix != _HASH_PREFIX:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def _sign(payload: str) -> str:
    return hmac.new(
        settings.AUTH_SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def create_access_token(user_id: str) -> str:
    expires = int(time.time()) + settings.AUTH_TOKEN_TTL_DAYS * 24 * 3600
    payload = f"{user_id}:{expires}"
    raw = f"{payload}:{_sign(payload)}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_access_token(token: str) -> str | None:
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        user_id, expires_s, signature = raw.rsplit(":", 2)
        payload = f"{user_id}:{expires_s}"
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        if int(expires_s) < int(time.time()):
            return None
        return user_id
    except (ValueError, UnicodeDecodeError):
        return None


def _unauthorized(detail: str = "Not authenticated.") -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise _unauthorized("Invalid or expired session.")
    return user


def get_owned_exam(exam_id: str, user: User, db: Session) -> Exam:
    """Return an exam only when it belongs to the current user."""
    exam = db.get(Exam, exam_id)
    if exam is None or exam.owner_id != user.id:
        # 404 avoids leaking whether another user's exam exists.
        raise HTTPException(status_code=404, detail="Exam not found.")
    return exam
