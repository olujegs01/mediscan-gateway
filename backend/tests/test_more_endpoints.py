"""
Tests for remaining uncovered endpoints:
billing, payer-mix, hospital switcher, FHIR webhook,
LWBS SMS, triage fallback, and more clinical journeys.
"""
import uuid
from unittest.mock import patch
from datetime import datetime


# ── Billing ───────────────────────────────────────────────────────────────────

def test_billing_create_checkout_no_stripe(client, auth_headers):
    r = client.post("/billing/create-checkout-session", headers=auth_headers, json={
        "tier": "starter",
        "email": "test@example.com",
        "hospital_name": "Test Hospital",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["demo_mode"] is True


def test_billing_status_no_stripe(client, auth_headers):
    r = client.get("/billing/status", headers=auth_headers)
    assert r.status_code == 200


def test_billing_webhook_no_stripe_config(client):
    # No STRIPE_WEBHOOK_SECRET → handle_webhook returns {"status": "skipped"} → 200
    r = client.post("/billing/webhook", content=b'{"type":"test"}',
                    headers={"content-type": "application/json"})
    assert r.status_code == 200
    assert r.json()["received"] is True


# ── Payer Mix Analytics ───────────────────────────────────────────────────────

def test_payer_mix_empty(client, auth_headers):
    r = client.get("/analytics/payer-mix", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "total_patients" in data
    assert "by_provider" in data


# ── Hospital Switcher ─────────────────────────────────────────────────────────

def test_list_available_hospitals(client, auth_headers):
    r = client.get("/hospitals/available", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_switch_hospital_not_found(client, auth_headers):
    r = client.post("/auth/switch-hospital", headers=auth_headers,
                    params={"slug": "nonexistent-hospital"})
    assert r.status_code == 404


def test_switch_hospital_success(client, auth_headers, db_session):
    from database import Hospital
    h = Hospital(
        slug="switch-test-hosp",
        name="Switch Test Hospital",
        active=True,
    )
    db_session.add(h)
    db_session.commit()

    r = client.post("/auth/switch-hospital", headers=auth_headers,
                    params={"slug": "switch-test-hosp"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["hospital"]["slug"] == "switch-test-hosp"


# ── FHIR Webhook ──────────────────────────────────────────────────────────────

def test_fhir_webhook_not_configured(client):
    r = client.post("/fhir/webhook", json={"resourceType": "Bundle", "type": "message", "entry": []})
    assert r.status_code == 503


def test_fhir_webhook_with_secret(client):
    with patch.dict("os.environ", {"FHIR_WEBHOOK_SECRET": "test-secret"}):
        r = client.post(
            "/fhir/webhook",
            json={"resourceType": "Bundle", "type": "message", "entry": []},
            headers={"X-FHIR-Secret": "test-secret", "X-Hospital-ID": "default"},
        )
        assert r.status_code == 200
        assert r.json()["accepted"] is True


def test_fhir_webhook_wrong_secret(client):
    with patch.dict("os.environ", {"FHIR_WEBHOOK_SECRET": "correct-secret"}):
        r = client.post(
            "/fhir/webhook",
            json={"resourceType": "Bundle", "type": "message", "entry": []},
            headers={"X-FHIR-Secret": "wrong-secret", "X-Hospital-ID": "default"},
        )
        assert r.status_code == 401


def test_fhir_webhook_missing_hospital_header(client):
    with patch.dict("os.environ", {"FHIR_WEBHOOK_SECRET": "test-secret"}):
        r = client.post(
            "/fhir/webhook",
            json={"resourceType": "Bundle", "type": "message", "entry": []},
            headers={"X-FHIR-Secret": "test-secret"},
        )
        assert r.status_code == 400


def test_fhir_webhook_not_a_bundle(client):
    with patch.dict("os.environ", {"FHIR_WEBHOOK_SECRET": "test-secret"}):
        r = client.post(
            "/fhir/webhook",
            json={"resourceType": "Patient", "id": "1"},
            headers={"X-FHIR-Secret": "test-secret", "X-Hospital-ID": "default"},
        )
        assert r.status_code == 200
        assert r.json()["accepted"] is False


# ── LWBS SMS ──────────────────────────────────────────────────────────────────

def test_lwbs_sms_not_found(client, auth_headers):
    r = client.post("/lwbs/nonexistent-id/sms", headers=auth_headers)
    assert r.status_code == 404


def test_lwbs_sms_no_phone(client, auth_headers, db_session):
    from database import LWBSRecord
    rec = LWBSRecord(
        id=str(uuid.uuid4()),
        hospital_id="default",
        name="LWBS Patient",
        age=40,
        phone=None,  # no phone
        left_at=datetime.utcnow(),
    )
    db_session.add(rec)
    db_session.commit()

    r = client.post(f"/lwbs/{rec.id}/sms", headers=auth_headers)
    assert r.status_code == 422


def test_lwbs_sms_success(client, auth_headers, db_session):
    from database import LWBSRecord
    rec = LWBSRecord(
        id=str(uuid.uuid4()),
        hospital_id="default",
        name="LWBS Patient With Phone",
        age=35,
        phone="+13125550099",
        left_at=datetime.utcnow(),
    )
    db_session.add(rec)
    db_session.commit()

    # No Twilio env vars → simulated send
    r = client.post(f"/lwbs/{rec.id}/sms", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["sent"] is True


# ── Compliance escalation rule update ────────────────────────────────────────

def test_compliance_patch_rule_success(client, auth_headers, db_session):
    from compliance import seed_escalation_rules
    seed_escalation_rules(db_session)

    from compliance import get_escalation_rules
    rules = get_escalation_rules(db_session)
    if rules:
        rule_id = rules[0]["id"]
        r = client.patch(
            f"/compliance/escalation-rules/{rule_id}",
            headers=auth_headers,
            json={"enabled": True, "response_time_minutes": 10},
        )
        assert r.status_code == 200


# ── Report email ──────────────────────────────────────────────────────────────

def test_report_email(client, auth_headers):
    with patch("email_service.send_email", return_value=True):
        r = client.post("/report/email", headers=auth_headers, json={
            "to_email": "admin@hospital.com",
        })
        assert r.status_code in (200, 422)


# ── Schedule appointment ──────────────────────────────────────────────────────

def test_schedule_slot_not_found(client):
    r = client.post("/check/schedule", json={
        "slot_id": "nonexistent",
        "patient_name": "Alice",
        "patient_age": 30,
        "phone": "+13125550001",
        "symptoms": "cough",
    })
    assert r.status_code == 409


# ── Chart note generate for non-existent patient ─────────────────────────────

def test_chart_note_generate_not_in_queue(client, auth_headers):
    r = client.post("/chart/note/PT-NOT-IN-QUEUE/generate", headers=auth_headers)
    assert r.status_code == 404


# ── Discharge endpoint (alternate route) ─────────────────────────────────────

def test_discharge_queue_route_not_found(client, auth_headers):
    r = client.delete("/queue/GHOST-PT/discharge", headers=auth_headers)
    assert r.status_code == 404


# ── Triage fallback ───────────────────────────────────────────────────────────

class TestTriageFallback:
    def _make_sensors(self, **overrides):
        from models import SensorReadings
        defaults = {
            "heart_rate": 75, "respiratory_rate": 16, "skin_temp": 37.0,
            "fever_flag": False, "gait_symmetry": 0.92, "posture_score": 0.88,
            "bone_density_flag": False, "o2_sat": 98, "inflammation_zones": [],
            "limb_asymmetry": None, "injury_indicators": [], "dense_tissue_alerts": [],
            "gait_speed": 1.2,
        }
        defaults.update(overrides)
        return SensorReadings(**defaults)

    def _make_ehr(self):
        from models import EHRRecord
        return EHRRecord(
            patient_id="PT-TRIAGE-001",
            history=[],
            current_medications=[],
            allergies=[],
            last_visit=None,
            blood_type="O+",
        )

    def test_triage_fallback_critical(self):
        from triage import _fallback_triage
        sensors = self._make_sensors(heart_rate=140, respiratory_rate=32)
        result = _fallback_triage(50, "chest pain", sensors)
        assert result["esi_level"] == 1
        assert result["priority_label"] == "CRITICAL"

    def test_triage_fallback_behavioral_health(self):
        from triage import _fallback_triage
        sensors = self._make_sensors()
        result = _fallback_triage(30, "suicidal ideation", sensors)
        assert result["esi_level"] == 2

    def test_triage_fallback_sepsis(self):
        from triage import _fallback_triage
        sensors = self._make_sensors(heart_rate=115, fever_flag=True, skin_temp=39.2)
        result = _fallback_triage(60, "fever and chills", sensors)
        assert result["esi_level"] in (1, 2)

    def test_triage_fallback_urgent(self):
        from triage import _fallback_triage
        sensors = self._make_sensors(heart_rate=105)
        result = _fallback_triage(45, "mild fever", sensors)
        assert result["esi_level"] in (2, 3)

    def test_triage_fallback_gait_issue(self):
        from triage import _fallback_triage
        sensors = self._make_sensors(gait_symmetry=0.6, bone_density_flag=True)
        result = _fallback_triage(70, "back pain", sensors)
        assert result["esi_level"] in (3, 4)

    def test_triage_fallback_pain(self):
        from triage import _fallback_triage
        sensors = self._make_sensors()
        result = _fallback_triage(35, "pain and nausea", sensors)
        assert result["esi_level"] in (3, 4)

    def test_triage_fallback_non_urgent(self):
        from triage import _fallback_triage
        sensors = self._make_sensors()
        result = _fallback_triage(28, "runny nose", sensors)
        assert result["esi_level"] == 5

    def test_run_ai_triage_fallback_on_api_error(self):
        from triage import run_ai_triage
        from models import SensorReadings, EHRRecord
        sensors = SensorReadings(
            heart_rate=75, respiratory_rate=16, skin_temp=37.0, fever_flag=False,
            gait_symmetry=0.92, posture_score=0.88, bone_density_flag=False,
            o2_sat=98, inflammation_zones=[], limb_asymmetry=None,
            injury_indicators=[], dense_tissue_alerts=[], gait_speed=1.2,
        )
        ehr = EHRRecord(
            patient_id="PT-T-001", history=[], current_medications=[],
            allergies=[], last_visit=None, blood_type="O+",
        )
        with patch("triage.client") as mock_client:
            mock_client.messages.create.side_effect = Exception("API down")
            result = run_ai_triage("PT-T-001", "Test", 40, "headache", sensors, ehr)
        assert "esi_level" in result
        assert "priority_label" in result
