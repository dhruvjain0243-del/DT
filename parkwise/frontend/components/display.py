from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st


def availability_cards(items: list[dict]) -> None:
    total = sum(item["total_capacity"] for item in items)
    occupied = sum(item["occupied_spaces"] for item in items)
    available = sum(item["available_spaces"] for item in items)
    percentage = round((occupied / total * 100) if total else 0, 1)
    with st.container(horizontal=True):
        st.metric("Total capacity", total, border=True)
        st.metric("Occupied", occupied, border=True)
        st.metric("Available", available, border=True)
        st.metric("Occupancy", f"{percentage}%", border=True)


def session_table(items: list[dict]) -> None:
    if not items:
        st.info("No parking sessions found.")
        return
    frame = pd.DataFrame(items)
    visible = [
        column
        for column in ("ticket_id", "vehicle_id", "facility_id", "zone_id", "slot_id", "entry_time", "exit_time", "status")
        if column in frame.columns
    ]
    st.dataframe(frame[visible], hide_index=True)


def ticket_summary(ticket: dict) -> None:
    st.table(
        {
            "Ticket": ticket["ticket_id"],
            "Vehicle": ticket["registration_number"],
            "Facility": ticket["facility_name"],
            "Zone": ticket["zone_name"],
            "Row": ticket.get("row_label") or "—",
            "Slot": ticket["slot_code"],
            "Entry time": ticket["entry_time"],
            "Status": ticket["status"],
        },
        border="horizontal",
        width="content",
    )
