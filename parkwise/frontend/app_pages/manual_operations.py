import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import get_client, show_api_error


client = get_client()
entry_tab, exit_tab, recovery_tab, correction_tab = st.tabs(
    ["Manual entry", "Manual exit", "Recover ticket", "Correct slot"]
)

with entry_tab:
    with st.form("manual_entry", border=True):
        user_id = st.number_input("User ID", min_value=1, step=1)
        vehicle_id = st.number_input("Vehicle ID", min_value=1, step=1)
        facility_id = st.number_input("Facility ID", min_value=1, step=1)
        submit_entry = st.form_submit_button("Create manual entry", type="primary")
    if submit_entry:
        try:
            ticket = client.post(
                "/api/parking/entry",
                json={
                    "user_id": user_id,
                    "vehicle_id": vehicle_id,
                    "facility_id": facility_id,
                    "entry_method": "MANUAL",
                },
            )
            st.success(f"Created ticket {ticket['ticket_id']} for slot {ticket['slot_code']}.")
        except APIError as exc:
            show_api_error(exc)

with exit_tab:
    with st.form("manual_exit", border=True):
        ticket_id = st.text_input("Ticket ID")
        submit_exit = st.form_submit_button("Close session", type="primary")
    if submit_exit:
        try:
            result = client.post("/api/parking/manual-exit", json={"ticket_id": ticket_id})
            st.success(f"Exit recorded after {result['duration_minutes']} minutes.")
        except APIError as exc:
            show_api_error(exc)

with recovery_tab:
    registration = st.text_input("Vehicle registration number")
    if st.button("Recover active ticket", icon=":material/search:"):
        try:
            ticket = client.get("/api/parking/recover", params={"registration_number": registration})
            st.success(f"Recovered ticket: {ticket['ticket_id']} · slot {ticket['slot_code']}")
        except APIError as exc:
            show_api_error(exc)

with correction_tab:
    correction_ticket = st.text_input("Ticket ID", key="correction_ticket")
    new_slot_id = st.number_input("New slot ID", min_value=1, step=1)
    if st.button("Correct assignment", icon=":material/edit:"):
        try:
            ticket = client.put(
                f"/api/parking/session/{correction_ticket}/slot",
                json={"slot_id": new_slot_id},
            )
            st.success(f"Assignment updated to {ticket['zone_name']} / {ticket['slot_code']}.")
        except APIError as exc:
            show_api_error(exc)
