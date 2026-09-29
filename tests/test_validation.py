"""Unit tests for dataset validation service."""

import pandas as pd
import pytest
from backend.config import EXPECTED_COLUMNS
from backend.validation_service import (
    validate_dataset,
    validate_derived_columns,
    validate_required_columns,
)


def test_validate_dataset_on_real_csv():
    """Verify that the real dataset passes all validation rules."""
    result = validate_dataset()
    assert result["file_exists"] is True
    assert result["valid"] is True
    assert result["row_count"] == 3750
    assert result["missing_values"] == 0
    assert result["duplicate_rows"] == 0
    assert result["duplicate_keys"] == 0
    assert result["parking_location_count"] == 5
    assert len(result["errors"]) == 0


def test_validate_required_columns():
    """Verify detection of missing required columns."""
    sample_df = pd.DataFrame({"timestamp": ["2026-01-01 08:00:00"], "parking_id": ["P1"]})
    is_valid, missing = validate_required_columns(sample_df)
    assert is_valid is False
    assert len(missing) == len(EXPECTED_COLUMNS) - 2


def test_validate_derived_columns_detects_mismatch():
    """Verify detection of space and occupancy calculation discrepancies."""
    mismatched_df = pd.DataFrame(
        {
            "total_spaces": [100],
            "occupied_spaces": [60],
            "available_spaces": [50],  # Error: should be 40
            "occupancy_rate": [0.90],   # Error: should be 0.60
        }
    )
    errors = validate_derived_columns(mismatched_df)
    assert errors["available_space_errors"] == 1
    assert errors["occupancy_rate_errors"] == 1
    assert errors["invalid_occupancy_rows"] == 0
