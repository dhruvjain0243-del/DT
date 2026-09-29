from __future__ import annotations

import streamlit as st

from frontend.components.auth import current_role, initialize_auth_state, is_authenticated, sign_out


st.set_page_config(page_title="PARKWISE", page_icon=":material/local_parking:", layout="wide")
initialize_auth_state()

if not is_authenticated():
    pages = {
        "Welcome": [
            st.Page("app_pages/login.py", title="Login", icon=":material/login:"),
            st.Page("app_pages/register.py", title="Register", icon=":material/person_add:"),
        ]
    }
else:
    role = current_role()
    pages = {
        "Parking": [
            st.Page("app_pages/student_dashboard.py", title="Dashboard", icon=":material/home:"),
            st.Page("app_pages/ticket.py", title="My parking ticket", icon=":material/confirmation_number:"),
            st.Page("app_pages/find_vehicle.py", title="Find my vehicle", icon=":material/location_on:"),
            st.Page("app_pages/availability.py", title="Live availability", icon=":material/local_parking:"),
            st.Page("app_pages/history.py", title="Parking history", icon=":material/history:"),
            st.Page("app_pages/feedback.py", title="Feedback", icon=":material/feedback:"),
        ]
    }
    if role in {"ADMIN", "ATTENDANT"}:
        pages["Operations"] = [
            st.Page("app_pages/active_sessions.py", title="Active sessions", icon=":material/list_alt:"),
            st.Page("app_pages/manual_operations.py", title="Manual entry and exit", icon=":material/sync_alt:"),
        ]
    if role == "ADMIN":
        pages["Administration"] = [
            st.Page("app_pages/admin_overview.py", title="Admin overview", icon=":material/dashboard:"),
            st.Page("app_pages/facilities.py", title="Facility management", icon=":material/business:"),
            st.Page("app_pages/zones_slots.py", title="Zones and slots", icon=":material/grid_view:"),
            st.Page("app_pages/reports.py", title="Reports", icon=":material/description:"),
            st.Page("app_pages/predictions.py", title="Prediction analytics", icon=":material/analytics:"),
        ]

page = st.navigation(pages, position="sidebar")

if is_authenticated():
    user = st.session_state.user
    with st.sidebar:
        st.caption(f"Signed in as **{user['full_name']}**")
        st.badge(user["role"], color="green")
        if st.button("Log out", icon=":material/logout:", width="stretch"):
            sign_out()
            st.rerun()

st.title(page.title, icon=page.icon)
page.run()
