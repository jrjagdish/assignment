"""
tests/test_api.py

Five required pytest tests for SkillBridge API.

Tests 1, 2, 4, 5  → SQLite in-memory (fast, no network)
Tests 3, X        → real PostgreSQL (via real_client fixture)

Run all:               pytest
Run fast only:         pytest -k "not real_db"
Run real-DB only:      pytest -k real_db
"""

import pytest
from fastapi.testclient import TestClient


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _signup(client: TestClient, email: str, password: str, role: str, name: str = "Test User"):
    return client.post("/auth/signup", json={
        "name": name,
        "email": email,
        "password": password,
        "role": role,
    })


def _login(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def _auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


# ────────────────────────────────────────────────────────────────────────────
# Test 1 – Student signup and login returns a valid JWT
# (SQLite – fast)
# ────────────────────────────────────────────────────────────────────────────

def test_student_signup_and_login_returns_jwt(client: TestClient):
    """Signup then login; both must return a non-empty bearer token."""
    signup_res = _signup(client, "student_test@test.dev", "secret123", "student", "Alice")
    assert signup_res.status_code == 201, signup_res.text
    signup_data = signup_res.json()
    assert "access_token" in signup_data
    assert len(signup_data["access_token"]) > 20
    assert signup_data["token_type"] == "bearer"

    login_res = _login(client, "student_test@test.dev", "secret123")
    assert login_res.status_code == 200, login_res.text
    login_data = login_res.json()
    assert "access_token" in login_data
    assert len(login_data["access_token"]) > 20

    # Sanity: wrong password must fail
    bad_res = _login(client, "student_test@test.dev", "wrongpassword")
    assert bad_res.status_code == 401


# ────────────────────────────────────────────────────────────────────────────
# Test 2 – Trainer creates a session with all required fields
# (SQLite – fast)
# ────────────────────────────────────────────────────────────────────────────

def test_trainer_creates_session(client: TestClient):
    """Trainer signs up, creates a batch, then creates a session in that batch."""
    # Create a dummy institution row directly so FK succeeds in SQLite tests
    from src.database import get_db
    from src.models import Institution, Batch, BatchTrainer, RoleEnum

    # Use the overridden DB from the fixture
    with client as c:
        # sign up trainer
        t_res = _signup(c, "trainer1@test.dev", "train1234", "trainer", "Bob Trainer")
        assert t_res.status_code == 201, t_res.text
        t_token = t_res.json()["access_token"]
        headers = _auth_headers(t_token)

        # We need an institution + batch in the DB.
        # Inject via the DB directly (bypasses business-logic endpoints for isolation).
        db = next(c.app.dependency_overrides[get_db]())
        inst = Institution(name="Test Institute")
        db.add(inst)
        db.commit()
        db.refresh(inst)

        batch = Batch(name="Test Batch", institution_id=inst.id)
        db.add(batch)
        db.commit()
        db.refresh(batch)

        # Get the trainer's user id from their token
        import jose.jwt as jwt_lib
        import os
        secret = os.environ.get("SECRET_KEY", "changeme-in-production-use-env")
        payload = jwt_lib.decode(t_token, secret, algorithms=["HS256"])
        trainer_id = int(payload["sub"])

        db.add(BatchTrainer(batch_id=batch.id, trainer_id=trainer_id))
        db.commit()

        # Now create the session via API
        sess_res = c.post("/sessions", json={
            "title": "Intro to Python",
            "date": "2024-09-01",
            "start_time": "09:00:00",
            "end_time": "11:00:00",
            "batch_id": batch.id,
        }, headers=headers)
        assert sess_res.status_code == 201, sess_res.text
        body = sess_res.json()
        assert body["title"] == "Intro to Python"
        assert body["batch_id"] == batch.id
        assert body["trainer_id"] == trainer_id

        db.close()


# ────────────────────────────────────────────────────────────────────────────
# Test 3 – Student marks own attendance (real PostgreSQL)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.real_db
def test_student_marks_attendance_real_db(real_client: TestClient):
    """
    Full flow on real DB:
      signup student → signup trainer → create institution + batch → assign trainer →
      enroll student → create session → student marks attendance
    """
    import uuid
    tag = uuid.uuid4().hex[:6]

    # Signup trainer
    t_res = _signup(real_client, f"rt_{tag}@test.dev", "train1234", "trainer", "Real Trainer")
    assert t_res.status_code == 201, t_res.text
    t_token = t_res.json()["access_token"]
    t_headers = _auth_headers(t_token)

    # Signup student
    s_res = _signup(real_client, f"rs_{tag}@test.dev", "stud1234", "student", "Real Student")
    assert s_res.status_code == 201, s_res.text
    s_token = s_res.json()["access_token"]
    s_headers = _auth_headers(s_token)

    # Inject institution + batch + trainer assignment + student enrollment via DB
    from src.database import get_db
    from src.models import Institution, Batch, BatchTrainer, BatchStudent
    import jose.jwt as jwt_lib
    import os
    secret = os.environ.get("SECRET_KEY", "changeme-in-production-use-env")

    db = next(real_client.app.dependency_overrides[get_db]())

    inst = Institution(name=f"Real Inst {tag}")
    db.add(inst)
    db.commit()
    db.refresh(inst)

    batch = Batch(name=f"Real Batch {tag}", institution_id=inst.id)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    t_payload = jwt_lib.decode(t_token, secret, algorithms=["HS256"])
    s_payload = jwt_lib.decode(s_token, secret, algorithms=["HS256"])
    trainer_id = int(t_payload["sub"])
    student_id = int(s_payload["sub"])

    db.add(BatchTrainer(batch_id=batch.id, trainer_id=trainer_id))
    batch_id = batch.id
    db.add(BatchStudent(batch_id=batch.id, student_id=student_id))
    db.commit()
    db.close()

    # Trainer creates session
    sess_res = real_client.post("/sessions", json={
        "title": f"Session {tag}",
        "date": "2024-10-01",
        "start_time": "10:00:00",
        "end_time": "12:00:00",
        "batch_id": batch_id,
    }, headers=t_headers)
    assert sess_res.status_code == 201, sess_res.text
    session_id = sess_res.json()["id"]

    # Student marks attendance
    att_res = real_client.post("/attendance/mark", json={
        "session_id": session_id,
        "status": "present",
    }, headers=s_headers)
    assert att_res.status_code == 201, att_res.text
    att_body = att_res.json()
    assert att_body["status"] == "present"
    assert att_body["student_id"] == student_id


# ────────────────────────────────────────────────────────────────────────────
# Test 4 – POST to /monitoring/attendance returns 405
# (SQLite – fast)
# ────────────────────────────────────────────────────────────────────────────

def test_post_monitoring_attendance_returns_405(client: TestClient):
    """Any non-GET method on /monitoring/attendance must return 405."""
    # No auth token needed – method check happens before auth
    res = client.post("/monitoring/attendance", json={})
    assert res.status_code == 405, res.text

    res2 = client.delete("/monitoring/attendance")
    assert res2.status_code == 405, res2.text


# ────────────────────────────────────────────────────────────────────────────
# Test 5 – Protected endpoint with no token returns 401
# (SQLite – fast)
# ────────────────────────────────────────────────────────────────────────────

def test_protected_endpoint_without_token_returns_401(client: TestClient):
    """Calling any protected endpoint without a Bearer token must return 401."""
    endpoints = [
        ("POST", "/sessions", {"title": "x", "date": "2024-01-01",
                               "start_time": "09:00:00", "end_time": "10:00:00", "batch_id": 1}),
        ("POST", "/attendance/mark", {"session_id": 1, "status": "present"}),
        ("GET",  "/programme/summary", None),
        ("GET",  "/monitoring/attendance", None),
    ]
    for method, path, body in endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json=body)
        assert res.status_code == 401, f"{method} {path} should be 401, got {res.status_code}: {res.text}"


# ────────────────────────────────────────────────────────────────────────────
# Bonus Test – Real DB: duplicate signup returns 409
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.real_db
def test_duplicate_signup_returns_409(real_client: TestClient):
    """Signing up with the same email twice must return 409 Conflict."""
    import uuid
    email = f"dup_{uuid.uuid4().hex[:6]}@test.dev"
    r1 = _signup(real_client, email, "pass1234", "student", "Dup User")
    assert r1.status_code == 201
    r2 = _signup(real_client, email, "pass1234", "student", "Dup User")
    assert r2.status_code == 409


# ────────────────────────────────────────────────────────────────────────────
# Bonus Test – student cannot mark attendance for unenrolled session (403)
# ────────────────────────────────────────────────────────────────────────────

def test_student_unenrolled_gets_403(client: TestClient):
    """A student not enrolled in a batch must receive 403 when marking attendance."""
    from src.database import get_db
    from src.models import Institution, Batch, BatchTrainer

    # Sign up student (no batch enrollment)
    s_res = _signup(client, "unrolled@test.dev", "stud5678", "student", "Lonely Student")
    assert s_res.status_code == 201, s_res.text
    s_token = s_res.json()["access_token"]
    s_headers = _auth_headers(s_token)

    # Sign up trainer
    t_res = _signup(client, "trainer_unrolled@test.dev", "train5678", "trainer", "Solo Trainer")
    assert t_res.status_code == 201
    t_token = t_res.json()["access_token"]

    db = next(client.app.dependency_overrides[get_db]())
    inst = Institution(name="UnenrolledInst")
    db.add(inst)
    db.commit()
    db.refresh(inst)

    batch = Batch(name="UnenrolledBatch", institution_id=inst.id)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    import jose.jwt as jwt_lib
    import os
    secret = os.environ.get("SECRET_KEY", "changeme-in-production-use-env")
    t_payload = jwt_lib.decode(t_token, secret, algorithms=["HS256"])
    trainer_id = int(t_payload["sub"])
    db.add(BatchTrainer(batch_id=batch.id, trainer_id=trainer_id))
    db.commit()
    batch_id_val = batch.id
    db.close()

    # Trainer creates session
    t_headers = _auth_headers(t_token)
    sess_res = client.post("/sessions", json={
        "title": "Private Session",
        "date": "2024-11-01",
        "start_time": "10:00:00",
        "end_time": "12:00:00",
        "batch_id": batch_id_val,
    }, headers=t_headers)
    assert sess_res.status_code == 201, sess_res.text
    session_id = sess_res.json()["id"]

    # Student (not enrolled) tries to mark attendance → 403
    att_res = client.post("/attendance/mark", json={
        "session_id": session_id,
        "status": "present",
    }, headers=s_headers)
    assert att_res.status_code == 403, att_res.text
