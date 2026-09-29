from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import create_token_pair, hash_password
from backend.app.models import User, UserRole


def create_user(
    db: Session,
    *,
    email: str,
    role: UserRole = UserRole.STUDENT,
    password: str = "StrongPassword!123",
) -> User:
    user = User(
        full_name=email.split("@")[0].title(),
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def headers_for(user: User) -> dict[str, str]:
    token = create_token_pair(user.id, user.role.value).access_token
    return {"Authorization": f"Bearer {token}"}


def seed_parking_api(
    client: TestClient,
    admin_headers: dict[str, str],
    *,
    capacity: int = 2,
) -> tuple[dict, dict, list[dict]]:
    facility = client.post(
        "/api/facilities",
        headers=admin_headers,
        json={
            "name": "Test Facility",
            "address": "1 Test Avenue",
            "total_capacity": capacity,
            "distance_km": 1,
            "price_per_hour": 20,
        },
    ).json()
    zone = client.post(
        f"/api/facilities/{facility['id']}/zones",
        headers=admin_headers,
        json={"name": "Zone A", "vehicle_type": "CAR", "capacity": capacity},
    ).json()
    slots = []
    for index in range(capacity):
        response = client.post(
            f"/api/zones/{zone['id']}/slots",
            headers=admin_headers,
            json={"slot_code": f"A-{index + 1}", "row_label": "A"},
        )
        assert response.status_code == 201
        slots.append(response.json())
    return facility, zone, slots
