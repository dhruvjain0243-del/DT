from backend.app.models import UserRole

from .helpers import create_user, headers_for, seed_parking_api
from .test_parking import setup_user_vehicle


def test_admin_registers_gate_and_scanner_and_records_scan_lifecycle(client, db_session):
    admin = create_user(db_session, email="gate-admin@example.com", role=UserRole.ADMIN)
    admin_headers = headers_for(admin)
    facility, _, _ = seed_parking_api(client, admin_headers)

    gate = client.post(
        f"/api/operations/facilities/{facility['id']}/gates",
        headers=admin_headers,
        json={"name": "Main College Gate", "gate_type": "BOTH"},
    )
    assert gate.status_code == 201
    scanner = client.post(
        f"/api/operations/gates/{gate.json()['id']}/scanners",
        headers=admin_headers,
        json={"name": "Main QR Reader", "device_identifier": "COLLEGE-MAIN-01"},
    )
    assert scanner.status_code == 201

    _, owner_headers, vehicle = setup_user_vehicle(client, db_session, "scan-owner@example.com")
    entry = client.post(
        "/api/parking/entry",
        headers=owner_headers,
        json={
            "vehicle_id": vehicle["id"],
            "facility_id": facility["id"],
            "gate_id": gate.json()["id"],
            "scanner_device_id": scanner.json()["id"],
            "scan_reference": "reader-entry-001",
        },
    )
    assert entry.status_code == 201
    exit_response = client.post(
        "/api/parking/exit",
        headers=owner_headers,
        json={
            "ticket_id": entry.json()["ticket_id"],
            "qr_token": entry.json()["qr_token"],
            "gate_id": gate.json()["id"],
            "scanner_device_id": scanner.json()["id"],
            "scan_reference": "reader-exit-001",
        },
    )
    assert exit_response.status_code == 200
    events = client.get("/api/operations/scan-events", headers=admin_headers)
    assert events.status_code == 200
    assert [(item["scan_type"], item["result"]) for item in events.json()[:2]] == [("EXIT", "SUCCESS"), ("ENTRY", "SUCCESS")]


def test_gate_direction_and_scanner_assignment_are_enforced(client, db_session):
    admin = create_user(db_session, email="direction-admin@example.com", role=UserRole.ADMIN)
    admin_headers = headers_for(admin)
    facility, _, _ = seed_parking_api(client, admin_headers)
    gate = client.post(
        f"/api/operations/facilities/{facility['id']}/gates",
        headers=admin_headers,
        json={"name": "Exit Only", "gate_type": "EXIT"},
    ).json()
    _, owner_headers, vehicle = setup_user_vehicle(client, db_session, "direction-owner@example.com")
    response = client.post(
        "/api/parking/entry",
        headers=owner_headers,
        json={"vehicle_id": vehicle["id"], "facility_id": facility["id"], "gate_id": gate["id"]},
    )
    assert response.status_code == 409

    student = create_user(db_session, email="scanner-student@example.com")
    forbidden = client.post(
        f"/api/operations/facilities/{facility['id']}/gates",
        headers=headers_for(student),
        json={"name": "Not Allowed", "gate_type": "BOTH"},
    )
    assert forbidden.status_code == 403


def test_scanner_key_can_complete_entry_and_qr_exit_without_admin_token(client, db_session):
    admin = create_user(db_session, email="device-admin@example.com", role=UserRole.ADMIN)
    admin_headers = headers_for(admin)
    facility, _, _ = seed_parking_api(client, admin_headers)
    gate = client.post(
        f"/api/operations/facilities/{facility['id']}/gates",
        headers=admin_headers,
        json={"name": "Device Gate", "gate_type": "BOTH"},
    ).json()
    scanner_response = client.post(
        f"/api/operations/gates/{gate['id']}/scanners",
        headers=admin_headers,
        json={"name": "Tablet Scanner", "device_identifier": "TABLET-01"},
    )
    scanner = scanner_response.json()
    assert scanner_response.status_code == 201
    assert scanner["api_key"].startswith("pwsc_")

    _, owner_headers, vehicle = setup_user_vehicle(client, db_session, "device-owner@example.com")
    device_headers = {"X-Scanner-Key": scanner["api_key"]}
    entry = client.post(
        f"/api/operations/scanners/{scanner['id']}/scan",
        headers=device_headers,
        json={"scan_type": "ENTRY", "vehicle_registration": vehicle["registration_number"]},
    )
    assert entry.status_code == 200
    ticket = entry.json()["ticket"]
    exit_response = client.post(
        f"/api/operations/scanners/{scanner['id']}/scan",
        headers=device_headers,
        json={"scan_type": "EXIT", "qr_token": ticket["qr_token"]},
    )
    assert exit_response.status_code == 200
    assert exit_response.json()["result"] == "SUCCESS"


def test_scanner_security_and_rejected_scans_preserve_parking_state(client, db_session):
    admin = create_user(db_session, email="security-admin@example.com", role=UserRole.ADMIN)
    admin_headers = headers_for(admin)
    facility, _, slots = seed_parking_api(client, admin_headers, capacity=1)
    gate = client.post(f"/api/operations/facilities/{facility['id']}/gates", headers=admin_headers, json={"name": "Secure Gate", "gate_type": "BOTH"}).json()
    scanner = client.post(f"/api/operations/gates/{gate['id']}/scanners", headers=admin_headers, json={"name": "Secure Scanner", "device_identifier": "SECURE-01"}).json()
    _, owner_headers, vehicle = setup_user_vehicle(client, db_session, "security-owner@example.com")
    endpoint = f"/api/operations/scanners/{scanner['id']}/scan"

    invalid = client.post(endpoint, headers={"X-Scanner-Key": "pwsc_invalid"}, json={"scan_type": "ENTRY", "vehicle_registration": vehicle["registration_number"]})
    assert invalid.status_code == 401
    assert client.get("/api/availability", headers=owner_headers).json()[0]["occupied_spaces"] == 0

    entry = client.post(endpoint, headers={"X-Scanner-Key": scanner["api_key"]}, json={"scan_type": "ENTRY", "vehicle_registration": vehicle["registration_number"]})
    assert entry.status_code == 200
    ticket = entry.json()["ticket"]
    duplicate_entry = client.post(endpoint, headers={"X-Scanner-Key": scanner["api_key"]}, json={"scan_type": "ENTRY", "vehicle_registration": vehicle["registration_number"]})
    assert duplicate_entry.status_code == 409
    assert client.get("/api/availability", headers=owner_headers).json()[0]["occupied_spaces"] == 1

    bad_exit = client.post(endpoint, headers={"X-Scanner-Key": scanner["api_key"]}, json={"scan_type": "EXIT", "qr_token": "invalid-ticket-token-value-long-enough"})
    assert bad_exit.status_code == 400
    assert client.get("/api/availability", headers=owner_headers).json()[0]["occupied_spaces"] == 1

    exit_response = client.post(endpoint, headers={"X-Scanner-Key": scanner["api_key"]}, json={"scan_type": "EXIT", "qr_token": ticket["qr_token"]})
    assert exit_response.status_code == 200
    duplicate_exit = client.post(endpoint, headers={"X-Scanner-Key": scanner["api_key"]}, json={"scan_type": "EXIT", "qr_token": ticket["qr_token"]})
    assert duplicate_exit.status_code == 409
    assert client.get("/api/availability", headers=owner_headers).json()[0]["occupied_spaces"] == 0
    assert client.get(f"/api/operations/gates/{gate['id']}/scanners", headers=admin_headers).json()[0]["last_seen_at"]

    revoked = client.post(f"/api/operations/scanners/{scanner['id']}/revoke", headers=admin_headers)
    assert revoked.status_code == 200
    assert client.post(endpoint, headers={"X-Scanner-Key": scanner["api_key"]}, json={"scan_type": "ENTRY", "vehicle_registration": vehicle["registration_number"]}).status_code == 401
    regenerated = client.post(f"/api/operations/scanners/{scanner['id']}/regenerate", headers=admin_headers)
    assert regenerated.status_code == 200
    assert regenerated.json()["api_key"] != scanner["api_key"]
    assert "api_key" not in client.get(f"/api/operations/gates/{gate['id']}/scanners", headers=admin_headers).json()[0]
    assert client.get("/api/reports/scanner-summary", headers=admin_headers).status_code == 200
    workbook = client.get("/api/reports/export-xlsx", headers=admin_headers)
    assert workbook.status_code == 200
    assert workbook.content[:2] == b"PK"
