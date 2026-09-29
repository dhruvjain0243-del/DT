from backend.app.models import UserRole

from .helpers import create_user, headers_for, seed_parking_api


def test_admin_reports_csv_and_prediction_api(client, db_session):
    admin = create_user(db_session, email="reports-admin@example.com", role=UserRole.ADMIN)
    headers = headers_for(admin)
    facility, _, _ = seed_parking_api(client, headers, capacity=2)
    _, student_headers, vehicle = _create_student_vehicle(client, db_session)
    ticket = client.post(
        "/api/parking/entry",
        headers=student_headers,
        json={"vehicle_id": vehicle["id"], "facility_id": facility["id"]},
    ).json()
    client.post(
        "/api/parking/exit",
        headers=student_headers,
        json={"ticket_id": ticket["ticket_id"], "qr_token": ticket["qr_token"]},
    )

    history = client.get("/api/reports/sessions", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    csv_response = client.get("/api/reports/export-csv", headers=headers)
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert ticket["ticket_id"] in csv_response.text

    prediction = client.post("/api/predictions/run", headers=headers)
    assert prediction.status_code == 200
    assert prediction.json()["model_available"] is True
    assert prediction.json()["predictions"][0]["facility_id"] == facility["id"]
    latest = client.get("/api/predictions/latest", headers=headers)
    assert latest.status_code == 200
    assert latest.json()[0]["predicted_available_spaces"] >= 0


def test_student_cannot_view_reports_or_feedback_admin_list(client, db_session):
    student = create_user(db_session, email="reports-student@example.com")
    headers = headers_for(student)
    assert client.get("/api/reports/daily", headers=headers).status_code == 403
    assert client.get("/api/feedback", headers=headers).status_code == 403


def _create_student_vehicle(client, db_session):
    student = create_user(db_session, email="reporting-student@example.com")
    headers = headers_for(student)
    vehicle = client.post(
        "/api/vehicles",
        headers=headers,
        json={"registration_number": "REPORT12345", "vehicle_type": "CAR"},
    ).json()
    return student, headers, vehicle
