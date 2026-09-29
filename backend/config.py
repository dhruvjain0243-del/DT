"""
Configuration module for PARKWISE.
Defines filesystem paths, model feature definitions, validation constants,
and recommendation scoring parameters.
"""

from pathlib import Path

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Data directory and potential dataset candidate paths
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
STORAGE_DIR = BASE_DIR / "storage"

# Candidate dataset paths in order of preference
DATASET_CANDIDATES = [
    DATA_DIR / "ParkWise_30day_simulated_parking_dataset-1.csv",
    BASE_DIR / "ParkWise_30day_simulated_parking_dataset-1.csv",
    DATA_DIR / "ParkWise_30day_simulated_parking_dataset (1).csv",
    BASE_DIR / "ParkWise_30day_simulated_parking_dataset (1).csv",
]

def get_dataset_path() -> Path:
    """Find and return existing dataset path among standard candidates."""
    for path in DATASET_CANDIDATES:
        if path.exists():
            return path
    # Default path for error reporting
    return DATA_DIR / "ParkWise_30day_simulated_parking_dataset-1.csv"

# Primary File Paths
DATASET_PATH = get_dataset_path()
MODEL_PATH = MODELS_DIR / "parking_model.pkl"
FEATURE_COLUMNS_PATH = MODELS_DIR / "feature_columns.json"
METRICS_PATH = MODELS_DIR / "model_metrics.json"
FEEDBACK_PATH = STORAGE_DIR / "user_feedback.csv"

# Expected Dataset Columns (18 columns)
EXPECTED_COLUMNS = [
    "timestamp",
    "parking_id",
    "parking_name",
    "parking_type",
    "latitude",
    "longitude",
    "total_spaces",
    "occupied_spaces",
    "available_spaces",
    "occupancy_rate",
    "distance_km",
    "price_per_hour",
    "traffic_level",
    "weather",
    "is_weekend",
    "is_peak_hour",
    "event_flag",
    "data_source",
]

# Expected Parking Locations
EXPECTED_PARKING_LOCATIONS = {
    "P1": "Central Mall Parking",
    "P2": "City Office Parking",
    "P3": "Market Road Parking",
    "P4": "Metro Station Parking",
    "P5": "College Campus Parking",
}

# Ordered Features for ML Model (Strict feature order)
MODEL_FEATURES = [
    "hour",
    "minute",
    "day_of_week",
    "is_weekend",
    "is_peak_hour",
    "total_spaces",
    "occupied_spaces",
    "distance_km",
    "price_per_hour",
    "event_flag",
]

# Target column name
TARGET_COLUMN = "target_available_30min"

# Prediction horizon in minutes
PREDICTION_HORIZON_MINUTES = 30

# Recommendation engine parameters
AVAILABILITY_WEIGHT = 0.50
DISTANCE_WEIGHT = 0.30
PRICE_WEIGHT = 0.20

# Availability classification thresholds
HIGH_AVAILABILITY_THRESHOLD = 0.60
MEDIUM_AVAILABILITY_THRESHOLD = 0.25

# User preference sorting options
PREFERENCE_BEST_BALANCE = "Best balance"
PREFERENCE_HIGHEST_AVAILABILITY = "Highest availability"
PREFERENCE_NEAREST = "Nearest"
PREFERENCE_CHEAPEST = "Cheapest"

PREFERENCE_OPTIONS = [
    PREFERENCE_BEST_BALANCE,
    PREFERENCE_HIGHEST_AVAILABILITY,
    PREFERENCE_NEAREST,
    PREFERENCE_CHEAPEST,
]

# Feedback allowed actual statuses
FEEDBACK_STATUS_OPTIONS = ["Available", "Nearly Full", "Full"]
