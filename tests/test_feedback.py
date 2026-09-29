"""Unit tests for user feedback service."""

import os
import tempfile
from pathlib import Path
import pytest
from backend.feedback_service import ensure_feedback_storage, load_feedback, save_feedback


def test_feedback_lifecycle_temporary():
    """Verify that feedback can be saved and loaded from a temporary storage path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_csv = Path(tmpdir) / "test_feedback.csv"

        # Ensure initialization
        ensure_feedback_storage(temp_csv)
        assert temp_csv.exists()

        initial_df = load_feedback(temp_csv)
        assert len(initial_df) == 0

        # Save record
        ok = save_feedback(
            parking_id="P1",
            actual_status="Available",
            comment="Plenty of parking spots open on 2nd floor.",
            filepath=temp_csv,
        )
        assert ok is True

        # Load and verify
        updated_df = load_feedback(temp_csv)
        assert len(updated_df) == 1
        assert updated_df.iloc[0]["parking_id"] == "P1"
        assert updated_df.iloc[0]["actual_status"] == "Available"
        assert updated_df.iloc[0]["comment"] == "Plenty of parking spots open on 2nd floor."


def test_invalid_status_rejection():
    """Verify that unpermitted statuses raise ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_csv = Path(tmpdir) / "test_feedback.csv"
        with pytest.raises(ValueError):
            save_feedback(
                parking_id="P1",
                actual_status="Completely Empty",  # Not in allowed statuses
                comment="Invalid status test",
                filepath=temp_csv,
            )
