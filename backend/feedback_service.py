"""
Feedback service for PARKWISE.
Persists ground-truth parking observations to CSV for ongoing system evaluation.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd

from backend.config import FEEDBACK_PATH, FEEDBACK_STATUS_OPTIONS

FEEDBACK_COLUMNS = ["feedback_timestamp", "parking_id", "actual_status", "comment"]


def ensure_feedback_storage(filepath: Optional[Path] = None) -> Path:
    """Ensure the feedback storage directory and CSV file exist with header."""
    target_path = Path(filepath) if filepath else FEEDBACK_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not target_path.exists():
        empty_df = pd.DataFrame(columns=FEEDBACK_COLUMNS)
        empty_df.to_csv(target_path, index=False)
    return target_path


def save_feedback(
    parking_id: str,
    actual_status: str,
    comment: str = "",
    filepath: Optional[Path] = None,
) -> bool:
    """
    Append user feedback to the storage CSV.
    Validates input parameters before saving.
    """
    if not parking_id:
        raise ValueError("Parking ID is required.")

    if actual_status not in FEEDBACK_STATUS_OPTIONS:
        raise ValueError(
            f"Invalid status '{actual_status}'. Expected one of: {FEEDBACK_STATUS_OPTIONS}"
        )

    target_path = ensure_feedback_storage(filepath)

    new_row = {
        "feedback_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "parking_id": str(parking_id).strip(),
        "actual_status": str(actual_status).strip(),
        "comment": str(comment).strip() if comment else "",
    }

    df_new = pd.DataFrame([new_row])
    df_new.to_csv(target_path, mode="a", header=False, index=False)
    return True


def load_feedback(filepath: Optional[Path] = None) -> pd.DataFrame:
    """Load all stored feedback entries into a DataFrame."""
    target_path = ensure_feedback_storage(filepath)
    try:
        df = pd.read_csv(target_path)
        return df
    except Exception:
        return pd.DataFrame(columns=FEEDBACK_COLUMNS)
