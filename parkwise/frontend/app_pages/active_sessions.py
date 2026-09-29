import pandas as pd
import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import get_client, show_api_error


try:
    sessions = get_client().get("/api/parking/active")
except APIError as exc:
    show_api_error(exc)
    st.stop()

query = st.text_input("Search tickets, vehicle IDs, or user IDs", type="search")
frame = pd.DataFrame(sessions)
if not frame.empty and query:
    mask = frame.astype(str).apply(lambda column: column.str.contains(query, case=False, na=False)).any(axis=1)
    frame = frame[mask]
st.metric("Active sessions", len(frame), border=True)
st.dataframe(frame, hide_index=True)
