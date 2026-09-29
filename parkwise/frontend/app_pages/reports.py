import pandas as pd
import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import current_role, get_client, show_api_error


if current_role() != "ADMIN":
    st.error("Administrator access is required.")
    st.stop()

client = get_client()
days = st.slider("Reporting window (days)", 7, 365, 30)
try:
    daily = client.get("/api/reports/daily", params={"days": days})
    peaks = client.get("/api/reports/peak-hours", params={"days": days})
    history = client.get("/api/reports/sessions", params={"days": days})
    daily_frame = pd.DataFrame(daily)
    peak_frame = pd.DataFrame(peaks)
    if not daily_frame.empty:
        st.line_chart(daily_frame, x="period", y=["entries", "exits"])
        st.dataframe(daily_frame, hide_index=True)
    st.subheader("Peak entry hours")
    st.bar_chart(peak_frame, x="hour", y="entries")
    st.subheader("Historical parking sessions")
    st.dataframe(pd.DataFrame(history), hide_index=True)
    csv_data = client.get("/api/reports/export-csv", params={"days": days})
    st.download_button("Export CSV", csv_data, file_name="parkwise-report.csv", mime="text/csv", icon=":material/download:")
except APIError as exc:
    show_api_error(exc)
