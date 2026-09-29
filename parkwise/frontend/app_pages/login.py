import streamlit as st

from frontend.api_client import APIClient, APIError
from frontend.components.auth import show_api_error, sign_in


st.caption("Use your PARKWISE account to access parking services.")
with st.form("login_form", border=True):
    email = st.text_input("Email", autocomplete="email")
    password = st.text_input("Password", type="password", autocomplete="current-password")
    submitted = st.form_submit_button("Log in", icon=":material/login:", type="primary")

if submitted:
    with st.spinner("Signing in…"):
        try:
            tokens = APIClient().login(email.strip(), password)
            sign_in(tokens)
            st.success("Welcome back.")
            st.rerun()
        except APIError as exc:
            show_api_error(exc)
