import streamlit as st

from frontend.api_client import APIClient, APIError
from frontend.components.auth import show_api_error


st.caption("Create a student, staff, or visitor account. Administrative roles are assigned by an administrator.")
with st.form("register_form", border=True):
    full_name = st.text_input("Full name")
    email = st.text_input("Email", autocomplete="email")
    college_id = st.text_input("College or employee ID (optional)")
    phone = st.text_input("Phone (optional)")
    role = st.segmented_control("Account type", ["STUDENT", "STAFF", "VISITOR"], default="STUDENT")
    password = st.text_input("Password", type="password", help="At least 12 characters with upper/lowercase, number, and symbol")
    submitted = st.form_submit_button("Create account", icon=":material/person_add:", type="primary")

if submitted:
    payload = {
        "full_name": full_name,
        "email": email,
        "college_id": college_id or None,
        "phone": phone or None,
        "password": password,
        "role": role,
    }
    try:
        APIClient().post("/api/auth/register", json=payload)
        st.success("Account created. Open the Login page to continue.")
    except APIError as exc:
        show_api_error(exc)
