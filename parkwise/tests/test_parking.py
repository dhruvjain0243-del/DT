from datetime import UTC, datetime

import pytest

from backend.app.models import ParkingSession, ParkingSessionStatus, ParkingSlot, SlotStatus, UserRole

from .helpers import create_user, headers_for, seed_parking_api


def setup_user_vehicle(client, db_session, email: str):
    user = create_user(db_session, email=email)
    headers = headers_for(user)
    registration = "".join(character for character in email.split("@")[0] if character.isalnum())
    vehicle = client.post(
        "/api/vehicles",
        headers=headers,
        json={"registration_number": registration[:10] + "12345", "vehicle_type": "CAR"},
    ).json()
    return user, headers, vehicle


def create_active_ticket(client, db_session, *, email="qr-exit@example.com", role=UserRole.STUDENT):
    admin = create_user(db_session, email=f"admin-{email}", role=UserRole.ADMIN)
    facility, _, slots = seed_parking_api(client, headers_for(admin), capacity=2)
    user, headers, vehicle = setup_user_vehicle(client, db_session, email)
    if role != UserRole.STUDENT:
        user.role = role
        db_session.commit()
        headers = headers_for(user)
    response = client.post(
        "/api/parking/entry",
        headers=headers,
        json={"vehicle_id": vehicle["id"], "facility_id": facility["id"]},
    )
    assert response.status_code == 201
    return user, headers, facility, slots, vehicle, response.json()


def test_successful_entry_and_live_occupancy(client, db_session):
    admin = create_user(db_session, email="entry-admin@example.com", role=UserRole.ADMIN)
    facility, _, _ = seed_parking_api(client, headers_for(admin), capacity=2)
    _, user_headers, vehicle = setup_user_vehicle(client, db_session, "entryuser@example.com")
    response = client.post(
        "/api/parking/entry",
        headers=user_headers,
        json={"vehicle_id": vehicle["id"], "facility_id": facility["id"]},
    )
    assert response.status_code == 201
    assert response.json()["ticket_id"].startswith("PW-")
    availability = client.get("/api/availability", headers=user_headers).json()[0]
    assert availability["occupied_spaces"] == 1
    assert availability["available_spaces"] == 1


def test_qr_entry_uses_scanned_slot_and_rejects_invalid_qr(client, db_session):
    admin = create_user(db_session, email="qr-entry-admin@example.com", role=UserRole.ADMIN)
    admin_headers = headers_for(admin)
    facility, _, slots = seed_parking_api(client, admin_headers, capacity=2)
    qr_response = client.post(f"/api/slots/{slots[1]['id']}/qr", headers=admin_headers)
    assert qr_response.status_code == 200

    _, user_headers, vehicle = setup_user_vehicle(client, db_session, "qrusr@example.com")
    invalid = client.post(
        "/api/parking/entry",
        headers=user_headers,
        json={
            "vehicle_id": vehicle["id"],
            "facility_id": facility["id"],
            "entry_method": "QR",
            "slot_qr_token": "invalid-slot-token-value",
        },
    )
    assert invalid.status_code == 400

    response = client.post(
        "/api/parking/entry",
        headers=user_headers,
        json={
            "vehicle_id": vehicle["id"],
            "facility_id": facility["id"],
            "entry_method": "QR",
            "slot_qr_token": qr_response.json()["qr_token"],
        },
    )
    assert response.status_code == 201
    assert response.json()["slot_id"] == slots[1]["id"]
    assert response.json()["entry_method"] == "QR"


def test_entry_full_and_duplicate_active_session(client, db_session):
    admin = create_user(db_session, email="full-admin@example.com", role=UserRole.ADMIN)
    facility, _, _ = seed_parking_api(client, headers_for(admin), capacity=1)
    _, first_headers, first_vehicle = setup_user_vehicle(client, db_session, "firstcar@example.com")
    first = client.post(
        "/api/parking/entry",
        headers=first_headers,
        json={"vehicle_id": first_vehicle["id"], "facility_id": facility["id"]},
    )
    assert first.status_code == 201
    duplicate = client.post(
        "/api/parking/entry",
        headers=first_headers,
        json={"vehicle_id": first_vehicle["id"], "facility_id": facility["id"]},
    )
    assert duplicate.status_code == 409
    _, second_headers, second_vehicle = setup_user_vehicle(client, db_session, "secondcar@example.com")
    full = client.post(
        "/api/parking/entry",
        headers=second_headers,
        json={"vehicle_id": second_vehicle["id"], "facility_id": facility["id"]},
    )
    assert full.status_code == 409


def test_successful_and_duplicate_exit(client, db_session):
    _, headers, facility, slots, vehicle, ticket = create_active_ticket(
        client, db_session, email="exitcar@example.com"
    )
    payload = {"ticket_id": ticket["ticket_id"], "qr_token": ticket["qr_token"]}
    bad_qr = client.post(
        "/api/parking/exit",
        headers=headers,
        json={"ticket_id": ticket["ticket_id"], "qr_token": "invalid-token-value-long-enough"},
    )
    assert bad_qr.status_code == 400
    assert db_session.get(ParkingSlot, ticket["slot_id"]).status == SlotStatus.OCCUPIED
    exit_response = client.post("/api/parking/exit", headers=headers, json=payload)
    assert exit_response.status_code == 200
    result = exit_response.json()
    assert result["status"] == "COMPLETED"
    assert result["ticket_id"] == ticket["ticket_id"]
    assert result["registration_number"] == vehicle["registration_number"]
    assert result["vehicle_type"] == vehicle["vehicle_type"]
    assert result["slot_id"] == ticket["slot_id"] == slots[0]["id"]
    assert result["slot_code"] == ticket["slot_code"]
    ticket_entry_time = datetime.fromisoformat(ticket["entry_time"])
    if ticket_entry_time.tzinfo is None:
        ticket_entry_time = ticket_entry_time.replace(tzinfo=UTC)
    assert datetime.fromisoformat(result["entry_time"]) == ticket_entry_time
    assert result["exit_time"]
    assert result["duration_minutes"] >= 0
    assert client.post("/api/parking/exit", headers=headers, json=payload).status_code == 409
    session = db_session.query(ParkingSession).filter_by(ticket_id=ticket["ticket_id"]).one()
    assert session.status == ParkingSessionStatus.COMPLETED
    assert session.exit_time is not None
    assert db_session.get(ParkingSlot, ticket["slot_id"]).status == SlotStatus.AVAILABLE
    availability = client.get("/api/availability", headers=headers).json()[0]
    assert availability["occupied_spaces"] == 0
    assert availability["available_spaces"] == facility["total_capacity"]


def test_exit_rejects_unknown_ticket_and_non_owner_without_releasing_slot(client, db_session):
    _, owner_headers, facility, _, _, ticket = create_active_ticket(
        client, db_session, email="ticketowner@example.com"
    )
    unauthenticated = client.post(
        "/api/parking/exit",
        json={"ticket_id": ticket["ticket_id"], "qr_token": ticket["qr_token"]},
    )
    assert unauthenticated.status_code == 401
    unknown_ticket = client.post(
        "/api/parking/exit",
        headers=owner_headers,
        json={"ticket_id": "PW-NOT-FOUND", "qr_token": ticket["qr_token"]},
    )
    assert unknown_ticket.status_code == 404

    other = create_user(db_session, email="exitother@example.com", role=UserRole.STAFF)
    forbidden = client.post(
        "/api/parking/exit",
        headers=headers_for(other),
        json={"ticket_id": ticket["ticket_id"], "qr_token": ticket["qr_token"]},
    )
    assert forbidden.status_code == 403
    assert db_session.get(ParkingSlot, ticket["slot_id"]).status == SlotStatus.OCCUPIED
    availability = client.get("/api/availability", headers=owner_headers).json()[0]
    assert availability["occupied_spaces"] == 1
    assert availability["available_spaces"] == facility["total_capacity"] - 1


@pytest.mark.parametrize("owner_role", [UserRole.STUDENT, UserRole.STAFF])
def test_student_and_staff_can_exit_their_own_active_session(client, db_session, owner_role):
    _, headers, _, _, _, ticket = create_active_ticket(
        client,
        db_session,
        email=f"{owner_role.value.lower()}owner@example.com",
        role=owner_role,
    )
    response = client.post(
        "/api/parking/exit",
        headers=headers,
        json={"ticket_id": ticket["ticket_id"], "qr_token": ticket["qr_token"]},
    )
    assert response.status_code == 200


@pytest.mark.parametrize("staff_role", [UserRole.ADMIN, UserRole.ATTENDANT])
def test_admin_and_attendant_can_assist_qr_exit(client, db_session, staff_role):
    _, _, _, _, _, ticket = create_active_ticket(
        client, db_session, email=f"assist-{staff_role.value.lower()}@example.com"
    )
    staff = create_user(
        db_session,
        email=f"{staff_role.value.lower()}-exit@example.com",
        role=staff_role,
    )
    response = client.post(
        "/api/parking/exit",
        headers=headers_for(staff),
        json={"ticket_id": ticket["ticket_id"], "qr_token": ticket["qr_token"]},
    )
    assert response.status_code == 200


def test_invalid_ticket_and_user_isolation(client, db_session):
    owner = create_user(db_session, email="owner@example.com")
    other = create_user(db_session, email="other@example.com")
    assert client.get("/api/parking/session/PW-NOTFOUND", headers=headers_for(owner)).status_code == 404
    admin = create_user(db_session, email="isolation-admin@example.com", role=UserRole.ADMIN)
    facility, _, _ = seed_parking_api(client, headers_for(admin), capacity=1)
    vehicle = client.post(
        "/api/vehicles",
        headers=headers_for(owner),
        json={"registration_number": "OWNER12345", "vehicle_type": "CAR"},
    ).json()
    ticket = client.post(
        "/api/parking/entry",
        headers=headers_for(owner),
        json={"vehicle_id": vehicle["id"], "facility_id": facility["id"]},
    ).json()
    assert client.get(
        f"/api/parking/session/{ticket['ticket_id']}", headers=headers_for(other)
    ).status_code == 403
    assert client.get(
        f"/api/parking/find-my-vehicle/{ticket['ticket_id']}", headers=headers_for(other)
    ).status_code == 403


def test_lost_ticket_recovery_and_wrong_slot_correction(client, db_session):
    admin = create_user(db_session, email="ops-admin@example.com", role=UserRole.ADMIN)
    admin_headers = headers_for(admin)
    facility, _, slots = seed_parking_api(client, admin_headers, capacity=2)
    _, user_headers, vehicle = setup_user_vehicle(client, db_session, "recovercar@example.com")
    ticket = client.post(
        "/api/parking/entry",
        headers=user_headers,
        json={"vehicle_id": vehicle["id"], "facility_id": facility["id"]},
    ).json()
    recovered = client.get(
        "/api/parking/recover",
        headers=admin_headers,
        params={"registration_number": vehicle["registration_number"]},
    )
    assert recovered.status_code == 200
    assert recovered.json()["ticket_id"] == ticket["ticket_id"]
    target_slot = next(item for item in slots if item["id"] != ticket["slot_id"])
    corrected = client.put(
        f"/api/parking/session/{ticket['ticket_id']}/slot",
        headers=admin_headers,
        json={"slot_id": target_slot["id"]},
    )
    assert corrected.status_code == 200
    assert corrected.json()["slot_id"] == target_slot["id"]
