"""
Tests for login, signup, session verification, lockout, and password reset.
"""
from app.services import password_reset_service


def test_login_success(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect username or password"


def test_login_lockout_after_repeated_failures(client):
    for _ in range(5):
        res = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert res.status_code == 401

    # 6th attempt — even with the CORRECT password — should be locked out.
    res = client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})
    assert res.status_code == 429
    assert "Too many failed attempts" in res.json()["detail"]


def test_lockout_applies_even_to_nonexistent_usernames(client):
    """Lockout timing must not reveal whether a username exists."""
    for _ in range(5):
        res = client.post("/api/auth/login", json={"username": "totally-fake-user", "password": "wrong"})
        assert res.status_code == 401

    res = client.post("/api/auth/login", json={"username": "totally-fake-user", "password": "wrong"})
    assert res.status_code == 429


def test_verify_with_valid_token(client, admin_token):
    res = client.get("/api/auth/verify", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json() == {"username": "admin", "role": "admin"}


def test_verify_without_token(client):
    res = client.get("/api/auth/verify")
    assert res.status_code in (401, 403)  # missing bearer credentials


def test_verify_with_garbage_token(client):
    res = client.get("/api/auth/verify", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


def test_signup_success(client):
    res = client.post("/api/auth/signup", json={
        "username": "newrecruiter", "email": "newrecruiter@example.com", "password": "password123",
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_signup_default_role_is_recruiter(client, recruiter_token):
    res = client.get("/api/auth/verify", headers={"Authorization": f"Bearer {recruiter_token}"})
    assert res.json()["role"] == "recruiter"


def test_signup_duplicate_username_rejected(client):
    client.post("/api/auth/signup", json={"username": "dupe", "email": "a@x.com", "password": "password123"})
    res = client.post("/api/auth/signup", json={"username": "dupe", "email": "b@x.com", "password": "password123"})
    assert res.status_code == 409


def test_signup_cannot_use_admin_username(client):
    res = client.post("/api/auth/signup", json={"username": "admin", "email": "a@x.com", "password": "password123"})
    assert res.status_code == 409


def test_signup_rejects_short_password(client):
    res = client.post("/api/auth/signup", json={"username": "shortpw", "email": "a@x.com", "password": "abc"})
    assert res.status_code == 400


def test_forgot_password_unknown_email_returns_generic_message(client):
    res = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert res.status_code == 200
    assert "If that email exists" in res.json()["message"]


def test_forgot_password_admin_email_and_reset(client):
    res = client.post("/api/auth/forgot-password", json={"email": "palaneek174@gmail.com"})
    assert res.status_code == 200

    # Generate a token directly (send_email is stubbed, so we can't read it from an inbox).
    token = password_reset_service.create_reset_token("admin", "admin")
    res = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewAdminPass123"})
    assert res.status_code == 200

    # New password works, old one doesn't.
    res = client.post("/api/auth/login", json={"username": "admin", "password": "NewAdminPass123"})
    assert res.status_code == 200
    res = client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})
    assert res.status_code == 401


def test_reset_token_is_single_use(client):
    token = password_reset_service.create_reset_token("admin", "admin")
    res = client.post("/api/auth/reset-password", json={"token": token, "new_password": "First123"})
    assert res.status_code == 200

    res = client.post("/api/auth/reset-password", json={"token": token, "new_password": "Second123"})
    assert res.status_code == 400


def test_reset_password_for_recruiter_does_not_affect_admin(client, recruiter_token):
    token = password_reset_service.create_reset_token("user", "recruiter_test")
    res = client.post("/api/auth/reset-password", json={"token": token, "new_password": "RecruiterNew123"})
    assert res.status_code == 200

    res = client.post("/api/auth/login", json={"username": "recruiter_test", "password": "RecruiterNew123"})
    assert res.status_code == 200

    # Admin's own password is untouched.
    res = client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})
    assert res.status_code == 200
