from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .config import get_settings


password_hasher = PasswordHasher()


class TokenError(ValueError):
    """Raised when a JWT cannot be safely accepted."""


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _create_token(
    *,
    subject: int,
    role: str,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "type": token_type,
        "jti": uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_token_pair(user_id: int, role: str) -> TokenPair:
    settings = get_settings()
    return TokenPair(
        access_token=_create_token(
            subject=user_id,
            role=role,
            token_type="access",
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        ),
        refresh_token=_create_token(
            subject=user_id,
            role=role,
            token_type="refresh",
            expires_delta=timedelta(days=settings.refresh_token_expire_days),
        ),
        expires_in=settings.access_token_expire_minutes * 60,
    )


def create_qr_token(reference: str, kind: Literal["ticket_qr", "slot_qr"]) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "ref": reference,
        "type": kind,
        "jti": uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(days=settings.qr_token_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "jti", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid token") from exc
    if expected_type and payload.get("type") != expected_type:
        raise TokenError("Incorrect token type")
    return payload
