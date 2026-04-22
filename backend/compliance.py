"""
Enterprise compliance module — escalation rules, BAA, HIPAA controls, data retention.
"""
import os
from datetime import datetime
from sqlalchemy.orm import Session
from database import EscalationRule

DEFAULT_RULES = [
    {
        "rule_name": "ESI 1 — Immediate Physician Notification",
        "condition_field": "esi_level",
        "condition_op": "eq",
        "condition_value": "1",
        "action": "notify_attending",
        "response_time_minutes": 2,
    },
    {
        "rule_name": "Sepsis Alert — Rapid Response",
        "condition_field": "sepsis_probability",
        "condition_op": "in",
        "condition_value": "high,critical",
        "action": "activate_rapid_response",
        "response_time_minutes": 5,
    },
    {
        "rule_name": "ESI 2 — Charge Nurse Notification",
        "condition_field": "esi_level",
        "condition_op": "eq",
        "condition_value": "2",
        "action": "page_charge_nurse",
        "response_time_minutes": 5,
    },
    {
        "rule_name": "High Admission Risk — Bed Management",
        "condition_field": "admission_probability",
        "condition_op": "gte",
        "condition_value": "80",
        "action": "notify_bed_management",
        "response_time_minutes": 15,
    },
    {
        "rule_name": "LWBS Risk — Proactive Rounding",
        "condition_field": "lwbs_risk",
        "condition_op": "eq",
        "condition_value": "high",
        "action": "proactive_rounding",
        "response_time_minutes": 20,
    },
    {
        "rule_name": "ED Capacity >90% — Surge Protocol",
        "condition_field": "ed_occupancy_pct",
        "condition_op": "gte",
        "condition_value": "90",
        "action": "activate_surge_protocol",
        "response_time_minutes": 0,
    },
]

HIPAA_CONTROLS = [
    {"control": "Data encrypted at rest (AES-256)",               "status": "pass"},
    {"control": "TLS 1.3 for all data in transit",                "status": "pass"},
    {"control": "HIPAA audit log — all PHI access events",        "status": "pass"},
    {"control": "Role-based access control (RBAC)",               "status": "pass"},
    {"control": "TOTP multi-factor authentication",               "status": "pass"},
    {"control": "Automatic session timeout (30 min)",             "status": "pass"},
    {"control": "PHI stripped from lobby/public endpoints",       "status": "pass"},
    {"control": "Data retention policy (7 years — 45 CFR 164)",   "status": "pass"},
    {"control": "Business Associate Agreement (BAA)",             "status": "available"},
    {"control": "Breach notification procedure",                  "status": "documented"},
    {"control": "Employee HIPAA training program",                "status": "in_progress"},
    {"control": "Penetration testing (annual)",                   "status": "scheduled"},
    {"control": "SOC 2 Type II audit",                            "status": "in_progress"},
    {"control": "Disaster recovery / BCP plan",                   "status": "in_progress"},
]

DATA_RETENTION_POLICY = {
    "patient_records_years": 7,
    "audit_logs_years": 7,
    "shift_reports_years": 3,
    "soap_notes_years": 7,
    "journey_records_years": 3,
    "basis": "HIPAA 45 CFR § 164.530(j) — 6-year minimum; extended to 7 for state law compliance",
    "deletion_method": "Cryptographic erasure + secure overwrite (NIST 800-88)",
    "backup_retention_days": 90,
}


def seed_escalation_rules(db: Session) -> None:
    from sqlalchemy import func
    if db.query(func.count(EscalationRule.id)).scalar() > 0:
        return
    for r in DEFAULT_RULES:
        db.add(EscalationRule(**r))
    db.commit()


def get_escalation_rules(db: Session) -> list:
    rows = db.query(EscalationRule).order_by(EscalationRule.response_time_minutes).all()
    return [_rule_to_dict(r) for r in rows]


def toggle_rule(db: Session, rule_id: str, enabled: bool) -> bool:
    rule = db.query(EscalationRule).filter_by(id=rule_id).first()
    if not rule:
        return False
    rule.enabled = enabled
    db.commit()
    return True


def update_rule(db: Session, rule_id: str, patch: dict) -> dict | None:
    rule = db.query(EscalationRule).filter_by(id=rule_id).first()
    if not rule:
        return None
    for field in ("action", "response_time_minutes", "condition_value", "enabled"):
        if field in patch:
            setattr(rule, field, patch[field])
    db.commit()
    return _rule_to_dict(rule)


def get_compliance_status() -> dict:
    pass_count = sum(1 for c in HIPAA_CONTROLS if c["status"] == "pass")
    return {
        "hipaa_controls": HIPAA_CONTROLS,
        "controls_passing": pass_count,
        "controls_total": len(HIPAA_CONTROLS),
        "compliance_score_pct": round(pass_count / len(HIPAA_CONTROLS) * 100),
        "data_retention": DATA_RETENTION_POLICY,
        "soc2_status": "in_progress",
        "soc2_expected": "Q3 2026",
        "baa_available": True,
        "last_pen_test": None,
        "next_pen_test": "2026-Q3",
        "generated_at": datetime.utcnow().isoformat(),
    }


def generate_baa_pdf() -> bytes:
    """Generate a minimal BAA PDF. Production: use pre-signed legal document."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        import io

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=1*inch, bottomMargin=1*inch)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("BUSINESS ASSOCIATE AGREEMENT (BAA)", styles["Heading1"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph("MediScan Gateway — HIPAA Business Associate Agreement", styles["Heading2"]))
        story.append(Spacer(1, 8))

        clauses = [
            ("1. Definitions", "Terms used but not otherwise defined in this Agreement shall have the same meaning as those in the HIPAA Rules (45 CFR Parts 160 and 164)."),
            ("2. Obligations of Business Associate", "MediScan Gateway agrees to: (a) not use or disclose Protected Health Information other than as permitted or required by the Agreement or as required by law; (b) use appropriate safeguards, and comply with Subpart C of 45 CFR Part 164 with respect to electronic PHI, to prevent use or disclosure of PHI; (c) report to Covered Entity any use or disclosure of PHI not provided for by the Agreement; (d) ensure that any subcontractors agree to the same restrictions; (e) make PHI available to the Covered Entity as necessary."),
            ("3. Security Measures", "MediScan Gateway implements: AES-256 encryption at rest, TLS 1.3 in transit, RBAC, MFA, continuous audit logging, and a 90-day backup retention policy consistent with NIST 800-88."),
            ("4. Breach Notification", "MediScan Gateway will notify Covered Entity without unreasonable delay, and no later than 60 calendar days following discovery of a Breach of Unsecured PHI, as required by 45 CFR § 164.410."),
            ("5. Term and Termination", "This Agreement shall be effective upon execution and shall terminate when all PHI is destroyed or returned, or upon written termination by either party with 30 days notice."),
            ("6. Governing Law", "This Agreement is governed by applicable federal law including the Health Insurance Portability and Accountability Act of 1996 (HIPAA) and the Health Information Technology for Economic and Clinical Health Act (HITECH)."),
        ]

        for title, body in clauses:
            story.append(Paragraph(title, styles["Heading3"]))
            story.append(Paragraph(body, styles["Normal"]))
            story.append(Spacer(1, 10))

        story.append(Spacer(1, 20))
        story.append(Paragraph("_________________________________     Date: ___________", styles["Normal"]))
        story.append(Paragraph("Authorized Representative — Covered Entity", styles["Normal"]))
        story.append(Spacer(1, 16))
        story.append(Paragraph("_________________________________     Date: ___________", styles["Normal"]))
        story.append(Paragraph("MediScan Gateway — Business Associate", styles["Normal"]))

        doc.build(story)
        return buf.getvalue()
    except Exception as e:
        print(f"BAA PDF error: {e}")
        return b""


def _rule_to_dict(r: EscalationRule) -> dict:
    return {
        "id": r.id,
        "rule_name": r.rule_name,
        "condition_field": r.condition_field,
        "condition_op": r.condition_op,
        "condition_value": r.condition_value,
        "action": r.action,
        "response_time_minutes": r.response_time_minutes,
        "enabled": r.enabled,
    }
