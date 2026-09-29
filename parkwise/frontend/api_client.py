from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import requests


class APIError(RuntimeError):
    def __init__(self, status_code: int, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.details = details


def api_base_url() -> str:
    try:
        import streamlit as st

        return str(st.secrets.get("API_BASE_URL", os.getenv("API_BASE_URL", "http://localhost:8000"))).rstrip("/")
    except Exception:
        return os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


class APIClient:
    """Thin authenticated client; the backend remains the authorization boundary."""

    def __init__(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
        on_token_refresh: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.base_url = api_base_url()
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.on_token_refresh = on_token_refresh
        self.session = requests.Session()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    @staticmethod
    def _raise(response: requests.Response) -> None:
        try:
            body = response.json()
        except ValueError:
            body = {}
        error = body.get("error", {}) if isinstance(body, dict) else {}
        message = error.get("message") or body.get("detail") or f"Request failed ({response.status_code})"
        raise APIError(response.status_code, str(message), error.get("details"))

    def _refresh(self) -> bool:
        if not self.refresh_token:
            return False
        response = self.session.post(
            f"{self.base_url}/api/auth/refresh",
            json={"refresh_token": self.refresh_token},
            timeout=15,
        )
        if not response.ok:
            return False
        tokens = response.json()
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens["refresh_token"]
        if self.on_token_refresh:
            self.on_token_refresh(tokens)
        return True

    def request(self, method: str, path: str, *, retry: bool = True, **kwargs) -> Any:
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            headers={**self._headers(), **kwargs.pop("headers", {})},
            timeout=kwargs.pop("timeout", 20),
            **kwargs,
        )
        if response.status_code == 401 and retry and self._refresh():
            return self.request(method, path, retry=False, **kwargs)
        if not response.ok:
            self._raise(response)
        if response.status_code == 204:
            return None
        content_type = response.headers.get("content-type", "")
        return response.json() if "application/json" in content_type else response.content

    def get(self, path: str, **kwargs) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Any:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Any:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Any:
        return self.request("DELETE", path, **kwargs)

    def login(self, email: str, password: str) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/api/auth/login",
            data={"username": email, "password": password},
            timeout=15,
        )
        if not response.ok:
            self._raise(response)
        return response.json()
