from backend.app.models import UserRole
from .helpers import create_user, headers_for


def test_signup_without_verification_and_duplicate_email(client):
    data = {"full_name": "New User", "email": "new.user@example.com", "password": "StrongPassword!123"}
    assert client.post('/api/auth/register', json=data).status_code == 201
    duplicate = {**data, "email": "NEW.USER@example.com"}
    assert client.post('/api/auth/register', json=duplicate).status_code == 409
    assert client.post('/api/auth/login', data={"username": data['email'], "password": data['password']}).status_code == 200


def test_only_designated_admin(client, db_session):
    designated = create_user(db_session, email='dhruvjain1223@gmail.com', role=UserRole.ADMIN, password='12345678')
    other = create_user(db_session, email='other.admin@example.com', role=UserRole.ADMIN)
    assert client.post('/api/auth/login', data={"username": designated.email, "password": "12345678"}).status_code == 200
    assert client.post('/api/auth/login', data={"username": other.email, "password": "StrongPassword!123"}).status_code == 403
    assert client.get('/api/auth/me', headers=headers_for(other)).status_code == 403
    assert client.post('/api/auth/register', json={"full_name": "Admin", "email": designated.email, "password": "StrongPassword!123"}).status_code == 409


def test_demo_access_disabled(client):
    assert client.post('/api/auth/demo-session', json={"role": "ADMIN"}).status_code == 404
