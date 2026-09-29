import pandas as pd
import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import current_role, get_client, show_api_error
from frontend.components.display import availability_cards


if current_role() != "ADMIN":
    st.error("Administrator access is required.")
    st.stop()

client = get_client()
try:
    availability = client.get("/api/availability")
    active = client.get("/api/parking/active")
    users = client.get("/api/users")
    audits = client.get("/api/audit-logs", params={"limit": 50})
    availability_cards(availability)
    with st.container(horizontal=True):
        st.metric("Active sessions", len(active), border=True)
        st.metric("Registered users", len(users), border=True)
        st.metric("Facilities", len(availability), border=True)
    st.subheader("Recent administrative activity")
    st.dataframe(pd.DataFrame(audits), hide_index=True)
    with st.expander("Manage users and roles"):
        user_options = {f"{item['full_name']} · {item['email']} (#{item['id']})": item for item in users}
        selected_label = st.selectbox("User", user_options)
        selected_user = user_options[selected_label]
        role = st.selectbox(
            "Role",
            ["ADMIN", "ATTENDANT", "STUDENT", "STAFF", "VISITOR"],
            index=["ADMIN", "ATTENDANT", "STUDENT", "STAFF", "VISITOR"].index(selected_user["role"]),
        )
        active_state = st.checkbox("Account active", value=selected_user["is_active"])
        if st.button("Update user", icon=":material/save:"):
            client.put(
                f"/api/users/{selected_user['id']}",
                json={"role": role, "is_active": active_state},
            )
            st.success("User updated. Existing tokens with stale roles will be rejected.")
            st.rerun()
except APIError as exc:
    show_api_error(exc)
