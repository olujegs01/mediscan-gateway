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
    {"control": "Data encrypted at rest (AES-256)",                "status": "pass",        "note": "SQLite/PostgreSQL with encrypted storage"},
    {"control": "TLS 1.3 for all data in transit",                 "status": "pass",        "note": "Enforced by Render/Vercel HTTPS"},
    {"control": "HIPAA audit log — all PHI access events",         "status": "pass",        "note": "AuditLog table records every access"},
    {"control": "Role-based access control (RBAC)",                "status": "pass",        "note": "admin / nurse / physician roles enforced"},
    {"control": "TOTP multi-factor authentication",                "status": "pass",        "note": "pyotp TOTP with 30s windows"},
    {"control": "Automatic session timeout (12h JWT expiry)",      "status": "pass",        "note": "TOKEN_EXPIRE_HOURS=12 in auth.py"},
    {"control": "PHI stripped from public/lobby endpoints",        "status": "pass",        "note": "Lobby and demo endpoints return no PHI"},
    {"control": "Data retention policy documented (7 years)",      "status": "pass",        "note": "45 CFR 164.530(j) compliant"},
    {"control": "Security headers (HSTS, X-Frame, CSP)",           "status": "pass",        "note": "Added via FastAPI middleware"},
    {"control": "Brute-force login protection (rate limiting)",    "status": "pass",        "note": "15-min lockout after 10 failed attempts"},
    {"control": "Input validation on all endpoints",               "status": "pass",        "note": "Pydantic models + FastAPI validation"},
    {"control": "Business Associate Agreement (BAA)",              "status": "available",   "note": "One-click PDF generation available"},
    {"control": "Breach notification procedure",                   "status": "documented",  "note": "60-day notification per 45 CFR §164.410"},
    {"control": "Employee HIPAA training program",                 "status": "in_progress", "note": "Scheduled for Q2 2026"},
    {"control": "Annual penetration testing",                      "status": "scheduled",   "note": "Scheduled Q3 2026 with external vendor"},
    {"control": "SOC 2 Type II audit",                             "status": "in_progress", "note": "Readiness assessment underway"},
    {"control": "Disaster recovery / BCP plan",                    "status": "in_progress", "note": "DR runbook in progress"},
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


def send_hipaa_alert_email(controls_at_risk: list) -> bool:
    """Email admin when HIPAA controls are not passing."""
    try:
        from email_service import send_email, ADMIN_EMAIL
        from datetime import datetime
        rows = "".join(
            f'<tr><td style="padding:8px;color:#e2e8f0;">{c["control"]}</td>'
            f'<td style="padding:8px;color:#fbbf24;text-transform:uppercase;">{c["status"]}</td>'
            f'<td style="padding:8px;color:#64748b;">{c.get("note","")}</td></tr>'
            for c in controls_at_risk
        )
        html = f"""
        <div style="font-family:Inter,sans-serif;max-width:640px;background:#050c18;color:#e2e8f0;border-radius:12px;overflow:hidden;">
          <div style="background:#ca8a04;padding:20px 28px;">
            <h1 style="margin:0;font-size:18px;color:#fff;">⚠ HIPAA Controls Need Attention</h1>
            <p style="margin:6px 0 0;font-size:13px;opacity:.85;">{len(controls_at_risk)} control(s) require action · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
          </div>
          <div style="padding:28px;">
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
              <tr style="background:#1e293b;color:#64748b;"><th style="padding:8px;text-align:left;">Control</th><th style="padding:8px;text-align:left;">Status</th><th style="padding:8px;text-align:left;">Note</th></tr>
              {rows}
            </table>
            <p style="margin-top:20px;font-size:12px;color:#475569;">Log in to the MediScan Gateway compliance center to review and remediate.</p>
          </div>
        </div>"""
        return send_email(ADMIN_EMAIL, f"⚠ MediScan HIPAA Alert — {len(controls_at_risk)} controls need attention", html)
    except Exception as e:
        print(f"[HIPAA Alert] Email error: {e}")
        return False


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
