from sqlalchemy import func, select

from backend.app.cli.seed import seed
from backend.app.models import (
    Facility,
    Feedback,
    ParkingSession,
    ParkingSlot,
    ParkingZone,
    Prediction,
    User,
    UserRole,
    Vehicle,
)


def test_demo_seed_is_complete_and_idempotent(db_session):
    users, passwords, facility = seed(db_session)
    db_session.commit()

    assert set(user.role for user in users.values()) == set(UserRole)
    assert len(passwords) == 5
    assert facility.total_capacity == 100
    assert sum(zone.capacity for zone in facility.zones) == 100
    assert all(zone.vehicle_type.value == "MOTORCYCLE" for zone in facility.zones)
    assert db_session.scalar(select(func.count(ParkingSlot.id))) == 100
    assert db_session.scalar(select(func.count(Vehicle.id))) == 3
    assert db_session.scalar(select(func.count(ParkingSession.id))) == 3
    assert db_session.scalar(select(func.count(Prediction.id))) == 1
    assert db_session.scalar(select(func.count(Feedback.id))) == 1
    assert all(slot.qr_code_value for zone in facility.zones for slot in zone.slots)

    second_users, second_passwords, second_facility = seed(db_session)
    db_session.commit()
    assert second_passwords == {}
    assert second_facility.id == facility.id
    assert set(second_users) == set(users)
    assert db_session.scalar(select(func.count(User.id))) == 5
    assert db_session.scalar(select(func.count(Facility.id))) == 1
    assert db_session.scalar(select(func.count(ParkingZone.id))) == 2
    assert db_session.scalar(select(func.count(ParkingSlot.id))) == 100
    assert db_session.scalar(select(func.count(Vehicle.id))) == 3
    assert db_session.scalar(select(func.count(ParkingSession.id))) == 3
    assert db_session.scalar(select(func.count(Prediction.id))) == 1
    assert db_session.scalar(select(func.count(Feedback.id))) == 1


def test_seeded_accounts_can_authenticate_every_role(client, db_session):
    _, passwords, _ = seed(db_session)
    db_session.commit()
    for email, password in passwords.items():
        response = client.post(
            "/api/auth/login",
            data={"username": email, "password": password},
        )
        assert response.status_code == 200
        assert response.json()["user"]["email"] == email
