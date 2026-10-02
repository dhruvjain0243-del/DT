import pandas as pd
import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import get_client, show_api_error
from frontend.components.display import availability_cards
from frontend.theme import section_label


client = get_client()
section_label("Parking intelligence / live network")
st.markdown('<div class="pw-hero">Find your next spot <span>before you arrive.</span></div>', unsafe_allow_html=True)
st.markdown('<div class="pw-subtitle">PARKWISE combines occupancy, facility data, and availability prediction to help every arrival start with a confident decision.</div>', unsafe_allow_html=True)
st.markdown('<div class="pw-demo">DEMO DATA ACTIVE &nbsp; Predictions are estimates from simulated training data and are not guaranteed real-time availability.</div>', unsafe_allow_html=True)
st.space("medium")

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

try:
    facilities = client.get("/api/facilities")
except APIError:
    facilities = []

if availability:
    st.subheader("Network snapshot")
    frame = pd.DataFrame(availability)
    total = int(frame["total_capacity"].sum())
    occupied = int(frame["occupied_spaces"].sum())
    available = int(frame["available_spaces"].sum())
    with st.container(horizontal=True):
        st.metric("Monitored places", len(frame), border=True)
        st.metric("Current occupancy", f"{round(occupied / total * 100, 1) if total else 0}%", border=True)
        st.metric("Available slots", available, border=True)
        st.metric("System health", "Connected", border=True)

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        with st.container(border=True):
            section_label("Live availability overview")
            st.bar_chart(frame, x="facility_name", y=["occupied_spaces", "available_spaces"], width="stretch")
    with right:
        with st.container(border=True):
            section_label("Top places right now", "#c084fc")
            for item in sorted(availability, key=lambda value: value["available_spaces"], reverse=True)[:3]:
                pct = item["occupancy_percentage"]
                st.markdown(f"**{item['facility_name']}**  \\  <span class='pw-muted'>{item['available_spaces']} available · {pct:.1f}% occupied</span>", unsafe_allow_html=True)
                st.progress(min(1.0, pct / 100), text=f"{pct:.1f}% occupied")

    mapped = pd.DataFrame([item for item in facilities if item.get("latitude") is not None and item.get("longitude") is not None])
    if not mapped.empty:
        st.subheader("Parking-place network")
        st.map(mapped.rename(columns={"latitude": "lat", "longitude": "lon"})[["lat", "lon"]], width="stretch")
    else:
        st.info("Map preview is unavailable because the API did not return coordinates.")

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
