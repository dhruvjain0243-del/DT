from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select

from ..core.security import TokenError, create_token_pair, decode_token, hash_password, verify_password
from ..dependencies import CurrentUser, DbSession, oauth2_scheme
from ..models import RevokedToken, User
from ..schemas.auth import LogoutRequest, RefreshRequest, TokenResponse, UserRead, UserRegister
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
    duplicate = db.scalar(
        select(User.id).where(
            or_(User.email == email, User.college_id == data.college_id)
            if data.college_id
            else User.email == email
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Email or college ID already exists")
    user = User(
        full_name=data.full_name.strip(),
        email=email,
        college_id=data.college_id.strip() if data.college_id else None,
        phone=data.phone.strip() if data.phone else None,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
