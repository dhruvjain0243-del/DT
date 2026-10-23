from __future__ import annotations

import threading
import time
import smtplib
import secrets
import httpx
from email.message import EmailMessage
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from ..core.config import get_settings
from ..core.security import TokenError, create_email_verification_token, create_token_pair, decode_token, hash_password, verify_password
from ..dependencies import CurrentUser, DbSession, oauth2_scheme
from ..models import RevokedToken, User, UserRole
from ..schemas.auth import LogoutRequest, RefreshRequest, SupabaseSessionRequest, TokenResponse, UserRead, UserRegister
from ..schemas.common import MessageResponse


router = APIRouter(prefix="/api/auth", tags=["authentication"])
_attempts: dict[str, deque[float]] = defaultdict(deque)
_attempt_lock = threading.Lock()


def _check_login_rate_limit(client_key: str, limit: int = 10, window_seconds: int = 60) -> None:
    now = time.monotonic()
    with _attempt_lock:
        bucket = _attempts[client_key]
        while bucket and bucket[0] < now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status_code=429, detail="Too many login attempts; try again later")
        bucket.append(now)


def _token_response(user: User) -> TokenResponse:
    pair = create_token_pair(user.id, user.role.value)
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
        user=UserRead.model_validate(user),
    )


def _revoke(db: DbSession, payload: dict) -> None:
    jti = str(payload["jti"])
    if db.scalar(select(RevokedToken.id).where(RevokedToken.jti == jti)):
        return
    expires_at = datetime.fromtimestamp(float(payload["exp"]), tz=UTC)
    db.add(RevokedToken(jti=jti, expires_at=expires_at))


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: DbSession) -> User:
    email = data.email.lower()
    duplicate = db.scalar(select(User.id).where(User.email == email))
    if duplicate:
        raise HTTPException(status_code=409, detail="Email already exists")
    user = User(
        full_name=data.full_name.strip(),
        email=email,
        phone=data.phone.strip() if data.phone else None,
        password_hash=hash_password(data.password),
        role=data.role,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/supabase-session", response_model=TokenResponse)
def create_supabase_session(
    data: SupabaseSessionRequest,
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> TokenResponse:
    """Bridge a verified Supabase Auth session into the existing PARKWISE API session."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(status_code=503, detail="Supabase authentication is not configured on the server")
    try:
        response = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={"apikey": settings.supabase_publishable_key, "Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Supabase authentication is unavailable") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Supabase session")
    remote = response.json()
    if not remote.get("email") or not remote.get("email_confirmed_at"):
        raise HTTPException(status_code=403, detail="Verify your email before signing in")
    email = str(remote["email"]).lower()
    supabase_user_id = str(remote["id"])
    user = db.scalar(select(User).where(User.supabase_user_id == supabase_user_id))
    if not user:
        user = db.scalar(select(User).where(User.email == email))
    metadata = remote.get("user_metadata") or {}
    if not user:
        user = User(
            full_name=(data.full_name or metadata.get("full_name") or email.split("@", 1)[0]).strip(),
            email=email,
            phone=data.phone,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role=UserRole.STUDENT,
            email_verified=True,
        )
        db.add(user)
        db.flush()
    user.supabase_user_id = supabase_user_id
    user.email_verified = True
    if data.full_name:
        user.full_name = data.full_name.strip()
    if data.phone is not None:
        user.phone = data.phone
    db.commit()
    db.refresh(user)
    return _token_response(user)


def _send_verification_email(user: User) -> None:
    settings = get_settings()
    if not settings.email_provider_configured:
        raise HTTPException(status_code=503, detail="Email verification is not configured. Set the server SMTP settings first.")
    token = create_email_verification_token(user.id)
    message = EmailMessage()
    message["Subject"] = "Verify your PARKWISE email"
    message["From"] = settings.email_from
    message["To"] = user.email
    message.set_content(f"Verify your PARKWISE account by opening:\n\n{settings.email_verify_base_url}?token={token}\n\nThis link expires in 24 hours.")
    try:
        with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(settings.email_smtp_username, settings.email_smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise HTTPException(status_code=502, detail="The verification email could not be sent by the configured provider") from exc


@router.post("/verify-email/request", response_model=MessageResponse)
def request_email_verification(email: str, db: DbSession) -> MessageResponse:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or user.email_verified:
        return MessageResponse(message="If the account exists and needs verification, a message will be sent.")
    _send_verification_email(user)
    return MessageResponse(message="Verification email sent. Check your mailbox before signing in.")


@router.get("/verify-email", response_class=Response)
def verify_email(token: str, db: DbSession) -> Response:
    try:
        payload = decode_token(token, "email_verify")
        user = db.get(User, int(payload["sub"]))
    except (TokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link") from exc
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")
    user.email_verified = True
    db.commit()
    return Response("<h1>PARKWISE email verified</h1><p>You can now return to the application and sign in.</p>", media_type="text/html")


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> TokenResponse:
    client_key = request.client.host if request.client else "unknown"
    _check_login_rate_limit(client_key)
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Verify your email from the mailbox before signing in")
    return _token_response(user)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    return user


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: DbSession) -> TokenResponse:
    try:
        payload = decode_token(data.refresh_token, "refresh")
        user_id = int(payload["sub"])
    except (TokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token") from exc
    if db.scalar(select(RevokedToken.id).where(RevokedToken.jti == str(payload["jti"]))):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")
    user = db.get(User, user_id)
    if not user or not user.is_active or user.role.value != payload.get("role"):
        raise HTTPException(status_code=401, detail="User is inactive or token role is stale")
    _revoke(db, payload)
    response = _token_response(user)
    db.commit()
    return response


@router.post("/logout", response_model=MessageResponse)
def logout(
    data: LogoutRequest,
    user: CurrentUser,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> MessageResponse:
    try:
        _revoke(db, decode_token(token, "access"))
        if data.refresh_token:
            refresh_payload = decode_token(data.refresh_token, "refresh")
            if int(refresh_payload["sub"]) == user.id:
                _revoke(db, refresh_payload)
    except (TokenError, KeyError, TypeError, ValueError):
        pass
    db.commit()
    return MessageResponse(message="Logged out successfully")
