"""
Unit tests for compliance.py.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base, EscalationRule
from compliance import (
    seed_escalation_rules,
    get_escalation_rules,
    toggle_rule,
    update_rule,
    get_compliance_status,
    generate_baa_pdf,
    DEFAULT_RULES,
    HIPAA_CONTROLS,
    DATA_RETENTION_POLICY,
)


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


def test_seed_escalation_rules(mem_db):
    seed_escalation_rules(mem_db)
    rules = mem_db.query(EscalationRule).all()
    assert len(rules) == len(DEFAULT_RULES)


def test_seed_escalation_rules_idempotent(mem_db):
    # Seeding twice should not add duplicates
    seed_escalation_rules(mem_db)
    rules = mem_db.query(EscalationRule).all()
    assert len(rules) == len(DEFAULT_RULES)


def test_get_escalation_rules(mem_db):
    rules = get_escalation_rules(mem_db)
    assert len(rules) == len(DEFAULT_RULES)
    for r in rules:
        assert "id" in r
        assert "rule_name" in r
        assert "enabled" in r


def test_toggle_rule_disable(mem_db):
    rules = get_escalation_rules(mem_db)
    rule_id = rules[0]["id"]
    result = toggle_rule(mem_db, rule_id, enabled=False)
    assert result is True

    # Verify the change persisted
    updated = get_escalation_rules(mem_db)
    match = next(r for r in updated if r["id"] == rule_id)
    assert match["enabled"] is False


def test_toggle_rule_enable(mem_db):
    rules = get_escalation_rules(mem_db)
    rule_id = rules[0]["id"]
    result = toggle_rule(mem_db, rule_id, enabled=True)
    assert result is True


def test_toggle_rule_not_found(mem_db):
    result = toggle_rule(mem_db, "nonexistent-id", enabled=False)
    assert result is False


def test_update_rule(mem_db):
    rules = get_escalation_rules(mem_db)
    rule_id = rules[0]["id"]
    updated = update_rule(mem_db, rule_id, {"response_time_minutes": 99, "enabled": False})
    assert updated is not None
    assert updated["response_time_minutes"] == 99
    assert updated["enabled"] is False


def test_update_rule_not_found(mem_db):
    result = update_rule(mem_db, "no-such-id", {"enabled": False})
    assert result is None


def test_get_compliance_status():
    status = get_compliance_status()
    assert "hipaa_controls" in status
    assert "compliance_score_pct" in status
    assert "controls_passing" in status
    assert "controls_total" in status
    assert "data_retention" in status
    assert "baa_available" in status
    assert status["controls_total"] == len(HIPAA_CONTROLS)
    assert 0 <= status["compliance_score_pct"] <= 100


def test_hipaa_controls_structure():
    for control in HIPAA_CONTROLS:
        assert "control" in control
        assert "status" in control


def test_data_retention_policy():
    assert DATA_RETENTION_POLICY["patient_records_years"] >= 6
    assert DATA_RETENTION_POLICY["audit_logs_years"] >= 6


def test_generate_baa_pdf():
    pdf = generate_baa_pdf()
    assert isinstance(pdf, bytes)
    assert len(pdf) > 0
    assert pdf[:4] == b"%PDF"


def test_default_rules_all_have_required_fields():
    required = {"rule_name", "condition_field", "condition_op", "condition_value", "action"}
    for rule in DEFAULT_RULES:
        for field in required:
            assert field in rule, f"Rule missing field: {field}"
