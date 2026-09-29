import base64

import pandas as pd
import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import current_role, get_client, show_api_error


if current_role() != "ADMIN":
    st.error("Administrator access is required.")
    st.stop()

client = get_client()
try:
    facilities = client.get("/api/facilities")
except APIError as exc:
    show_api_error(exc)
    st.stop()

active_facilities = {item["name"]: item for item in facilities if item["is_active"]}
if not active_facilities:
    st.info("Create an active facility first.")
    st.stop()
facility_name = st.selectbox("Facility", active_facilities)
facility = active_facilities[facility_name]
zones = client.get(f"/api/facilities/{facility['id']}/zones")

zone_tab, slot_tab = st.tabs(["Zones", "Slots"])
with zone_tab:
    st.dataframe(pd.DataFrame(zones), hide_index=True)
    with st.form("zone_form", border=True):
        zone_name = st.text_input("Zone name")
        vehicle_type = st.selectbox("Vehicle type", ["CAR", "MOTORCYCLE", "BICYCLE", "VAN", "EV", "ACCESSIBLE"])
        zone_capacity = st.number_input("Capacity", min_value=1, step=1)
        create_zone = st.form_submit_button("Create zone", type="primary")
    if create_zone:
        try:
            client.post(
                f"/api/facilities/{facility['id']}/zones",
                json={"name": zone_name, "vehicle_type": vehicle_type, "capacity": zone_capacity, "is_active": True},
            )
            st.success("Zone created.")
            st.rerun()
        except APIError as exc:
            show_api_error(exc)
    if zones:
        zone_admin_options = {item["name"]: item for item in zones}
        zone_admin_label = st.selectbox("Zone to manage", zone_admin_options, key="manage_zone")
        zone_admin = zone_admin_options[zone_admin_label]
        if st.button("Deactivate zone", icon=":material/block:"):
            try:
                client.delete(f"/api/zones/{zone_admin['id']}")
                st.success("Zone deactivated.")
                st.rerun()
            except APIError as exc:
                show_api_error(exc)

with slot_tab:
    if not zones:
        st.info("Create a zone first.")
    else:
        zone_options = {f"{item['name']} · {item['vehicle_type']}": item for item in zones}
        selected_zone_label = st.selectbox("Zone", zone_options)
        zone = zone_options[selected_zone_label]
        slots = client.get(f"/api/zones/{zone['id']}/slots")
        st.dataframe(pd.DataFrame(slots), hide_index=True)
        with st.form("slot_form", border=True):
            row_label = st.text_input("Row label")
            slot_code = st.text_input("Slot code")
            create_slot = st.form_submit_button("Create slot", type="primary")
        if create_slot:
            try:
                client.post(
                    f"/api/zones/{zone['id']}/slots",
                    json={"row_label": row_label or None, "slot_code": slot_code, "status": "AVAILABLE", "is_active": True},
                )
                st.success("Slot created.")
                st.rerun()
            except APIError as exc:
                show_api_error(exc)
        if slots:
            slot_options = {item["slot_code"]: item["id"] for item in slots}
            qr_slot = st.selectbox("Generate QR for slot", slot_options)
            if st.button("Generate slot QR", icon=":material/qr_code:"):
                try:
                    result = client.post(f"/api/slots/{slot_options[qr_slot]}/qr")
                    png = base64.b64decode(result["png_base64"])
                    st.image(png, caption=f"Slot {qr_slot}")
                    st.download_button("Download slot QR", png, file_name=f"slot-{qr_slot}.png", mime="image/png")
                except APIError as exc:
                    show_api_error(exc)
            with st.expander("Update slot status"):
                status_slot = st.selectbox("Slot", slot_options, key="status_slot")
                slot_status = st.selectbox("Status", ["AVAILABLE", "RESERVED", "OUT_OF_SERVICE"])
                if st.button("Save slot status", icon=":material/save:"):
                    try:
                        client.put(
                            f"/api/slots/{slot_options[status_slot]}",
                            json={"status": slot_status},
                        )
                        st.success("Slot status updated.")
                        st.rerun()
                    except APIError as exc:
                        show_api_error(exc)
