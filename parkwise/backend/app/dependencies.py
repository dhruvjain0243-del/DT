from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.database import get_db
from .core.security import TokenError, decode_token
from .models import RevokedToken, User, UserRole


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
DbSession = Annotated[Session, Depends(get_db)]


def get_token_payload(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> dict[str, Any]:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token, "access")
        user_id = int(payload["sub"])
        jti = str(payload["jti"])
    except (TokenError, KeyError, TypeError, ValueError) as exc:
        raise credentials_error from exc
    if db.scalar(select(RevokedToken.id).where(RevokedToken.jti == jti)):
        raise credentials_error
    payload["user_id"] = user_id
    return payload


def get_current_user(
    payload: Annotated[dict[str, Any], Depends(get_token_payload)], db: DbSession
) -> User:
    user = db.get(User, payload["user_id"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive or no longer exists")
    if user.role.value != payload.get("role"):
        raise HTTPException(status_code=401, detail="Token role is stale; sign in again")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[CurrentUser], User]:
    allowed = set(roles)

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency
