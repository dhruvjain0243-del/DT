import pandas as pd
import streamlit as st

from frontend.api_client import APIError
from frontend.components.auth import current_role, get_client, show_api_error


if current_role() != "ADMIN":
    st.error("Administrator access is required.")
    st.stop()

client = get_client()
st.warning("Predictions use a model trained on simulated data and are not a real-time availability guarantee.")
try:
    metrics = client.get("/api/predictions/metrics")
    with st.container(horizontal=True):
        st.metric("MAE", metrics.get("model_mae", "—"), border=True)
        st.metric("RMSE", metrics.get("model_rmse", "—"), border=True)
        st.metric("R²", metrics.get("model_r2", "—"), border=True)
        st.metric("Baseline MAE", metrics.get("baseline_mae", "—"), border=True)
    if st.button("Run 30-minute prediction", icon=":material/play_arrow:", type="primary"):
        with st.spinner("Running trusted model inference…"):
            result = client.post("/api/predictions/run")
            if not result["model_available"]:
                st.warning("The trained model was unavailable; capacity-based fallback values were stored.")
            st.success(f"Stored {len(result['predictions'])} predictions.")
    latest = client.get("/api/predictions/latest")
    if latest:
        frame = pd.DataFrame(latest)
        st.bar_chart(frame, x="facility_id", y="predicted_available_spaces")
        st.dataframe(frame, hide_index=True)
except APIError as exc:
    show_api_error(exc)
