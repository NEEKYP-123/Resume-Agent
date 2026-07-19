"""
Tests for role-based access control: job postings, user management,
per-recruiter note privacy, and Gemini usage visibility.
"""
from app.services import mongodb_service


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Job postings ----

def test_recruiter_cannot_create_job(client, recruiter_token):
    res = client.post("/api/jobs", json={"title": "Sneaky Job"}, headers=auth_header(recruiter_token))
    assert res.status_code == 403


def test_admin_can_create_job(client, admin_token):
    res = client.post(
        "/api/jobs", json={"title": "Backend Engineer", "description": "Python"}, headers=auth_header(admin_token)
    )
    assert res.status_code == 200
    assert res.json()["status"] == "open"


def test_both_roles_can_list_jobs(client, admin_token, recruiter_token):
    client.post("/api/jobs", json={"title": "Backend Engineer"}, headers=auth_header(admin_token))

    res = client.get("/api/jobs", headers=auth_header(recruiter_token))
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_recruiter_cannot_close_job(client, admin_token, recruiter_token):
    job = client.post("/api/jobs", json={"title": "Backend Engineer"}, headers=auth_header(admin_token)).json()
    res = client.post(f"/api/jobs/{job['id']}/close", headers=auth_header(recruiter_token))
    assert res.status_code == 403


def test_admin_can_close_job(client, admin_token):
    job = client.post("/api/jobs", json={"title": "Backend Engineer"}, headers=auth_header(admin_token)).json()
    res = client.post(f"/api/jobs/{job['id']}/close", headers=auth_header(admin_token))
    assert res.status_code == 200
    assert res.json()["status"] == "closed"


# ---- User management ----

def test_recruiter_cannot_list_users(client, recruiter_token):
    res = client.get("/api/users", headers=auth_header(recruiter_token))
    assert res.status_code == 403


def test_admin_can_list_users(client, admin_token, recruiter_token):
    res = client.get("/api/users", headers=auth_header(admin_token))
    assert res.status_code == 200
    usernames = [u["username"] for u in res.json()]
    assert "recruiter_test" in usernames
    # password hash must never be exposed
    assert all("password_hash" not in u for u in res.json())


def test_admin_can_promote_recruiter_and_it_takes_effect_immediately(client, admin_token, recruiter_token):
    res = client.post(
        "/api/users/recruiter_test/role", json={"role": "admin"}, headers=auth_header(admin_token)
    )
    assert res.status_code == 200

    # Same token, no re-login — role should already reflect the promotion.
    res = client.get("/api/auth/verify", headers=auth_header(recruiter_token))
    assert res.json()["role"] == "admin"


def test_admin_cannot_remove_own_account(client, admin_token):
    res = client.delete("/api/users/admin", headers=auth_header(admin_token))
    assert res.status_code == 400


def test_admin_can_remove_recruiter(client, admin_token, recruiter_token):
    res = client.delete("/api/users/recruiter_test", headers=auth_header(admin_token))
    assert res.status_code == 200

    res = client.post("/api/auth/login", json={"username": "recruiter_test", "password": "password123"})
    assert res.status_code == 401


# ---- Notes visibility ----

def _create_resume_record():
    return mongodb_service.create_entry(
        sender="candidate@example.com", subject="Application", b2_key="fake/key.pdf", filename="resume.pdf",
    )


def test_recruiter_only_sees_own_notes(client, admin_token, recruiter_token):
    record = _create_resume_record()

    other_token = client.post(
        "/api/auth/signup",
        json={"username": "recruiter_two", "email": "recruiter_two@example.com", "password": "password123"},
    ).json()["access_token"]

    client.post(f"/api/resumes/{record['id']}/notes", json={"text": "Alice's note"}, headers=auth_header(recruiter_token))
    client.post(f"/api/resumes/{record['id']}/notes", json={"text": "Bob's note"}, headers=auth_header(other_token))

    alice_view = client.get("/api/resumes", headers=auth_header(recruiter_token)).json()
    alice_notes = alice_view[0]["notes"]
    assert len(alice_notes) == 1
    assert alice_notes[0]["text"] == "Alice's note"

    bob_view = client.get("/api/resumes", headers=auth_header(other_token)).json()
    bob_notes = bob_view[0]["notes"]
    assert len(bob_notes) == 1
    assert bob_notes[0]["text"] == "Bob's note"


def test_admin_sees_every_recruiters_notes(client, admin_token, recruiter_token):
    record = _create_resume_record()
    client.post(f"/api/resumes/{record['id']}/notes", json={"text": "Alice's note"}, headers=auth_header(recruiter_token))

    admin_view = client.get("/api/resumes", headers=auth_header(admin_token)).json()
    assert len(admin_view[0]["notes"]) == 1
    assert admin_view[0]["notes"][0]["text"] == "Alice's note"


# ---- Gemini usage ----

def test_recruiter_cannot_view_usage(client, recruiter_token):
    res = client.get("/api/usage", headers=auth_header(recruiter_token))
    assert res.status_code == 403


def test_admin_can_view_usage(client, admin_token):
    res = client.get("/api/usage", headers=auth_header(admin_token))
    assert res.status_code == 200
    assert res.json()["call_count"] == 0
