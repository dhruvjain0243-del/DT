"""
CLI script to train the PARKWISE parking prediction model and generate artifacts.
Run command: python scripts/train_model.py
"""

import json
import sys
from pathlib import Path

# Ensure root directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config import FEATURE_COLUMNS_PATH, METRICS_PATH, MODEL_PATH
from backend.model_service import train_model
from backend.validation_service import validate_dataset


def main():
    print("=" * 65)
    print("PARKWISE MODEL TRAINING PIPELINE")
    print("=" * 65)

    # Step 1: Validate dataset
    print("\n[Step 1/3] Validating input dataset...")
    val_result = validate_dataset()
    if not val_result["valid"]:
        print("[ERROR] Dataset validation failed. Cannot proceed with training.")
        for err in val_result["errors"]:
            print(f"  - {err}")
        sys.exit(1)
    print("[OK] Dataset validation passed successfully.")

    # Step 2: Train baseline and Random Forest model
    print("\n[Step 2/3] Training baseline and Random Forest model (80/20 chronological split)...")
    try:
        _, metrics = train_model()
    except Exception as e:
        print(f"[ERROR] Training encountered an error: {str(e)}")
        sys.exit(1)

    # Step 3: Report results
    print("\n[Step 3/3] Model Evaluation Metrics:")
    print(json.dumps(metrics, indent=4))

    print("\n[Artifacts Saved Successfully]:")
    print(f"  - Model File:           {MODEL_PATH}")
    print(f"  - Feature Columns:      {FEATURE_COLUMNS_PATH}")
    print(f"  - Performance Metrics:  {METRICS_PATH}")
    print("\nTraining completed successfully! You may now launch the application with:")
    print("  streamlit run app.py")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
