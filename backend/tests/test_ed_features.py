"""
Tests for ED-specific features:
charge dashboard, clinical notes, shift summary, patient search,
staff assignment, staff list, demo login, FHIR status, patient satisfaction,
journeys feedback, LWBS, beds turnover, interpreter, medications.
"""
import uuid
from datetime import datetime


# ── Demo Login ────────────────────────────────────────────────────────────────

def test_demo_login(client):
    r = client.post("/auth/demo-login")
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["demo"] is True


# ── FHIR Status ───────────────────────────────────────────────────────────────

def test_fhir_integration_status(client, auth_headers):
    r = client.get("/fhir/status", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "fhir_available" in data
    assert "mode" in data


# ── Charge Dashboard ──────────────────────────────────────────────────────────

def test_charge_dashboard(client, auth_headers):
    r = client.get("/charge/dashboard", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "queue_depth" in data
    assert "bed_summary" in data
    assert "queue_by_esi" in data
    assert "longest_waits" in data
    assert "throughput_8h" in data


# ── Clinical Notes ────────────────────────────────────────────────────────────

def test_get_notes_empty(client, auth_headers):
    r = client.get("/queue/PT-NO-NOTES/notes", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_add_and_get_note(client, auth_headers):
    r = client.post("/queue/PT-NOTE-TEST/notes", headers=auth_headers, json={
        "note_text": "Patient reports mild pain 3/10",
        "note_type": "general",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["note_text"] == "Patient reports mild pain 3/10"
    assert "id" in data

    r2 = client.get("/queue/PT-NOTE-TEST/notes", headers=auth_headers)
    assert r2.status_code == 200
    notes = r2.json()
    assert len(notes) >= 1


def test_add_note_empty_text(client, auth_headers):
    r = client.post("/queue/PT-NOTE-TEST/notes", headers=auth_headers, json={
        "note_text": "   ",
        "note_type": "general",
    })
    assert r.status_code == 400


def test_delete_note(client, auth_headers):
    r = client.post("/queue/PT-DEL-NOTE/notes", headers=auth_headers, json={
        "note_text": "To be deleted",
        "note_type": "alert",
    })
    assert r.status_code == 200
    note_id = r.json()["id"]

    r2 = client.delete(f"/notes/{note_id}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["deleted"] == note_id


def test_delete_note_not_found(client, auth_headers):
    r = client.delete("/notes/nonexistent-note-id", headers=auth_headers)
    assert r.status_code == 404


# ── Shift Summary ─────────────────────────────────────────────────────────────

def test_shift_summary(client, auth_headers):
    r = client.get("/report/shift-summary", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "shift_start" in data
    assert "total_active" in data
    assert "esi_breakdown" in data
    assert "bed_utilization" in data


# ── Patient Search ────────────────────────────────────────────────────────────

def test_patient_search_empty(client, auth_headers):
    r = client.get("/patients/search", headers=auth_headers, params={"q": "ZZZnonexistentXXX"})
    assert r.status_code == 200
    assert r.json() == []


def test_patient_search_with_results(client, auth_headers, db_session):
    from database import PatientRecord
    db_session.add(PatientRecord(
        patient_id="PT-SEARCH-001",
        name="SearchablePatient Jones",
        age=45,
        chief_complaint="cough",
        esi_level=3,
        status="active",
        hospital_id="default",
    ))
    db_session.commit()

    r = client.get("/patients/search", headers=auth_headers, params={"q": "SearchablePatient"})
    assert r.status_code == 200
    results = r.json()
    names = [p["name"] for p in results]
    assert "SearchablePatient Jones" in names


def test_patient_search_include_discharged(client, auth_headers, db_session):
    from database import PatientRecord
    db_session.add(PatientRecord(
        patient_id="PT-DISC-SRCH-001",
        name="DischargedSearchable Smith",
        age=50,
        chief_complaint="headache",
        esi_level=4,
        status="discharged",
        hospital_id="default",
        discharged_at=datetime.utcnow(),
    ))
    db_session.commit()

    r = client.get("/patients/search", headers=auth_headers, params={
        "q": "DischargedSearchable",
        "include_discharged": "true",
    })
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "DischargedSearchable Smith" in names


# ── Staff Assignment ──────────────────────────────────────────────────────────

def test_assign_staff_not_in_queue(client, auth_headers):
    r = client.patch("/queue/NO-SUCH-PT/assign", headers=auth_headers, json={
        "assigned_nurse": "nurse1",
    })
    assert r.status_code == 404


# ── Staff List ────────────────────────────────────────────────────────────────

def test_staff_list(client, auth_headers):
    r = client.get("/staff/list", headers=auth_headers)
    assert r.status_code == 200
    staff = r.json()
    assert isinstance(staff, list)
    roles = [s["role"] for s in staff]
    assert "admin" in roles or "nurse" in roles


# ── Patient Satisfaction / Outcomes ──────────────────────────────────────────

def test_satisfaction_stats_empty(client, auth_headers):
    r = client.get("/outcomes/satisfaction", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "total_responses" in data


def test_journey_feedback_invalid_rating(client, auth_headers):
    r = client.post("/journeys/fake-id/feedback", headers=auth_headers, json={
        "rating": 6,
        "comment": "Great!",
    })
    assert r.status_code == 400


def test_journey_feedback_not_found(client, auth_headers):
    r = client.post("/journeys/nonexistent-journey/feedback", headers=auth_headers, json={
        "rating": 4,
        "comment": "Good",
    })
    assert r.status_code == 404


def test_journey_feedback_success(client, auth_headers, db_session):
    from database import ClinicalJourney as CJModel
    j = CJModel(
        id=str(uuid.uuid4()),
        patient_id="PT-FB-001",
        name="Feedback Patient",
        esi_level=3,
        portal_token=str(uuid.uuid4()),
    )
    db_session.add(j)
    db_session.commit()

    r = client.post(f"/journeys/{j.id}/feedback", headers=auth_headers, json={
        "rating": 5,
        "comment": "Excellent service",
        "category": "overall",
    })
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_satisfaction_stats_with_data(client, auth_headers, db_session):
    from database import PatientFeedback
    for i in range(3):
        db_session.add(PatientFeedback(
            hospital_id="default",
            rating=4,
            category="overall",
        ))
    db_session.commit()

    r = client.get("/outcomes/satisfaction", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_responses"] >= 3
    assert data["avg_rating"] is not None


# ── LWBS ─────────────────────────────────────────────────────────────────────

def test_get_lwbs_list(client, auth_headers):
    r = client.get("/lwbs", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_mark_lwbs_not_in_queue(client, auth_headers):
    r = client.post("/queue/NOPAT-LWBS/lwbs", headers=auth_headers)
    assert r.status_code == 404


# ── Beds Turnover ─────────────────────────────────────────────────────────────

def test_beds_turnover(client, auth_headers):
    r = client.get("/beds/turnover", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── Interpreter ───────────────────────────────────────────────────────────────

def test_add_interpreter_not_in_queue(client, auth_headers):
    r = client.post("/queue/NOPAT-INTERP/interpreter", headers=auth_headers, json={
        "language": "Spanish",
    })
    assert r.status_code == 404


def test_delete_interpreter_not_in_queue(client, auth_headers):
    # cancel_interpreter is idempotent — always 200 even if patient not in queue
    r = client.delete("/queue/NOPAT-INTERP/interpreter", headers=auth_headers)
    assert r.status_code == 200


# ── Medications ───────────────────────────────────────────────────────────────

def test_get_medications_not_in_queue(client, auth_headers):
    r = client.get("/queue/NOPAT-MEDS/medications", headers=auth_headers)
    assert r.status_code == 404


# ── Demo Seed ─────────────────────────────────────────────────────────────────

def test_demo_seed(client, auth_headers):
    r = client.get("/demo/seed", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["seeded"] is True
