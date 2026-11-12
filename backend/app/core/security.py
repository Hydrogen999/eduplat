from datetime import datetime, timedelta, timezone
from typing import Literal
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from jose import jwt, JWTError
from app.core.config import settings

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

def hash_password(plain: str) -> str:
    return _hasher.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError):
        return False

TokenKind = Literal["access", "refresh", "email_verify", "password_reset"]

def create_token(sub: str, kind: TokenKind, minutes: int | None = None) -> str:
    if minutes is None:
        minutes = settings.ACCESS_TOKEN_MINUTES if kind == "access" else settings.REFRESH_TOKEN_DAYS * 1440
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub, "kind": kind,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str, expected_kind: TokenKind) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise ValueError("Invalid or expired token") from e
    if payload.get("kind") != expected_kind:
        raise ValueError("Wrong token kind")
    return payload