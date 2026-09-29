import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import get_client, show_api_error


with st.form("feedback_form", border=True):
    category = st.selectbox("Category", ["AVAILABILITY", "SAFETY", "CLEANLINESS", "ACCESSIBILITY", "OTHER"])
    description = st.text_area("Description", max_chars=2000)
    reported = st.number_input("Observed available spaces (optional)", min_value=0, value=None, step=1)
    submitted = st.form_submit_button("Submit feedback", icon=":material/send:", type="primary")

if submitted:
    try:
        get_client().post(
            "/api/feedback",
            json={
                "category": category,
                "description": description,
                "reported_available_spaces": reported,
            },
        )
        st.success("Thank you. Your feedback was recorded.")
    except APIError as exc:
        show_api_error(exc)
