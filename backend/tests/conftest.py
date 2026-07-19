"""
Shared test fixtures. Every local-mode JSON file used by the services is
redirected into a per-test tmp_path, so tests never read/write the project's
real ./local_storage data. Gmail sending is stubbed out entirely — no real
API calls, no real credentials needed to run these tests.
"""
import pytest
from fastapi.testclient import TestClient

from app.services import (
    admin_service, users_service, login_security_service,
    password_reset_service, job_postings_service, usage_service,
    mongodb_service, settings_service, gmail_service,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(admin_service, "LOCAL_ADMIN_FILE", str(tmp_path / "admin.json"))
    monkeypatch.setattr(users_service, "LOCAL_USERS_FILE", str(tmp_path / "users.json"))
    monkeypatch.setattr(login_security_service, "LOCAL_ATTEMPTS_FILE", str(tmp_path / "login_attempts.json"))
    monkeypatch.setattr(password_reset_service, "LOCAL_RESETS_FILE", str(tmp_path / "password_resets.json"))
    monkeypatch.setattr(job_postings_service, "LOCAL_JOBS_FILE", str(tmp_path / "job_postings.json"))
    monkeypatch.setattr(usage_service, "LOCAL_USAGE_FILE", str(tmp_path / "usage.json"))
    monkeypatch.setattr(mongodb_service, "LOCAL_TRACKING_FILE", str(tmp_path / "tracking.json"))
    monkeypatch.setattr(settings_service, "LOCAL_SETTINGS_FILE", str(tmp_path / "settings.json"))

    # Never actually send email in tests.
    monkeypatch.setattr(gmail_service, "send_email", lambda **kwargs: None)

    from app.main import app
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})
    return res.json()["access_token"]


def signup_and_login(client, username, email, password):
    res = client.post("/api/auth/signup", json={"username": username, "email": email, "password": password})
    return res.json()["access_token"]


@pytest.fixture
def recruiter_token(client):
    return signup_and_login(client, "recruiter_test", "recruiter_test@example.com", "password123")
