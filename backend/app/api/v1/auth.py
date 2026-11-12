import re, secrets
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_token, decode_token
from app.core.deps import CurrentUser
from app.db.session import get_db
from app.models import User, Role, EmailVerificationToken, PasswordResetToken
from app.services.email import send_email

router = APIRouter(prefix="/auth", tags=["auth"])

PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")

class RegisterIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=120)
    email: EmailStr
    phone: str
    password: str = Field(min_length=8, max_length=128)
    date_of_birth: date
    class_level: str = Field(min_length=2, max_length=20)
    school_name: str | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        if not PHONE_RE.match(v.replace(" ", "")):
            raise ValueError("Invalid phone number")
        return v.strip()

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain letters and numbers")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def _age(cls, v: date):
        today = date.today()
        years = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if years < settings.MIN_AGE:
            raise ValueError(f"You must be at least {settings.MIN_AGE} years old to register.")
        if years > 100:
            raise ValueError("Please provide a valid date of birth")
        return v

class LoginIn(BaseModel):
    email: EmailStr
    password: str

@router.post("/register", status_code=201)
async def register(payload: RegisterIn, db: Annotated[AsyncSession, Depends(get_db)]):
    existing = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(409, "Email already registered")

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name.strip(),
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        date_of_birth=payload.date_of_birth,
        class_level=payload.class_level,
        school_name=payload.school_name,
        role=Role.STUDENT,
    )
    db.add(user)
    await db.flush()

    token = secrets.token_urlsafe(32)
    db.add(EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    await db.flush()

    await send_email(
        to=user.email,
        subject="Verify your EduPlat NG account",
        body=f"Open this link to verify your email:\n{settings.FRONTEND_ORIGIN}/verify-email.html?token={token}",
    )
    return {"message": "Registration successful. Check your email to verify your account."}

@router.get("/verify-email")
async def verify_email(token: str, db: Annotated[AsyncSession, Depends(get_db)]):
    row = await db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.token == token))
    if not row or row.used or row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "Invalid or expired token")
    row.used = True
    user = await db.get(User, row.user_id)
    user.is_email_verified = True
    await db.flush()
    return {"message": "Email verified successfully"}

@router.post("/login")
async def login(payload: LoginIn, response: Response,
                db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")

    access = create_token(user.id, "access")
    refresh = create_token(user.id, "refresh")
    response.set_cookie(
        "refresh_token", refresh,
        httponly=True,
        secure=settings.ENV == "prod",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_DAYS * 86400,
        path="/",
    )
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "access_token": access,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_email_verified": user.is_email_verified,
            "class_level": user.class_level,
        },
    }

@router.post("/refresh")
async def refresh(request: Request, response: Response,
                  db: Annotated[AsyncSession, Depends(get_db)]):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(401, "No refresh token")
    try:
        payload = decode_token(rt, "refresh")
    except ValueError:
        raise HTTPException(401, "Invalid refresh token")
    user = await db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(401, "User inactive")

    new_access = create_token(user.id, "access")
    new_refresh = create_token(user.id, "refresh")
    response.set_cookie(
        "refresh_token", new_refresh,
        httponly=True,
        secure=settings.ENV == "prod",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_DAYS * 86400,
        path="/",
    )
    return {"access_token": new_access, "token_type": "bearer"}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out"}

@router.get("/me")
async def me(user: CurrentUser):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "class_level": user.class_level,
        "department_id": user.department_id,
    }

class ResetRequest(BaseModel):
    email: EmailStr

@router.post("/password-reset/request")
async def request_reset(payload: ResetRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user:
        token = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        await db.flush()
        await send_email(
            to=user.email,
            subject="Reset your EduPlat NG password",
            body=f"Reset link (valid 1 hour):\n{settings.FRONTEND_ORIGIN}/reset-password.html?token={token}",
        )
    return {"message": "If the email exists, a reset link has been sent."}

class ResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

@router.post("/password-reset/confirm")
async def confirm_reset(payload: ResetConfirm, db: Annotated[AsyncSession, Depends(get_db)]):
    row = await db.scalar(select(PasswordResetToken).where(PasswordResetToken.token == payload.token))
    if not row or row.used or row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "Invalid or expired token")
    row.used = True
    user = await db.get(User, row.user_id)
    user.hashed_password = hash_password(payload.new_password)
    await db.flush()
    return {"message": "Password updated successfully"}