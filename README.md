# PARKWISE
## Smart Parking Availability Prediction and Recommendation System

> **Academic Prototype Notice:** This system is an academic prototype powered by a 30-day simulated parking dataset. Predictions do not guarantee real-time parking spot availability.

---

### 1. Project Title
**PARKWISE: Smart Parking Availability Prediction and Recommendation System**

### 2. Problem Statement
Urban drivers waste significant time, consume unnecessary fuel, and contribute to traffic congestion searching for parking spaces during peak commuting hours. Conventional parking navigation systems either rely solely on static distance or require cost-prohibitive IoT camera infrastructure. Drivers require an intelligent, forward-looking system that can forecast parking capacity ahead of their actual arrival time and recommend optimal facilities balancing availability, proximity, and tariff rates.

### 3. Target Users
- **Urban Commuters & Office Workers:** Seeking dependable parking spots close to business districts during morning and evening rush hours.
- **Weekend Shoppers & Visitors:** Looking for cost-effective parking near commercial and retail centers.
- **Municipal Planners & Parking Operators:** Academic researchers analyzing parking utilization trends and evaluating predictive allocation algorithms.

### 4. Objective
To build an end-to-end full-stack prototype that:
1. Validates and preprocesses simulated parking time-series data across multiple urban facilities.
2. Forecasts available parking spaces approximately **30 minutes ahead** using a Random Forest regressor.
3. Ranks facilities based on multi-factor scoring (predicted availability, distance, and price).
4. Recommends the top three parking facilities tailored to user preferences.
5. Provides an interactive Streamlit web dashboard and RESTful API layer without requiring external APIs, payment gateways, or live IoT hardware.

### 5. Main Features
- **30-Minute Predictive Horizon:** Eliminates current-state lag by predicting future parking availability at the driver's planned arrival time.
- **Multi-Factor Recommendation Engine:** Combines availability (50%), distance (30%), and hourly cost (20%) into a normalized composite score.
- **User Preference Modes:** Supports sorting by *Best balance*, *Highest availability*, *Nearest*, and *Cheapest*.
- **Interactive Visualizations:** Plotly bar charts for capacity and composite scores, plus interactive 30-day historical occupancy trendlines.
- **Integrated Geospatial Map:** Visualizes facility locations, sizes, and predicted spaces using native Streamlit mapping with automatic tabular fallback.
- **Ground-Truth Feedback Loop:** Allows drivers to record actual parking observations (`Available`, `Nearly Full`, `Full`) saved persistently to CSV.
- **Comprehensive Quality & Metrics Auditing:** Displays model comparison (Random Forest vs. Historical Baseline), MAE, RMSE, R², and dataset validation status.
- **Dual-Mode Backend:** Seamless direct service integration for Streamlit, alongside an optional FastAPI REST service (`api/main.py`).

### 6. Architecture
```
                                 ┌───────────────────────────────┐
                                 │       User Web Browser        │
                                 └───────────────┬───────────────┘
                                                 │
                     ┌───────────────────────────┴───────────────────────────┐
                     ▼                                                       ▼
        ┌─────────────────────────┐                             ┌─────────────────────────┐
        │   Streamlit Frontend    │                             │    FastAPI REST API     │
        │        (app.py)         │                             │     (api/main.py)       │
        └────────────┬────────────┘                             └────────────┬────────────┘
                     │                                                       │
                     └───────────────────────────┬───────────────────────────┘
                                                 ▼
        ┌─────────────────────────────────────────────────────────────────────────────────┐
        │                               Backend Service Layer                             │
        │  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────────┐  │
        │  │   data_service.py    │  │ validation_service.py│  │   feature_service.py  │  │
        │  └──────────────────────┘  └──────────────────────┘  └───────────────────────┘  │
        │  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────────┐  │
        │  │   model_service.py   │  │recommendation_service│  │  feedback_service.py  │  │
        │  └──────────────────────┘  └──────────────────────┘  └───────────────────────┘  │
        └────────────────────────────────────────┬────────────────────────────────────────┘
                                                 ▼
        ┌─────────────────────────────────────────────────────────────────────────────────┐
        │                                Storage & Artifacts                              │
        │  • data/ParkWise_30day_simulated_parking_dataset-1.csv                          │
        │  • models/parking_model.pkl (RandomForestRegressor)                             │
        │  • models/feature_columns.json & model_metrics.json                             │
        │  • storage/user_feedback.csv                                                    │
        └─────────────────────────────────────────────────────────────────────────────────┘
```

### 7. Dataset Description
- **Records:** 3,750 observations collected across 30 simulated calendar days (January 1, 2026 – January 30, 2026).
- **Sampling Interval:** Every 30 minutes from 08:00 AM to 08:30 PM daily (25 timestamps per day).
- **Five Configured Parking Facilities:**
  1. `P1` — **Central Mall Parking** (Mall, 200 spaces, ₹40/hr, 0.8 km)
  2. `P2` — **City Office Parking** (Office, 150 spaces, ₹30/hr, 1.4 km)
  3. `P3` — **Market Road Parking** (Street, 80 spaces, ₹20/hr, 0.5 km)
  4. `P4` — **Metro Station Parking** (Transit, 250 spaces, ₹25/hr, 1.8 km)
  5. `P5` — **College Campus Parking** (Campus, 120 spaces, ₹15/hr, 1.0 km)

### 8. Simulated-Data Limitation
All parking measurements, occupancy rates, weather conditions, and traffic levels in this project are generated synthetically for academic demonstration. The dataset simulates diurnal peaks (office hours, shopping spikes, transit surges) but does not reflect live camera or sensor feeds. Predictions must not be treated as a legal or real-time parking reservation guarantee.

### 9. Data Columns
| Column Name | Data Type | Description |
|---|---|---|
| `timestamp` | Datetime (YYYY-MM-DD HH:MM:SS) | Observation recording timestamp |
| `parking_id` | String (`P1` to `P5`) | Unique parking lot code |
| `parking_name` | String | Facility descriptive title |
| `parking_type` | String (`Mall`, `Office`, `Street`, `Transit`, `Campus`) | Facility zoning classification |
| `latitude` | Float | Geographic latitude coordinate |
| `longitude` | Float | Geographic longitude coordinate |
| `total_spaces` | Integer | Total physical parking capacity |
| `occupied_spaces` | Integer | Number of currently taken parking spots |
| `available_spaces` | Integer | Currently vacant parking spots (`total - occupied`) |
| `occupancy_rate` | Float | Ratio of occupied to total capacity (`occupied / total`) |
| `distance_km` | Float | Distance from destination/center in kilometers |
| `price_per_hour` | Float | Tariff in rupees per hour (₹/hr) |
| `traffic_level` | String (`low`, `medium`, `high`) | Surrounding road traffic condition |
| `weather` | String (`clear`, `rain`, `cloudy`) | Ambient weather condition |
| `is_weekend` | Integer (0 or 1) | Weekend binary flag |
| `is_peak_hour` | Integer (0 or 1) | Peak rush-hour binary flag |
| `event_flag` | Integer (0 or 1) | Nearby special event flag |
| `data_source` | String (`simulated`) | Data provenance identifier |

### 10. Prediction Target
- **Target Variable:** `target_available_30min`
- **Definition:** The number of available parking spaces at the next scheduled observation (+30 minutes later) for the specific facility.
- **Shift Calculation:**
  ```python
  df = df.sort_values(["parking_id", "timestamp"])
  df["target_available_30min"] = df.groupby("parking_id")["available_spaces"].shift(-1)
  df = df.dropna(subset=["target_available_30min"])
  ```
- **Leakage Prevention:** `available_spaces`, `occupancy_rate`, `target_available_30min`, and `timestamp` are strictly excluded from model feature inputs.

### 11. Model Method
- **Algorithm:** `RandomForestRegressor` from `scikit-learn`
- **Hyperparameters:** `n_estimators=100`, `max_depth=12`, `random_state=42`, `n_jobs=-1`
- **Features Used (10 predictors):**
  `hour`, `minute`, `day_of_week`, `is_weekend`, `is_peak_hour`, `total_spaces`, `occupied_spaces`, `distance_km`, `price_per_hour`, `event_flag`.
- **Chronological Split:**
  - Training Set: First 80% of timeline (2,995 observations)
  - Testing Set: Final 20% of timeline (750 observations)
  - Shuffling is disabled to preserve temporal order.

### 12. Baseline Method
- **Method:** Historical Average per Parking Location.
- For each `parking_id`, the mean number of `available_spaces` is calculated exclusively from the training partition.
- Test observations are evaluated against their respective location baseline mean.

### 13. Recommendation Formula
For each facility, the raw prediction is first bounded:
$$\text{predicted\_available\_spaces} = \min(\max(\hat{y}, 0), \text{total\_spaces})$$

Normalized sub-scores (0.0 to 1.0):
$$\text{availability\_score} = \frac{\text{predicted\_available\_spaces}}{\text{total\_spaces}}$$
$$\text{distance\_score} = 1 - \frac{\text{distance\_km}}{\max(\text{distance\_km})}$$
$$\text{price\_score} = 1 - \frac{\text{price\_per\_hour}}{\max(\text{price\_per\_hour})}$$

Composite Recommendation Score:
$$\text{recommendation\_score} = 0.50 \cdot \text{availability\_score} + 0.30 \cdot \text{distance\_score} + 0.20 \cdot \text{price\_score}$$

Availability classification:
- **High:** $\text{availability\_score} \ge 0.60$
- **Medium:** $0.25 \le \text{availability\_score} < 0.60$
- **Low:** $\text{availability\_score} < 0.25$

### 14. Evaluation Metrics
Evaluated on the 20% unseen chronological test split (750 samples):

| Metric | Historical Baseline | Random Forest Model | Improvement |
|---|---|---|---|
| **Mean Absolute Error (MAE)** | 28.9982 spaces | **5.1269 spaces** | **82.3% error reduction** |
| **Root Mean Squared Error (RMSE)** | — | **6.6059 spaces** | — |
| **Coefficient of Determination ($R^2$)** | — | **0.9713 (97.1%)** | — |

*MAE represents the average prediction error in the number of parking spaces. Lower MAE is better.*

### 15. Folder Structure
```
parkwise/
│
├── app.py                     # Streamlit frontend dashboard
├── requirements.txt           # Environment dependencies
├── README.md                  # Comprehensive documentation
├── .gitignore                 # Version control exclusions
│
├── data/
│   └── ParkWise_30day_simulated_parking_dataset-1.csv
│
├── models/
│   ├── parking_model.pkl      # Trained Random Forest regressor
│   ├── feature_columns.json   # Exact feature ordering definition
│   └── model_metrics.json     # Stored evaluation metrics
│
├── backend/
│   ├── __init__.py
│   ├── config.py              # Constants, paths, weights, preferences
│   ├── data_service.py        # Loading, datetime parsing, nearest queries
│   ├── validation_service.py  # 17-point dataset integrity checker
│   ├── feature_service.py     # Temporal features & +30min target creation
│   ├── model_service.py       # ML training, evaluation & inference
│   ├── recommendation_service.py # Scoring, confidence & ranking engine
│   └── feedback_service.py    # CSV user feedback read/append
│
├── scripts/
│   ├── validate_data.py       # CLI dataset validation script
│   └── train_model.py         # CLI model training pipeline script
│
├── storage/
│   └── user_feedback.csv      # Ground-truth user observation logs
│
├── api/
│   ├── __init__.py
│   └── main.py                # Optional FastAPI service
│
└── tests/
    ├── test_validation.py     # Validation unit tests
    ├── test_features.py       # Feature engineering unit tests
    ├── test_recommendations.py# Recommendation engine unit tests
    ├── test_feedback.py       # Feedback storage unit tests
    └── test_api.py            # FastAPI endpoint tests
```

### 16. Installation Instructions
Ensure Python 3.10+ is installed on your system.

```bash
# 1. Clone or navigate to the project directory
cd parkwise

# 2. Install dependencies
pip install -r requirements.txt
```

### 17. Validation Command
Run the 17-point validation pipeline on the dataset:
```bash
python scripts/validate_data.py
```

### 18. Training Command
Train the historical baseline and Random Forest model, and generate evaluation artifacts:
```bash
python scripts/train_model.py
```

### 19. Streamlit Command
Launch the interactive web application:
```bash
streamlit run app.py
```

### 20. Optional API Command
Launch the FastAPI REST server:
```bash
uvicorn api.main:app --reload
```
Interactive Swagger API documentation will be available at: `http://127.0.0.1:8000/docs`.

### 21. Testing Instructions
Run all unit tests using pytest:
```bash
python -m pytest tests/ -v
```

### 22. Screenshots Section
The Streamlit frontend provides 9 structured visual sections:
1. **Header & Disclaimer:** Prominent academic prototype alert.
2. **Interactive Query Sidebar:** Date selector, 30-min time steps, and ranking criteria.
3. **KPI Summary Cards:** Locations evaluated, top recommendation name, predicted free capacity, score, and model MAE.
4. **Top 3 Facility Cards:** Facility badges, confidence tier, price, distance, and personalized explanations.
5. **Plotly Analytical Charts:** Free capacity distribution, composite score bar chart, and 30-day facility trendlines.
6. **Geographical Facility Map:** Native map pinpointing facility coordinates with point size scaled by capacity.
7. **Model Performance Table:** Baseline vs. Random Forest side-by-side comparison with metric definitions.
8. **Data Quality Audit Table:** Verification audit confirming all 17 dataset consistency rules.
9. **Ground-Truth Feedback Portal:** Form to log actual witnessed parking status and recent submissions table.

### 23. Limitations
- **Simulated Data:** Dataset patterns are synthetic and do not account for unmodelled real-world disruptions (e.g., road closures, sudden accidents).
- **30-Minute Discretization:** Predictions are provided in 30-minute intervals rather than continuous minute-by-minute intervals.
- **Fixed Facility Radius:** Assumes a fixed origin for distance calculations without personalized GPS routes.

### 24. Future Improvements
- Integration with OpenStreetMap routing engines for real-time turn-by-turn travel duration.
- Expanding the model to support variable prediction horizons (+15 min, +45 min, +60 min).
- Online model retraining pipeline that periodically incorporates driver feedback records.
