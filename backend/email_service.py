"""
Email notifications — SendGrid REST API (primary) or SMTP (fallback).
Set SENDGRID_API_KEY for SendGrid, or SMTP_HOST + SMTP_USER + SMTP_PASS for SMTP.
ADMIN_EMAIL sets the destination for demo requests and escalation alerts.
"""
import os
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import httpx

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SMTP_HOST        = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT        = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER        = os.getenv("SMTP_USER", "")
SMTP_PASS        = os.getenv("SMTP_PASS", "")
FROM_EMAIL       = os.getenv("FROM_EMAIL", "noreply@mediscan.health")
ADMIN_EMAIL      = os.getenv("ADMIN_EMAIL", "olumidejegede@gmail.com")


def _send_sendgrid(to: str, subject: str, html: str) -> bool:
    try:
        r = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
            content=json.dumps({
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": FROM_EMAIL, "name": "MediScan Gateway"},
                "subject": subject,
                "content": [{"type": "text/html", "value": html}],
            }),
            timeout=10,
        )
        return r.status_code in (200, 202)
    except Exception as e:
        print(f"[Email] SendGrid error: {e}")
        return False


def _send_smtp(to: str, subject: str, html: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = FROM_EMAIL
        msg["To"]      = to
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(FROM_EMAIL, to, msg.as_string())
        return True
    except Exception as e:
        print(f"[Email] SMTP error: {e}")
        return False


def send_email(to: str, subject: str, html: str) -> bool:
    if SENDGRID_API_KEY:
        return _send_sendgrid(to, subject, html)
    if SMTP_USER and SMTP_PASS:
        return _send_smtp(to, subject, html)
    print(f"[Email] DEV MODE — To: {to} | Subject: {subject}")
    return True


# ── Templates ─────────────────────────────────────────────────────────────────

def notify_demo_request(name: str, hospital: str, role: str, email: str,
                        bed_count: int | None, message: str | None) -> bool:
    beds_line = f"<tr><td><b>Bed Count</b></td><td>{bed_count}</td></tr>" if bed_count else ""
    msg_line  = f"<tr><td><b>Message</b></td><td>{message}</td></tr>" if message else ""
    html = f"""
    <div style="font-family:Inter,sans-serif;max-width:600px;margin:0 auto;background:#050c18;color:#e2e8f0;border-radius:12px;overflow:hidden;">
      <div style="background:#0d9488;padding:24px 32px;">
        <h1 style="margin:0;font-size:22px;color:#fff;">⚕ New Demo Request</h1>
        <p style="margin:6px 0 0;opacity:.85;font-size:14px;">Someone wants to see MediScan in action</p>
      </div>
      <div style="padding:32px;">
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td style="padding:8px 0;color:#64748b;width:120px;"><b>Name</b></td><td style="color:#e2e8f0;">{name}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;"><b>Hospital</b></td><td style="color:#e2e8f0;">{hospital}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;"><b>Role</b></td><td style="color:#e2e8f0;">{role or "—"}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;"><b>Email</b></td><td><a href="mailto:{email}" style="color:#0d9488;">{email}</a></td></tr>
          {beds_line}
          {msg_line}
          <tr><td style="padding:8px 0;color:#64748b;"><b>Submitted</b></td><td style="color:#64748b;">{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</td></tr>
        </table>
        <div style="margin-top:24px;">
          <a href="mailto:{email}?subject=Your MediScan Demo Request" style="background:#0d9488;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700;font-size:14px;">
            Reply to {name.split()[0]} →
          </a>
        </div>
      </div>
    </div>
    """
    return send_email(ADMIN_EMAIL, f"🏥 Demo Request — {name} @ {hospital}", html)


def notify_journey_escalation(patient_name: str, esi_level: int, phone: str,
                               reason: str, portal_token: str | None = None) -> bool:
    portal_link = ""
    if portal_token:
        url = f"https://mediscan-gateway.vercel.app/patient?token={portal_token}"
        portal_link = f'<p><a href="{url}" style="color:#0d9488;">View Patient Portal →</a></p>'
    html = f"""
    <div style="font-family:Inter,sans-serif;max-width:600px;margin:0 auto;background:#050c18;color:#e2e8f0;border-radius:12px;overflow:hidden;">
      <div style="background:#dc2626;padding:24px 32px;">
        <h1 style="margin:0;font-size:22px;color:#fff;">🚨 Journey Escalation Alert</h1>
        <p style="margin:6px 0 0;opacity:.85;font-size:14px;">A patient has reported worsening symptoms</p>
      </div>
      <div style="padding:32px;">
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td style="padding:8px 0;color:#64748b;width:120px;"><b>Patient</b></td><td style="color:#e2e8f0;">{patient_name}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;"><b>ESI Level</b></td><td style="color:#f87171;">ESI {esi_level}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;"><b>Phone</b></td><td style="color:#e2e8f0;">{phone}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;"><b>Reason</b></td><td style="color:#fca5a5;">{reason}</td></tr>
          <tr><td style="padding:8px 0;color:#64748b;"><b>Time</b></td><td style="color:#64748b;">{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</td></tr>
        </table>
        {portal_link}
        <div style="margin-top:16px;padding:12px 16px;background:rgba(220,38,38,0.1);border:1px solid rgba(220,38,38,0.3);border-radius:8px;font-size:13px;color:#fca5a5;">
          Please attempt to contact the patient and assess for ED return.
        </div>
      </div>
    </div>
    """
    return send_email(ADMIN_EMAIL, f"🚨 Journey Escalation — {patient_name} (ESI {esi_level})", html)


def send_portal_link_sms_fallback(patient_name: str, portal_url: str) -> str:
    """Returns an SMS body with the portal link (caller uses notifications._sms)."""
    first = patient_name.split()[0]
    return (
        f"Hi {first}, your MediScan post-discharge care portal is ready: {portal_url} "
        f"Check in here for your follow-up schedule and to contact your care team."
    )
