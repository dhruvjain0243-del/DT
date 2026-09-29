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
    facilities = []

st.dataframe(pd.DataFrame(facilities), hide_index=True)
with st.form("facility_form", border=True):
    name = st.text_input("Facility name")
    address = st.text_area("Address")
    capacity = st.number_input("Total capacity", min_value=1, step=1)
    latitude = st.number_input("Latitude", value=None, min_value=-90.0, max_value=90.0)
    longitude = st.number_input("Longitude", value=None, min_value=-180.0, max_value=180.0)
    distance = st.number_input("Distance (km)", min_value=0.0, step=0.1)
    price = st.number_input("Price per hour", min_value=0.0, step=1.0)
    create = st.form_submit_button("Create facility", icon=":material/add:", type="primary")
if create:
    try:
        client.post(
            "/api/facilities",
            json={
                "name": name,
                "address": address,
                "total_capacity": capacity,
                "latitude": latitude,
                "longitude": longitude,
                "distance_km": distance,
                "price_per_hour": price,
                "is_active": True,
            },
        )
        st.success("Facility created.")
        st.rerun()
    except APIError as exc:
        show_api_error(exc)

if facilities:
    with st.expander("Update facility"):
        update_options = {f"{item['name']} (#{item['id']})": item for item in facilities}
        update_label = st.selectbox("Facility", update_options, key="update_facility")
        update_item = update_options[update_label]
        update_name = st.text_input("Name", value=update_item["name"], key="update_name")
        update_address = st.text_area("Address", value=update_item["address"], key="update_address")
        update_capacity = st.number_input("Capacity", min_value=1, value=update_item["total_capacity"], step=1, key="update_capacity")
        if st.button("Save facility", icon=":material/save:"):
            try:
                client.put(
                    f"/api/facilities/{update_item['id']}",
                    json={"name": update_name, "address": update_address, "total_capacity": update_capacity},
                )
                st.success("Facility updated.")
                st.rerun()
            except APIError as exc:
                show_api_error(exc)
    deactivate_options = {f"{item['name']} (#{item['id']})": item["id"] for item in facilities if item["is_active"]}
    if deactivate_options:
        selected = st.selectbox("Facility to deactivate", deactivate_options)
        if st.button("Deactivate facility", icon=":material/block:"):
            try:
                client.delete(f"/api/facilities/{deactivate_options[selected]}")
                st.success("Facility deactivated.")
                st.rerun()
            except APIError as exc:
                show_api_error(exc)
