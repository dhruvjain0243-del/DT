from backend.app.core.security import decode_token, hash_password, verify_password
from backend.app.models import UserRole

from .helpers import create_user, headers_for


VALID_USER = {
    "full_name": "Student One",
    "email": "student@example.com",
    "college_id": "COL001",
    "phone": "9999999999",
    "password": "StrongPassword!123",
    "role": "STUDENT",
}


def test_user_registration_hashes_password(client, db_session):
    response = client.post("/api/auth/register", json=VALID_USER)
    assert response.status_code == 201
    assert "password" not in response.json()
    from backend.app.models import User

    user = db_session.get(User, response.json()["id"])
    assert user.password_hash != VALID_USER["password"]
    assert verify_password(VALID_USER["password"], user.password_hash)


def test_password_hashing_round_trip():
    hashed = hash_password("StrongPassword!123")
    assert hashed.startswith("$argon2")
    assert verify_password("StrongPassword!123", hashed)
    assert not verify_password("incorrect", hashed)


def test_login_and_jwt_claims(client):
    client.post("/api/auth/register", json=VALID_USER)
    response = client.post(
        "/api/auth/login",
        data={"username": VALID_USER["email"], "password": VALID_USER["password"]},
    )
    assert response.status_code == 200
    body = response.json()
    payload = decode_token(body["access_token"], "access")
    assert payload["role"] == "STUDENT"
    assert "exp" in payload and "sub" in payload


def test_invalid_login(client):
    response = client.post(
        "/api/auth/login",
        data={"username": "missing@example.com", "password": "WrongPassword!123"},
    )
    assert response.status_code == 401


def test_invalid_jwt_is_rejected(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer broken.token.value"})
    assert response.status_code == 401


def test_role_based_authorization(client, db_session):
    student = create_user(db_session, email="role@example.com", role=UserRole.STUDENT)
    response = client.post(
        "/api/facilities",
        headers=headers_for(student),
        json={"name": "Forbidden", "address": "No Access Road", "total_capacity": 10},
    )
    assert response.status_code == 403


def test_api_validation_errors_are_safe(client):
    response = client.post(
        "/api/auth/register",
        json={**VALID_USER, "email": "not-an-email", "password": "weak"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
