import pandas as pd
import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import get_client, show_api_error


client = get_client()
default_ticket = ""
try:
    default_ticket = client.get("/api/parking/my-active-session")["ticket_id"]
except APIError:
    pass

ticket_id = st.text_input("Ticket ID", value=default_ticket, placeholder="PW-…")
if st.button("Find vehicle", icon=":material/search:", type="primary"):
    try:
        location = client.get(f"/api/parking/find-my-vehicle/{ticket_id.strip()}")
        if location["status"] != "ACTIVE":
            st.warning("This parking session is completed; the location is historical.")
        st.table(
            {
                "Facility": location["facility_name"],
                "Address": location["facility_address"],
                "Zone": location["zone_name"],
                "Row": location.get("row_label") or "—",
                "Slot": location["slot_code"],
                "Entry time": location["entry_time"],
            },
            border="horizontal",
            width="content",
        )
        slots = client.get(f"/api/zones/{location['zone_id']}/slots")
        diagram = pd.DataFrame(
            {
                "Row": [item.get("row_label") or "—" for item in slots],
                "Slot": [item["slot_code"] for item in slots],
                "Status": [item["status"] for item in slots],
                "Your vehicle": [item["id"] == location["slot_id"] for item in slots],
            }
        )
        st.subheader("Parking-area diagram")
        st.dataframe(diagram, hide_index=True)
        if location.get("latitude") is not None and location.get("longitude") is not None:
            st.map(pd.DataFrame([{"lat": location["latitude"], "lon": location["longitude"]}]))
    except APIError as exc:
        show_api_error(exc)

with st.expander("Confirm a slot QR"):
    slot_ticket = st.text_input("Ticket ID for confirmation", value=default_ticket, key="confirm_ticket")
    slot_token = st.text_area("Scanned slot QR token")
    if st.button("Confirm assigned slot", icon=":material/qr_code_scanner:"):
        try:
            result = client.post(
                "/api/parking/confirm-slot",
                json={"ticket_id": slot_ticket, "slot_qr_token": slot_token},
            )
            st.success(result["message"])
        except APIError as exc:
            show_api_error(exc)
