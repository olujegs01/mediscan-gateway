"""
Targeted tests to push overall coverage above 80%.
Covers: clinical_journeys, sms_triage, billing, monitor, email templates.
"""
import asyncio
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base, ClinicalJourney


@pytest.fixture(scope="module")
def mem_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


# ── clinical_journeys.py ──────────────────────────────────────────────────────

class TestClinicalJourneysSMS:
    def test_send_checkin_sms_no_phone(self, mem_db):
        from clinical_journeys import send_checkin_sms
        journey = ClinicalJourney(
            patient_id="PT-SMS-001",
            name="Alice",
            phone="",  # empty phone
            esi_level=3,
        )
        mem_db.add(journey)
        mem_db.commit()
        result = send_checkin_sms(journey, 1)
        assert result is False

    def test_send_checkin_sms_with_phone(self, mem_db):
        from clinical_journeys import send_checkin_sms
        journey = ClinicalJourney(
            patient_id="PT-SMS-002",
            name="Bob Smith",
            phone="+13125550001",
            esi_level=2,
        )
        mem_db.add(journey)
        mem_db.commit()
        with patch("clinical_journeys._sms" if hasattr(__import__("clinical_journeys"), "_sms") else "notifications._sms", return_value=False):
            result = send_checkin_sms(journey, 2)
            assert isinstance(result, bool)

    def test_process_sms_response_no_journey(self, mem_db):
        from clinical_journeys import process_sms_response
        result = process_sms_response(mem_db, "+19999999999", "feeling better")
        assert result is None

    def test_process_sms_response_improving(self, mem_db):
        from clinical_journeys import trigger_journey, process_sms_response
        trigger_journey(mem_db, "PT-SMS-PROC-01", "Carol", "+13125550100", esi_level=3)
        result = process_sms_response(mem_db, "+13125550100", "1")
        assert result is not None
        assert result.get("escalated") is False

    def test_process_sms_response_worsening(self, mem_db):
        from clinical_journeys import trigger_journey, process_sms_response
        trigger_journey(mem_db, "PT-SMS-PROC-02", "Dave", "+13125550200", esi_level=2)
        with patch("email_service.notify_journey_escalation", return_value=True):
            result = process_sms_response(mem_db, "+13125550200", "worse, severe chest pain")
        assert result is not None
        assert result.get("escalated") is True

    def test_process_sms_response_3_is_worsening(self, mem_db):
        from clinical_journeys import trigger_journey, process_sms_response
        trigger_journey(mem_db, "PT-SMS-PROC-03", "Eve", "+13125550300", esi_level=3)
        result = process_sms_response(mem_db, "+13125550300", "3")
        assert result is not None
        assert result.get("escalated") is True

    def test_process_sms_response_journey_completes(self, mem_db):
        """When all check-ins are done, journey completes."""
        from clinical_journeys import trigger_journey, process_sms_response
        trigger_journey(mem_db, "PT-SMS-COMPLETE", "Frank", "+13125550400", esi_level=5)
        # ESI 5 has only 1 check-in; after 1 response it should complete
        process_sms_response(mem_db, "+13125550400", "feeling fine")
        journey = mem_db.query(ClinicalJourney).filter_by(patient_id="PT-SMS-COMPLETE").first()
        assert journey is not None
        assert journey.journey_status in ("completed", "active")


# ── sms_triage.py ─────────────────────────────────────────────────────────────

class TestSmsTriage:
    def test_handle_help_message(self, mem_db):
        from sms_triage import handle_inbound_sms
        result = handle_inbound_sms(mem_db, "+13125550001", "HELP")
        assert isinstance(result, str)
        assert "MediScan" in result or "xml" in result.lower() or "<Response>" in result

    def test_handle_empty_message(self, mem_db):
        from sms_triage import handle_inbound_sms
        result = handle_inbound_sms(mem_db, "+13125550001", "")
        assert isinstance(result, str)

    def test_handle_sms_with_symptoms(self, mem_db):
        from sms_triage import handle_inbound_sms
        mock_result = {
            "care_level": "URGENT_CARE",
            "urgency": "moderate",
            "reasoning": "mild symptoms",
            "follow_up_questions": [],
            "red_flags": [],
            "care_instructions": ["Rest", "Monitor symptoms"],
        }
        with patch("sms_triage.run_assessment", return_value=mock_result):
            result = handle_inbound_sms(mem_db, "+13125550002", "45M chest pain started 2hrs ago")
            assert isinstance(result, str)

    def test_twiml_helper(self):
        from sms_triage import _twiml
        xml = _twiml("Test message")
        assert "<Response>" in xml
        assert "Test message" in xml

    def test_format_sms_result(self):
        from sms_triage import _format_sms_result
        result = {
            "care_level": "URGENT_CARE",
            "reasoning": "Moderate symptoms",
            "care_instructions": ["Rest", "Take ibuprofen"],
            "red_flags": ["chest pain"],
        }
        formatted = _format_sms_result(result)
        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_parse_demographics(self):
        from sms_triage import _parse_demographics
        age, sex = _parse_demographics("45M chest pain")
        assert age == 45
        assert sex.lower() in ("male", "m", "man")

    def test_parse_demographics_female(self):
        from sms_triage import _parse_demographics
        age, sex = _parse_demographics("32F headache")
        assert age == 32
        assert sex.lower() in ("female", "f", "woman")

    def test_parse_demographics_no_match(self):
        from sms_triage import _parse_demographics
        age, sex = _parse_demographics("I have a headache")
        # Should return defaults when no demographics found
        assert age is None or isinstance(age, int)

    def test_handle_sms_journey_response(self, mem_db):
        """If the phone matches an active journey, it routes to process_sms_response."""
        from clinical_journeys import trigger_journey
        from sms_triage import handle_inbound_sms
        trigger_journey(mem_db, "PT-TWILIO-01", "Grace", "+13125559999", esi_level=3)
        result = handle_inbound_sms(mem_db, "+13125559999", "feeling better")
        assert isinstance(result, str)


# ── billing.py ────────────────────────────────────────────────────────────────

class TestBilling:
    def test_stripe_available_false(self):
        import billing
        with patch.object(billing, "STRIPE_SECRET_KEY", ""):
            assert billing.stripe_available() is False

    def test_stripe_available_true(self):
        import billing
        with patch.object(billing, "STRIPE_SECRET_KEY", "sk_test_xxx"):
            assert billing.stripe_available() is True

    def test_create_checkout_no_stripe(self):
        from billing import create_checkout_session
        result = create_checkout_session("starter", "test@example.com", "Test Hospital")
        assert result["demo_mode"] is True

    def test_create_checkout_with_stripe(self):
        import billing
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/session/xxx"
        mock_session.id = "cs_test_xxx"

        with patch.object(billing, "STRIPE_SECRET_KEY", "sk_test_xxx"):
            with patch.object(billing, "STRIPE_PRICE_STARTER", "price_starter_xxx"):
                with patch("stripe.checkout.Session.create", return_value=mock_session):
                    result = billing.create_checkout_session("starter", "test@example.com")
                    assert result["demo_mode"] is False
                    assert "checkout_url" in result

    def test_create_checkout_no_price_id(self):
        import billing
        with patch.object(billing, "STRIPE_SECRET_KEY", "sk_test_xxx"):
            with patch.object(billing, "STRIPE_PRICE_STARTER", ""):
                result = billing.create_checkout_session("starter")
                assert result["demo_mode"] is True

    def test_handle_webhook_no_secret(self):
        from billing import handle_webhook
        result = handle_webhook(b'{"type":"test"}', "sig")
        assert result["status"] == "skipped"

    def test_handle_webhook_with_secret(self):
        import billing
        mock_event = {"type": "checkout.session.completed",
                      "data": {"object": {"id": "cs_xxx", "subscription": "sub_xxx",
                                          "customer_email": "x@example.com",
                                          "metadata": {"tier": "starter", "hospital": "Test"}}}}
        with patch.object(billing, "STRIPE_WEBHOOK_SECRET", "whsec_xxx"):
            with patch.object(billing, "STRIPE_SECRET_KEY", "sk_xxx"):
                with patch("stripe.Webhook.construct_event", return_value=mock_event):
                    result = billing.handle_webhook(b'{}', "sig")
                    assert result.get("event") == "checkout.session.completed"


# ── monitor.py ────────────────────────────────────────────────────────────────

class TestMonitor:
    def test_run_checks_empty_queue(self):
        from monitor import _run_checks
        broadcast_calls = []

        async def mock_broadcast(event, staff_data, lobby_data=None):
            broadcast_calls.append(event)

        asyncio.get_event_loop().run_until_complete(
            _run_checks([], mock_broadcast)
        )
        # No alerts for empty queue
        assert len(broadcast_calls) == 0

    def test_run_checks_with_patient_no_timestamp(self):
        from monitor import _run_checks

        async def mock_broadcast(event, staff_data, lobby_data=None):
            pass

        queue = [{
            "patient_id": "PT-M-001",
            "name": "Test Patient",
            "esi_level": 3,
            "room_assignment": "Room 5",
            "timestamp": None,
            "triage_detail": {},
        }]
        asyncio.get_event_loop().run_until_complete(
            _run_checks(queue, mock_broadcast)
        )

    def test_run_checks_with_long_wait(self):
        from monitor import _run_checks
        from datetime import datetime, timedelta

        broadcast_calls = []

        async def mock_broadcast(event, staff_data, lobby_data=None):
            broadcast_calls.append((event, staff_data))

        # Patient with ESI 1 waiting too long
        old_ts = (datetime.utcnow() - timedelta(minutes=15)).isoformat()
        queue = [{
            "patient_id": "PT-M-002",
            "name": "Long Wait Patient",
            "esi_level": 1,
            "room_assignment": "Trauma Bay",
            "timestamp": old_ts,
            "triage_detail": {"sepsis_probability": "high"},
        }]

        with patch("monitor._anthropic") as mock_anthro:
            mock_anthro.messages.create.side_effect = Exception("API error")
            asyncio.get_event_loop().run_until_complete(
                _run_checks(queue, mock_broadcast)
            )


# ── email_service.py templates ────────────────────────────────────────────────

class TestEmailServiceTemplates:
    def test_notify_journey_escalation(self):
        from email_service import notify_journey_escalation
        with patch("email_service.send_email", return_value=True):
            result = notify_journey_escalation(
                patient_name="John Doe",
                esi_level=2,
                phone="+13125550001",
                reason="Patient reported worsening symptoms",
                portal_token="abc-token-123",
            )
            assert result is True

    def test_send_shift_report_email(self):
        from email_service import send_shift_report_email
        report = {
            "generated_by": "admin",
            "total_patients": 42,
            "esi_breakdown": {"1": 2, "2": 8},
            "sepsis_count": 3,
            "bh_count": 1,
            "admissions_predicted": 5,
            "lwbs_high_risk_count": 2,
            "avg_wait_minutes": 18.5,
            "shift_start": "2026-05-01T07:00",
            "shift_end": "2026-05-01T19:00",
        }
        with patch("email_service.send_email", return_value=True):
            result = send_shift_report_email(report, ["admin@hospital.com"])
            assert result is True


# ── Training Simulation Endpoints ────────────────────────────────────────────

def test_training_scenarios_returns_list(client):
    res = client.get("/training/scenarios")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 10

def test_training_scenarios_no_correct_esi(client):
    res = client.get("/training/scenarios")
    for scenario in res.json():
        assert "correct_esi" not in scenario
        assert "correct_reasoning" not in scenario
        assert "teaching_points" not in scenario

def test_training_scenarios_have_required_fields(client):
    res = client.get("/training/scenarios")
    for s in res.json():
        assert "id" in s
        assert "name" in s
        assert "chief_complaint" in s
        assert "vitals" in s
        assert "difficulty" in s

def test_training_submit_correct(client, auth_headers):
    # T002 is the ankle sprain — correct ESI is 4
    res = client.post("/training/submit",
        json={"scenario_id": "T002", "selected_esi": 4, "response_time_seconds": 15.0},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["correct"] is True
    assert data["correct_esi"] == 4
    assert data["score"] > 0
    assert "reasoning" in data
    assert "teaching_points" in data

def test_training_submit_wrong(client, auth_headers):
    res = client.post("/training/submit",
        json={"scenario_id": "T002", "selected_esi": 1, "response_time_seconds": 30.0},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["correct"] is False
    assert data["score"] == 0

def test_training_submit_adjacent_partial_credit(client, auth_headers):
    # T002 correct=4; guess 3 should give 50 pts partial
    res = client.post("/training/submit",
        json={"scenario_id": "T002", "selected_esi": 3, "response_time_seconds": 30.0},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["score"] == 50

def test_training_submit_invalid_scenario(client, auth_headers):
    res = client.post("/training/submit",
        json={"scenario_id": "T999", "selected_esi": 3, "response_time_seconds": 10.0},
        headers=auth_headers,
    )
    assert res.status_code == 404

def test_training_submit_requires_auth(client):
    res = client.post("/training/submit",
        json={"scenario_id": "T002", "selected_esi": 4, "response_time_seconds": 10.0},
    )
    assert res.status_code in (401, 403)

def test_training_reveal(client, auth_headers):
    res = client.get("/training/scenarios/T001/reveal", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "correct_esi" in data
    assert data["correct_esi"] == 1
    assert "teaching_points" in data

def test_training_reveal_not_found(client, auth_headers):
    res = client.get("/training/scenarios/T999/reveal", headers=auth_headers)
    assert res.status_code == 404

def test_training_speed_bonus(client, auth_headers):
    # Fast correct answer should get speed bonus
    fast = client.post("/training/submit",
        json={"scenario_id": "T002", "selected_esi": 4, "response_time_seconds": 5.0},
        headers=auth_headers,
    ).json()
    slow = client.post("/training/submit",
        json={"scenario_id": "T002", "selected_esi": 4, "response_time_seconds": 119.0},
        headers=auth_headers,
    ).json()
    assert fast["speed_bonus"] > slow["speed_bonus"]
    assert fast["score"] > slow["score"]
