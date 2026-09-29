"""
Data service for PARKWISE.
Handles dataset loading, timestamp conversion, date-range discovery,
and nearest-timestamp filtering.
"""

from pathlib import Path
from typing import Optional, Tuple
import pandas as pd

from backend.config import get_dataset_path


def load_dataset(filepath: Optional[Path] = None) -> pd.DataFrame:
    """
    Load the CSV dataset from disk. Raises FileNotFoundError if missing.
    """
    target_path = Path(filepath) if filepath else get_dataset_path()
    if not target_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at '{target_path}'. "
            f"Please ensure the CSV file is located in the data/ or project root folder."
        )
    return pd.read_csv(target_path)


def prepare_dataset(filepath: Optional[Path] = None) -> pd.DataFrame:
    """
    Load, parse timestamps, and sort dataset by parking_id and timestamp.
    """
    df = load_dataset(filepath)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(by=["parking_id", "timestamp"]).reset_index(drop=True)
    return df


def get_available_date_range(df: pd.DataFrame) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """
    Return (min_timestamp, max_timestamp) available in the dataset.
    """
    if "timestamp" not in df.columns:
        raise ValueError("DataFrame does not contain 'timestamp' column.")
    ts_series = pd.to_datetime(df["timestamp"])
    return ts_series.min(), ts_series.max()


def get_nearest_timestamp(df: pd.DataFrame, target_dt: pd.Timestamp) -> pd.Timestamp:
    """
    Find the closest timestamp present in the dataset to the requested target_dt.
    """
    ts_series = pd.to_datetime(df["timestamp"])
    time_diffs = (ts_series - target_dt).abs()
    nearest_idx = time_diffs.idxmin()
    return pd.to_datetime(df.loc[nearest_idx, "timestamp"])


def get_records_at_timestamp(
    df: pd.DataFrame, target_dt: pd.Timestamp
) -> Tuple[pd.DataFrame, pd.Timestamp]:
    """
    Extract parking records for the given timestamp (or nearest available).
    Returns (records_df, resolved_timestamp).
    """
    df_prepared = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_prepared["timestamp"]):
        df_prepared["timestamp"] = pd.to_datetime(df_prepared["timestamp"])

    exact_records = df_prepared[df_prepared["timestamp"] == target_dt]
    if not exact_records.empty:
        return exact_records.copy(), target_dt

    resolved_dt = get_nearest_timestamp(df_prepared, target_dt)
    nearest_records = df_prepared[df_prepared["timestamp"] == resolved_dt]
    return nearest_records.copy(), resolved_dt


def get_latest_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get the most recent record for each parking location.
    """
    df_prepared = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_prepared["timestamp"]):
        df_prepared["timestamp"] = pd.to_datetime(df_prepared["timestamp"])

    latest_ts = df_prepared["timestamp"].max()
    return df_prepared[df_prepared["timestamp"] == latest_ts].copy()
