"""
FastAPI endpoint integration tests.

Uses TestClient with an in-memory SQLite database (wired up via conftest.py).
External services (Anthropic, Twilio, Stripe, email) are mocked where needed.
"""
from unittest.mock import patch


# ── Health / root ─────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "MediScan" in r.json()["message"]


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_login_success(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "mediscan2026"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["role"] == "admin"


def test_login_wrong_password(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


def test_login_nurse(client):
    r = client.post("/auth/login", json={"username": "nurse", "password": "nurse2026"})
    assert r.status_code == 200
    assert r.json()["role"] == "nurse"


def test_login_physician(client):
    r = client.post("/auth/login", json={"username": "physician", "password": "physician2026"})
    assert r.status_code == 200


def test_auth_me(client, auth_headers):
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"


def test_auth_me_unauthorized(client):
    r = client.get("/auth/me")
    assert r.status_code in (401, 403)


def test_auth_me_bad_token(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert r.status_code == 401


def test_auth_refresh(client, auth_headers):
    r = client.post("/auth/refresh", headers=auth_headers)
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_fhir_status(client, auth_headers):
    r = client.get("/auth/fhir_status", headers=auth_headers)
    assert r.status_code == 200
    assert "fhir_available" in r.json()


# ── MFA ───────────────────────────────────────────────────────────────────────

def test_mfa_setup(client, auth_headers):
    r = client.get("/auth/mfa/setup", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "secret" in data
    assert "qr_code_base64" in data
    assert "backup_codes" in data


def test_mfa_disable_missing_user(client, auth_headers):
    r = client.post("/auth/mfa/disable", headers=auth_headers, params={"username": "doesnotexist"})
    assert r.status_code == 404


def test_mfa_disable_existing_user(client, auth_headers):
    r = client.post("/auth/mfa/disable", headers=auth_headers, params={"username": "admin"})
    assert r.status_code == 200
    assert r.json()["mfa_disabled"] is True


def test_mfa_enable_invalid_code(client, auth_headers):
    r = client.post("/auth/mfa/enable", headers=auth_headers, params={"code": "000000"})
    assert r.status_code == 400


# ── Queue ─────────────────────────────────────────────────────────────────────

def test_get_queue_empty(client, auth_headers):
    r = client.get("/queue", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_queue_unauthorized(client):
    r = client.get("/queue")
    assert r.status_code in (401, 403)


def test_discharge_nonexistent_patient(client, auth_headers):
    r = client.delete("/queue/FAKE-999", headers=auth_headers)
    assert r.status_code == 404


def test_clear_queue(client, auth_headers):
    r = client.delete("/queue", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["cleared"] is True


def test_clear_queue_forbidden_for_nurse(client, nurse_headers):
    r = client.delete("/queue", headers=nurse_headers)
    assert r.status_code == 403


# ── Analytics & Stats ─────────────────────────────────────────────────────────

def test_get_analytics(client, auth_headers):
    r = client.get("/analytics", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "queue" in data
    assert "capacity" in data
    assert "timeseries" in data
    assert "benchmarks" in data


def test_public_stats(client):
    r = client.get("/stats")
    assert r.status_code == 200
    data = r.json()
    assert "patients_triaged" in data
    assert "ai_accuracy_pct" in data


# ── Beds ──────────────────────────────────────────────────────────────────────

def test_list_beds_requires_auth(client):
    r = client.get("/beds")
    assert r.status_code in (401, 403)


def test_list_beds(client, auth_headers, db_session):
    from database import Bed
    # Seed a bed for this test
    b = Bed(unit="ED Main", room="TEST-1")
    db_session.add(b)
    db_session.commit()

    r = client.get("/beds", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_update_bed_status(client, auth_headers, db_session):
    from database import Bed
    b = Bed(unit="ED Main", room="TEST-BED-2")
    db_session.add(b)
    db_session.commit()

    r = client.put(
        "/beds/TEST-BED-2",
        headers=auth_headers,
        json={"status": "occupied", "patient_id": None},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "occupied"


def test_update_bed_invalid_status(client, auth_headers, db_session):
    from database import Bed
    b = Bed(unit="ED Main", room="TEST-BED-3")
    db_session.add(b)
    db_session.commit()

    r = client.put(
        "/beds/TEST-BED-3",
        headers=auth_headers,
        json={"status": "broken"},
    )
    assert r.status_code == 400


def test_update_bed_not_found(client, auth_headers):
    r = client.put(
        "/beds/NO-SUCH-ROOM",
        headers=auth_headers,
        json={"status": "available"},
    )
    assert r.status_code == 404


def test_update_bed_cleaning_status(client, auth_headers, db_session):
    from database import Bed
    b = Bed(unit="Fast Track", room="TEST-CLEAN-1")
    db_session.add(b)
    db_session.commit()

    r = client.put(
        "/beds/TEST-CLEAN-1",
        headers=auth_headers,
        json={"status": "cleaning"},
    )
    assert r.status_code == 200


# ── Compliance ────────────────────────────────────────────────────────────────

def test_compliance_status(client, auth_headers):
    r = client.get("/compliance/status", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "hipaa_controls" in data
    assert "compliance_score_pct" in data


def test_compliance_baa_pdf(client, auth_headers):
    r = client.get("/compliance/baa", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_compliance_escalation_rules(client, auth_headers):
    r = client.get("/compliance/escalation-rules", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_compliance_patch_rule_not_found(client, auth_headers):
    r = client.patch(
        "/compliance/escalation-rules/nonexistent-id",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert r.status_code == 404


# ── Hospitals ────────────────────────────────────────────────────────────────

def test_list_hospitals(client, auth_headers):
    r = client.get("/hospitals", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_hospital(client, auth_headers):
    r = client.post("/hospitals", headers=auth_headers, json={
        "slug": "test-hospital-ci",
        "name": "CI Test Hospital",
        "city": "Springfield",
        "state": "IL",
    })
    assert r.status_code == 200
    assert r.json()["slug"] == "test-hospital-ci"


def test_create_hospital_duplicate_slug(client, auth_headers):
    client.post("/hospitals", headers=auth_headers, json={
        "slug": "dupe-slug",
        "name": "First",
    })
    r = client.post("/hospitals", headers=auth_headers, json={
        "slug": "dupe-slug",
        "name": "Second",
    })
    assert r.status_code == 400


def test_list_hospitals_forbidden_for_nurse(client, nurse_headers):
    r = client.get("/hospitals", headers=nurse_headers)
    assert r.status_code == 403


# ── Demo Request ──────────────────────────────────────────────────────────────

def test_demo_request(client):
    with patch("email_service.send_email", return_value=True):
        r = client.post("/demo-request", json={
            "name": "Dr. Test",
            "hospital": "Test Medical",
            "role": "CIO",
            "email": "test@example.com",
            "bed_count": 200,
        })
    assert r.status_code == 200
    assert r.json()["success"] is True


# ── Demo Patients ─────────────────────────────────────────────────────────────

def test_demo_patients_count(client):
    r = client.get("/demo/patients")
    assert r.status_code == 200
    assert "count" in r.json()
    assert r.json()["count"] > 0


# ── Audit Log ────────────────────────────────────────────────────────────────

def test_get_audit(client, auth_headers):
    r = client.get("/audit", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_audit_forbidden_for_nurse(client, nurse_headers):
    r = client.get("/audit", headers=nurse_headers)
    assert r.status_code == 403


# ── Shift Report ──────────────────────────────────────────────────────────────

def test_list_reports(client, auth_headers):
    r = client.get("/report", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_generate_report_json(client, auth_headers):
    r = client.post("/report", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "total_patients" in data
    assert "esi_breakdown" in data


def test_generate_report_pdf(client, auth_headers):
    with patch("pdf_report.generate_shift_pdf", return_value=b"%PDF-1.4 test"):
        r = client.post("/report", headers=auth_headers, params={"format": "pdf"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


# ── Admin Users ───────────────────────────────────────────────────────────────

def test_list_admin_users(client, auth_headers):
    r = client.get("/admin/users", headers=auth_headers)
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list)
    usernames = [u["username"] for u in users]
    assert "admin" in usernames


def test_list_admin_users_forbidden_for_nurse(client, nurse_headers):
    r = client.get("/admin/users", headers=nurse_headers)
    assert r.status_code == 403


def test_create_staff_user(client, auth_headers):
    r = client.post("/admin/users", headers=auth_headers, json={
        "username": "teststaff01",
        "password": "staffpass123",
        "role": "nurse",
        "name": "Test Nurse",
        "email": "testnurse@example.com",
    })
    assert r.status_code == 200
    assert r.json()["created"] is True


def test_create_staff_duplicate_username(client, auth_headers):
    client.post("/admin/users", headers=auth_headers, json={
        "username": "dupuser",
        "password": "pass1234",
        "role": "nurse",
        "name": "Dup",
    })
    r = client.post("/admin/users", headers=auth_headers, json={
        "username": "dupuser",
        "password": "pass1234",
        "role": "nurse",
        "name": "Dup",
    })
    assert r.status_code == 409


def test_create_staff_invalid_role(client, auth_headers):
    r = client.post("/admin/users", headers=auth_headers, json={
        "username": "badroleuser",
        "password": "pass1234",
        "role": "superadmin",
        "name": "Bad",
    })
    assert r.status_code == 400


def test_update_staff_user(client, auth_headers):
    client.post("/admin/users", headers=auth_headers, json={
        "username": "updateme",
        "password": "pass1234",
        "role": "nurse",
        "name": "To Update",
    })
    r = client.patch("/admin/users/updateme", headers=auth_headers, json={"name": "Updated Name"})
    assert r.status_code == 200
    assert r.json()["updated"] is True


def test_update_staff_not_found(client, auth_headers):
    r = client.patch("/admin/users/nope", headers=auth_headers, json={"name": "x"})
    assert r.status_code == 404


def test_reset_staff_password(client, auth_headers):
    client.post("/admin/users", headers=auth_headers, json={
        "username": "resetme",
        "password": "oldpass1",
        "role": "nurse",
        "name": "Reset User",
    })
    r = client.post(
        "/admin/users/resetme/reset-password",
        headers=auth_headers,
        json={"new_password": "newpass999"},
    )
    assert r.status_code == 200
    assert r.json()["reset"] is True


def test_reset_password_too_short(client, auth_headers):
    client.post("/admin/users", headers=auth_headers, json={
        "username": "resetme2",
        "password": "oldpass1",
        "role": "nurse",
        "name": "Short",
    })
    r = client.post(
        "/admin/users/resetme2/reset-password",
        headers=auth_headers,
        json={"new_password": "abc"},
    )
    assert r.status_code == 400


def test_reset_password_user_not_found(client, auth_headers):
    r = client.post(
        "/admin/users/nosuchuser/reset-password",
        headers=auth_headers,
        json={"new_password": "newpass999"},
    )
    assert r.status_code == 404


# ── CareNavigator assess ──────────────────────────────────────────────────────

def test_assess_missing_symptoms(client):
    r = client.post("/check/assess", json={
        "age": 30,
        "sex": "female",
        "symptoms": "ok",  # too short (< 5 chars stripped)
    })
    # "ok" has 2 chars after strip, should fail validation
    # Actually "ok" is 2 chars < 5 — should get 400
    assert r.status_code in (400, 422)


def test_assess_invalid_age(client):
    r = client.post("/check/assess", json={
        "age": -1,
        "sex": "male",
        "symptoms": "chest pain and shortness of breath",
    })
    assert r.status_code == 400


def test_assess_invalid_age_too_high(client):
    r = client.post("/check/assess", json={
        "age": 150,
        "sex": "male",
        "symptoms": "chest pain and shortness of breath",
    })
    assert r.status_code == 400


def test_assess_valid(client):
    mock_result = {
        "care_level": "URGENT_CARE",
        "urgency": "moderate",
        "reasoning": "mock reasoning",
        "follow_up_questions": [],
        "red_flags": [],
        "care_instructions": [],
    }
    with patch("main.run_assessment", return_value=mock_result):
        r = client.post("/check/assess", json={
            "age": 35,
            "sex": "male",
            "symptoms": "mild headache and fatigue since yesterday",
        })
    assert r.status_code == 200
    assert r.json()["care_level"] == "URGENT_CARE"


# ── Pre-register ──────────────────────────────────────────────────────────────

def test_pre_register(client):
    r = client.post("/check/pre-register", json={
        "name": "Jane Doe",
        "age": 40,
        "sex": "female",
        "symptoms": "chest pain",
        "care_level": "ED_NOW",
        "phone": "+13125550001",
    })
    assert r.status_code == 200
    data = r.json()
    assert "patient_id" in data
    assert data["patient_id"].startswith("PRE-")


# ── Scheduling ────────────────────────────────────────────────────────────────

def test_get_slots(client):
    r = client.get("/check/slots", params={"care_type": "urgent_care"})
    assert r.status_code == 200
    data = r.json()
    assert "slots" in data
    assert "care_type" in data


def test_get_slots_invalid_type(client):
    r = client.get("/check/slots", params={"care_type": "emergency"})
    assert r.status_code == 400


# ── Chart notes ───────────────────────────────────────────────────────────────

def test_get_chart_note_not_found(client, auth_headers):
    r = client.get("/chart/note/NOPAT-999", headers=auth_headers)
    assert r.status_code == 404


def test_patch_chart_note_not_found(client, auth_headers):
    r = client.patch(
        "/chart/note/NOPAT-PATCH",
        headers=auth_headers,
        json={"subjective": "Patient reports..."},
    )
    assert r.status_code == 404


# ── Patient portal ────────────────────────────────────────────────────────────

def test_patient_portal_not_found(client):
    r = client.get("/patient/portal/invalid-token-xyz")
    assert r.status_code == 404


def test_patient_portal_respond_not_found(client):
    r = client.post(
        "/patient/portal/invalid-token-xyz/respond",
        json={"response": "Feeling better"},
    )
    assert r.status_code == 404


def test_patient_portal_valid(client, db_session):
    from database import ClinicalJourney as CJModel
    from datetime import datetime
    import uuid

    token = str(uuid.uuid4())
    cj = CJModel(
        patient_id="PT-PORTAL-TEST",
        name="Portal Patient",
        esi_level=3,
        portal_token=token,
        discharge_at=datetime.utcnow(),
    )
    db_session.add(cj)
    db_session.commit()

    r = client.get(f"/patient/portal/{token}")
    assert r.status_code == 200
    assert r.json()["name"] == "Portal Patient"


# ── Journeys ─────────────────────────────────────────────────────────────────

def test_list_journeys(client, auth_headers):
    r = client.get("/journeys", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_journeys_for_patient_not_found(client, auth_headers):
    r = client.get("/journeys/patient/NOPAT", headers=auth_headers)
    assert r.status_code == 404


def test_journey_checkin_returns_result(client, auth_headers):
    # manual_checkin with a non-existent journey returns a result (not 404)
    r = client.post("/journeys/fake-journey-id/checkin", headers=auth_headers)
    assert r.status_code == 200


def test_journey_resolve_not_found(client, auth_headers):
    r = client.post("/journeys/fake-journey-id/resolve", headers=auth_headers)
    assert r.status_code == 404


# ── Discharge via /queue/{id}/discharge ──────────────────────────────────────

def test_discharge_queue_endpoint_not_found(client, auth_headers):
    r = client.delete("/queue/FAKEPAT/discharge", headers=auth_headers)
    assert r.status_code == 404


# ── Security headers ──────────────────────────────────────────────────────────

def test_security_headers_present(client):
    r = client.get("/health")
    assert "x-content-type-options" in r.headers
    assert "x-frame-options" in r.headers
