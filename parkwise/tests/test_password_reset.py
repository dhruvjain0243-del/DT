import re
from urllib.parse import parse_qs, urlsplit
from backend.app.routers import auth
from .helpers import create_user


def test_reset_email_single_use_and_password_change(client, db_session, monkeypatch):
    user = create_user(db_session, email="reset.user@example.com")
    settings = auth.get_settings().model_copy(update={"email_smtp_host": "smtp.example.com", "email_smtp_username": "sender", "email_smtp_password": "secret", "email_from": "sender@example.com"})
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    sent = []
    class Mail:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def starttls(self): pass
        def login(self, *args): pass
        def send_message(self, message): sent.append(message)
    monkeypatch.setattr(auth.smtplib, "SMTP", Mail)
    response = client.post("/api/auth/forgot-password", json={"email": user.email})
    assert response.status_code == 200
    unknown = client.post("/api/auth/forgot-password", json={"email": "missing@example.com"})
    assert unknown.json() == response.json()
    assert len(sent) == 1
    link = re.search(r"http[^\s]+", sent[0].get_content()).group()
    token = parse_qs(urlsplit(link).fragment)["token"][0]
    body = {"token": token, "password": "NewPassword!456"}
    assert client.post("/api/auth/reset-password", json={**body, "token": "x" * 30}).status_code == 400
    assert client.post("/api/auth/reset-password", json=body).status_code == 200
    assert client.post("/api/auth/reset-password", json=body).status_code == 400
    assert client.post("/api/auth/login", data={"username": user.email, "password": "StrongPassword!123"}).status_code == 401
    assert client.post("/api/auth/login", data={"username": user.email, "password": "NewPassword!456"}).status_code == 200
