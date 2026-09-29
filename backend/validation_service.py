"""
Validation service for PARKWISE dataset.
Validates file existence, schema integrity, value ranges, and domain logic.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from backend.config import (
    EXPECTED_COLUMNS,
    EXPECTED_PARKING_LOCATIONS,
    get_dataset_path,
)


def validate_required_columns(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Check if all required columns are present in the DataFrame."""
    missing = [col for col in EXPECTED_COLUMNS if col not in df.columns]
    return len(missing) == 0, missing


def validate_derived_columns(df: pd.DataFrame) -> Dict[str, int]:
    """
    Validate mathematical relationships and domain constraints:
    - available_spaces == total_spaces - occupied_spaces
    - occupancy_rate ~= occupied_spaces / total_spaces
    - occupied_spaces within [0, total_spaces]
    """
    errors = {
        "available_space_errors": 0,
        "occupancy_rate_errors": 0,
        "invalid_occupancy_rows": 0,
    }

    # available_spaces == total_spaces - occupied_spaces
    calc_available = df["total_spaces"] - df["occupied_spaces"]
    avail_mismatch = (df["available_spaces"] != calc_available).sum()
    errors["available_space_errors"] = int(avail_mismatch)

    # occupancy_rate ~= occupied_spaces / total_spaces (rounded in dataset to 4 decimals)
    expected_rate = df["occupied_spaces"] / df["total_spaces"]
    rate_mismatch = ((df["occupancy_rate"] - expected_rate).abs() > 0.005).sum()
    errors["occupancy_rate_errors"] = int(rate_mismatch)

    # occupied spaces not negative and not exceeding total_spaces
    invalid_occ = (
        (df["occupied_spaces"] < 0) | (df["occupied_spaces"] > df["total_spaces"])
    ).sum()
    errors["invalid_occupancy_rows"] = int(invalid_occ)

    return errors


def validate_dataset(filepath: Optional[Path] = None) -> Dict[str, Any]:
    """
    Perform complete 17-point validation on the parking dataset.
    Returns a structured dictionary with validation metrics and status.
    """
    target_path = Path(filepath) if filepath else get_dataset_path()

    result: Dict[str, Any] = {
        "valid": False,
        "file_exists": False,
        "filepath": str(target_path),
        "row_count": 0,
        "missing_values": 0,
        "duplicate_rows": 0,
        "duplicate_keys": 0,
        "invalid_occupancy_rows": 0,
        "available_space_errors": 0,
        "occupancy_rate_errors": 0,
        "parking_location_count": 0,
        "errors": [],
    }

    if not target_path.exists():
        result["errors"].append(f"Dataset file not found at: {target_path}")
        return result

    result["file_exists"] = True

    try:
        df = pd.read_csv(target_path)
    except Exception as e:
        result["errors"].append(f"Failed to read CSV file: {str(e)}")
        return result

    result["row_count"] = int(len(df))

    # 2. Check required columns
    cols_ok, missing_cols = validate_required_columns(df)
    if not cols_ok:
        result["errors"].append(f"Missing required columns: {missing_cols}")
        return result

    # 3. Check timestamps valid
    try:
        parsed_timestamps = pd.to_datetime(df["timestamp"], errors="coerce")
        invalid_ts_count = int(parsed_timestamps.isna().sum())
        if invalid_ts_count > 0:
            result["errors"].append(f"Found {invalid_ts_count} invalid timestamps.")
    except Exception as e:
        result["errors"].append(f"Timestamp parsing error: {str(e)}")

    # 4. Check missing values across the entire dataset
    missing_total = int(df.isna().sum().sum())
    result["missing_values"] = missing_total
    if missing_total > 0:
        result["errors"].append(f"Dataset contains {missing_total} missing values.")

    # 5. Check duplicate rows
    dup_rows = int(df.duplicated().sum())
    result["duplicate_rows"] = dup_rows
    if dup_rows > 0:
        result["errors"].append(f"Dataset contains {dup_rows} duplicate rows.")

    # 6. Check duplicate timestamp & parking_id keys
    dup_keys = int(df.duplicated(subset=["timestamp", "parking_id"]).sum())
    result["duplicate_keys"] = dup_keys
    if dup_keys > 0:
        result["errors"].append(
            f"Dataset contains {dup_keys} duplicate timestamp & parking_id keys."
        )

    # 7, 8, 9, 10. Check derived mathematical integrity
    derived_errors = validate_derived_columns(df)
    result["available_space_errors"] = derived_errors["available_space_errors"]
    result["occupancy_rate_errors"] = derived_errors["occupancy_rate_errors"]
    result["invalid_occupancy_rows"] = derived_errors["invalid_occupancy_rows"]

    if derived_errors["invalid_occupancy_rows"] > 0:
        result["errors"].append(
            f"{derived_errors['invalid_occupancy_rows']} rows have invalid occupied_spaces."
        )
    if derived_errors["available_space_errors"] > 0:
        result["errors"].append(
            f"{derived_errors['available_space_errors']} rows have available_spaces mismatch."
        )
    if derived_errors["occupancy_rate_errors"] > 0:
        result["errors"].append(
            f"{derived_errors['occupancy_rate_errors']} rows have occupancy_rate calculation mismatch."
        )

    # 11 & 12. Non-negative distance and price
    if (df["distance_km"] < 0).any():
        result["errors"].append("distance_km contains negative values.")
    if (df["price_per_hour"] < 0).any():
        result["errors"].append("price_per_hour contains negative values.")

    # 13, 14, 15. Binary flags (0 or 1)
    for flag_col in ["is_weekend", "is_peak_hour", "event_flag"]:
        unique_vals = set(df[flag_col].unique())
        if not unique_vals.issubset({0, 1}):
            result["errors"].append(f"{flag_col} contains values other than 0 and 1: {unique_vals}")

    # 16. Exactly five parking locations exist
    unique_locations = df["parking_id"].unique()
    result["parking_location_count"] = int(len(unique_locations))
    if len(unique_locations) != 5:
        result["errors"].append(
            f"Expected 5 parking locations, but found {len(unique_locations)}: {list(unique_locations)}"
        )

    # 17. data_source clearly indicates simulated data
    if not (df["data_source"].str.lower() == "simulated").all():
        result["errors"].append("data_source column contains values other than 'simulated'.")

    # Overall valid status
    result["valid"] = len(result["errors"]) == 0

    return result
