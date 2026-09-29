import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import get_client, show_api_error
from frontend.components.display import availability_cards


client = get_client()
st.caption("Register a vehicle, review capacity, and manage parking entry and exit.")

try:
    availability = client.get("/api/availability")
    availability_cards(availability)
except APIError as exc:
    show_api_error(exc)
    availability = []

last_exit = st.session_state.pop("last_exit_result", None)
if last_exit:
    with st.container(border=True):
        st.success(last_exit["message"])
        st.table(
            {
                "Ticket": last_exit["ticket_id"],
                "Vehicle": f"{last_exit['registration_number']} · {last_exit['vehicle_type']}",
                "Slot": last_exit["slot_code"],
                "Entry time": last_exit["entry_time"],
                "Exit time": last_exit["exit_time"],
                "Duration": f"{last_exit['duration_minutes']} minutes",
            },
            border="horizontal",
            width="content",
        )

register_tab, entry_tab, exit_tab = st.tabs(["My vehicles", "Enter parking", "Exit parking"])
with register_tab:
    try:
        vehicles = client.get("/api/vehicles/mine")
    except APIError as exc:
        show_api_error(exc)
        vehicles = []
    if vehicles:
        st.dataframe(vehicles, hide_index=True)
    else:
        st.info("Register your first vehicle to begin.")
    with st.form("vehicle_form", border=True):
        registration = st.text_input("Registration number", placeholder="KA01AB1234")
        vehicle_type = st.selectbox("Vehicle type", ["CAR", "MOTORCYCLE", "BICYCLE", "VAN", "EV", "ACCESSIBLE"])
        add_vehicle = st.form_submit_button("Register vehicle", icon=":material/add:")
    if add_vehicle:
        try:
            client.post("/api/vehicles", json={"registration_number": registration, "vehicle_type": vehicle_type})
            st.success("Vehicle registered.")
            st.rerun()
        except APIError as exc:
            show_api_error(exc)

with entry_tab:
    try:
        vehicles = client.get("/api/vehicles/mine")
        facilities = client.get("/api/facilities")
    except APIError as exc:
        show_api_error(exc)
        vehicles, facilities = [], []
    if not vehicles or not facilities:
        st.info("You need a registered vehicle and an active facility before entry.")
    else:
        vehicle_options = {f"{item['registration_number']} · {item['vehicle_type']}": item["id"] for item in vehicles}
        facility_options = {item["name"]: item["id"] for item in facilities if item["is_active"]}
        with st.form("entry_form", border=True):
            selected_vehicle = st.selectbox("Vehicle", vehicle_options)
            selected_facility = st.selectbox("Facility", facility_options)
            slot_qr_token = st.text_input(
                "Scanned slot QR token",
                placeholder="Paste the token read by your QR scanner",
                help="Scan the QR label on your assigned parking slot, then paste its token here.",
            )
            enter = st.form_submit_button("Generate entry ticket", icon=":material/confirmation_number:", type="primary")
        if enter:
            if not slot_qr_token.strip():
                st.error("Scan a parking slot QR code before starting entry.")
                st.stop()
            try:
                ticket = client.post(
                    "/api/parking/entry",
                    json={
                        "vehicle_id": vehicle_options[selected_vehicle],
                        "facility_id": facility_options[selected_facility],
                        "entry_method": "QR",
                        "slot_qr_token": slot_qr_token.strip(),
                    },
                )
                st.session_state.last_ticket = ticket
                st.success(f"Entry recorded. Assigned slot: {ticket['slot_code']}")
            except APIError as exc:
                show_api_error(exc)

with exit_tab:
    st.caption(
        "Enter the ticket ID shown on the parking ticket and paste the decoded token from its QR scan. "
        "ADMIN and ATTENDANT users can also assist another driver."
    )
    with st.form("qr_exit_form", border=True):
        ticket_id = st.text_input("Ticket ID", placeholder="PW-…", key="exit_ticket_id")
        ticket_qr_token = st.text_input(
            "Scanned ticket QR token",
            placeholder="Paste the token read by your QR scanner",
            key="exit_qr_token",
        )
        submit_exit = st.form_submit_button(
            "Confirm QR exit", icon=":material/logout:", type="primary", key="qr_exit_submit"
        )
    if submit_exit:
        if not ticket_id.strip() or not ticket_qr_token.strip():
            st.error("Enter the ticket ID and scan its ticket QR code before confirming exit.")
        else:
            try:
                result = client.post(
                    "/api/parking/exit",
                    json={
                        "ticket_id": ticket_id.strip(),
                        "qr_token": ticket_qr_token.strip(),
                    },
                )
                st.session_state.last_exit_result = result
                st.rerun()
            except APIError as exc:
                show_api_error(exc)
