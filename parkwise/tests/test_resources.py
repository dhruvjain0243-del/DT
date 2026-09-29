from backend.app.models import UserRole

from .helpers import create_user, headers_for


def test_admin_can_create_facility_zone_and_slot(client, db_session):
    admin = create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)
    headers = headers_for(admin)
    facility = client.post(
        "/api/facilities",
        headers=headers,
        json={"name": "Campus", "address": "Main Road", "total_capacity": 5},
    )
    assert facility.status_code == 201
    zone = client.post(
        f"/api/facilities/{facility.json()['id']}/zones",
        headers=headers,
        json={"name": "Cars", "vehicle_type": "CAR", "capacity": 5},
    )
    assert zone.status_code == 201
    slot = client.post(
        f"/api/zones/{zone.json()['id']}/slots",
        headers=headers,
        json={"slot_code": "A-01", "row_label": "A"},
    )
    assert slot.status_code == 201
    assert slot.json()["status"] == "AVAILABLE"


def test_zone_capacity_cannot_exceed_facility(client, db_session):
    admin = create_user(db_session, email="capacity@example.com", role=UserRole.ADMIN)
    headers = headers_for(admin)
    facility = client.post(
        "/api/facilities",
        headers=headers,
        json={"name": "Small", "address": "Small Road", "total_capacity": 1},
    ).json()
    response = client.post(
        f"/api/facilities/{facility['id']}/zones",
        headers=headers,
        json={"name": "Too large", "vehicle_type": "CAR", "capacity": 2},
    )
    assert response.status_code == 400
