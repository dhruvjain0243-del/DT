import base64

import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import get_client, show_api_error
from frontend.components.display import ticket_summary


client = get_client()
try:
    ticket = client.get("/api/parking/my-active-session")
except APIError as exc:
    if exc.status_code == 404:
        st.info("You do not have an active parking ticket.")
        st.stop()
    show_api_error(exc)
    st.stop()

ticket_summary(ticket)
png = base64.b64decode(ticket["qr_png_base64"])
st.image(png, caption="Secure ticket QR")
st.download_button(
    "Download ticket QR",
    data=png,
    file_name=f"ticket-{ticket['ticket_id']}.png",
    mime="image/png",
    icon=":material/download:",
)

with st.container(border=True):
    st.subheader("Exit parking")
    st.caption("The backend validates the signed ticket QR before closing the session.")
    if st.button("Confirm QR exit", icon=":material/logout:", type="primary"):
        try:
            result = client.post(
                "/api/parking/exit",
                json={"ticket_id": ticket["ticket_id"], "qr_token": ticket["qr_token"]},
            )
            st.success(f"Exit confirmed. Duration: {result['duration_minutes']} minutes.")
            st.rerun()
        except APIError as exc:
            show_api_error(exc)
