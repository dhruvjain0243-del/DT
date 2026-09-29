"""Unit tests for FastAPI endpoints."""

from fastapi.testclient import TestClient
import pytest
from api.main import app

client = TestClient(app)


def test_api_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "PARKWISE API"
    assert data["status"] in ["healthy", "degraded"]


def test_api_locations():
    response = client.get("/locations")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["count"] == 5


def test_api_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "model_mae" in data["metrics"]


def test_api_recommendations_post():
    payload = {
        "arrival_timestamp": "2026-01-15 18:00:00",
        "preference": "Best balance",
        "parking_type": "All",
    }
    response = client.post("/recommendations", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["recommendations"]) <= 3
    first_rec = data["recommendations"][0]
    assert "parking_id" in first_rec
    assert "recommendation_score" in first_rec
    assert "explanation" in first_rec


def test_api_feedback_post():
    payload = {
        "parking_id": "P3",
        "actual_status": "Nearly Full",
        "comment": "FastAPI endpoint test feedback.",
    }
    response = client.post("/feedback", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
