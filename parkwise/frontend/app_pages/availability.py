import pandas as pd
import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import get_client, show_api_error
from frontend.components.display import availability_cards


st.caption("Calculated from active parking sessions; refreshed every 30 seconds.")


@st.fragment(run_every="30s")
def live_availability() -> None:
    try:
        items = get_client().get("/api/availability")
        availability_cards(items)
        if items:
            frame = pd.DataFrame(items)
            st.bar_chart(frame, x="facility_name", y=["occupied_spaces", "available_spaces"])
            st.dataframe(
                frame[["facility_name", "total_capacity", "occupied_spaces", "available_spaces", "occupancy_percentage", "last_update_time"]],
                hide_index=True,
            )
    except APIError as exc:
        show_api_error(exc)


live_availability()
