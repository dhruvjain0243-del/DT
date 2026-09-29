"""
CLI script to validate the PARKWISE parking dataset against 17 verification rules.
Run command: python scripts/validate_data.py
"""

import json
import sys
from pathlib import Path

# Ensure root directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.validation_service import validate_dataset


def main():
    print("=" * 65)
    print("PARKWISE DATASET VALIDATION PIPELINE")
    print("=" * 65)

    result = validate_dataset()

    # Formatted display of structured result
    display_result = {
        "valid": result["valid"],
        "row_count": result["row_count"],
        "missing_values": result["missing_values"],
        "duplicate_rows": result["duplicate_rows"],
        "duplicate_keys": result["duplicate_keys"],
        "invalid_occupancy_rows": result["invalid_occupancy_rows"],
        "available_space_errors": result["available_space_errors"],
        "occupancy_rate_errors": result["occupancy_rate_errors"],
        "parking_location_count": result["parking_location_count"],
    }

    print("\n[Validation Metrics Summary]:")
    print(json.dumps(display_result, indent=4))

    if result["errors"]:
        print("\n[Validation Errors Detected]:")
        for err in result["errors"]:
            print(f"  - [FAIL] {err}")
        print("\nDataset validation FAILED. Please review the issues above.")
        sys.exit(1)
    else:
        print("\n[PASS] Dataset validation PASSED all 17 verification criteria successfully.")
        print(f"File verified: {result['filepath']}")
        sys.exit(0)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
