import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import get_client, show_api_error
from frontend.components.display import session_table


try:
    history = get_client().get("/api/parking/my-history")
    session_table(history)
except APIError as exc:
    show_api_error(exc)
