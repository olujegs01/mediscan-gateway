"""
HIPAA-compliant audit logging middleware.
Every protected endpoint logs: who, what, when, patient_id, IP, success/fail.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import jwt as pyjwt

from auth import SECRET_KEY, ALGORITHM
from database import SessionLocal
from patient_store import write_audit

# Actions that should be audit-logged (path prefix → action label)
_AUDIT_MAP = {
    ("POST",  "/auth/login"):     "login",
    ("GET",   "/queue"):          "view_queue",
    ("DELETE","/queue/"):         "discharge",
    ("DELETE","/queue"):          "clear_queue",
    ("GET",   "/scan/stream"):    "scan",
    ("GET",   "/analytics"):      "view_analytics",
    ("GET",   "/audit"):          "view_audit",
    ("GET",   "/report"):         "view_report",
    ("POST",  "/report"):         "generate_report",
}


def _resolve_action(method: str, path: str) -> str | None:
    for (m, p), label in _AUDIT_MAP.items():
        if method == m and path.startswith(p):
            return label
    return None


def _extract_token_payload(request: Request) -> dict | None:
    auth = request.headers.get("Authorization", "")
    token = None
    if auth.startswith("Bearer "):
        token = auth[7:]
    elif "token" in request.query_params:
        token = request.query_params["token"]
    if not token:
        return None
    try:
        return pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None


def _extract_patient_id(path: str) -> str | None:
    """Pull patient_id from /queue/{patient_id}."""
    parts = path.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "queue":
        return parts[1]
    return None


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        action = _resolve_action(request.method, request.url.path)
        response = await call_next(request)

        if action:
            payload = _extract_token_payload(request)
            username = payload["sub"] if payload else "anonymous"
            role     = payload.get("role", "unknown") if payload else "unknown"
            patient_id = _extract_patient_id(request.url.path)
            ip = request.client.host if request.client else None
            success = response.status_code < 400

            db = SessionLocal()
            try:
                write_audit(
                    db=db,
                    username=username,
                    role=role,
                    action=action,
                    patient_id=patient_id,
                    ip_address=ip,
                    details={"path": request.url.path, "status": response.status_code},
                    success=success,
                )
            finally:
                db.close()

        return response
