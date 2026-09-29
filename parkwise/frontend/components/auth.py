from __future__ import annotations

import streamlit as st

from frontend.api_client import APIClient, APIError


AUTH_KEYS = ("access_token", "refresh_token", "user")


def initialize_auth_state() -> None:
    for key in AUTH_KEYS:
        st.session_state.setdefault(key, None)


def _save_refreshed_tokens(tokens: dict) -> None:
    st.session_state.access_token = tokens["access_token"]
    st.session_state.refresh_token = tokens["refresh_token"]
    st.session_state.user = tokens.get("user", st.session_state.user)


def get_client() -> APIClient:
    return APIClient(
        access_token=st.session_state.get("access_token"),
        refresh_token=st.session_state.get("refresh_token"),
        on_token_refresh=_save_refreshed_tokens,
    )


def sign_in(tokens: dict) -> None:
    _save_refreshed_tokens(tokens)


def sign_out() -> None:
    client = get_client()
    try:
        if st.session_state.get("access_token"):
            client.post(
                "/api/auth/logout",
                json={"refresh_token": st.session_state.get("refresh_token")},
            )
    except APIError:
        pass
    for key in AUTH_KEYS:
        st.session_state[key] = None


def is_authenticated() -> bool:
    return bool(st.session_state.get("access_token") and st.session_state.get("user"))


def current_role() -> str:
    user = st.session_state.get("user") or {}
    return str(user.get("role", ""))


def show_api_error(exc: APIError) -> None:
    st.error(exc.message)
    if exc.details:
        with st.expander("Validation details"):
            st.json(exc.details)
