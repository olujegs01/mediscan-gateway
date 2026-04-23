import os
import jwt
import bcrypt
import pyotp
import qrcode
import io
import base64
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

SECRET_KEY = os.getenv("SECRET_KEY", "mediscan-dev-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12

security = HTTPBearer()

# Production: move to DB + proper identity provider (Auth0/Okta)
USERS_DB = {
    "admin": {
        "password_hash": bcrypt.hashpw(b"mediscan2026", bcrypt.gensalt()).decode(),
        "role": "admin",
        "name": "System Admin",
        "hospital_id": "default",
        "mfa_secret": pyotp.random_base32(),
        "mfa_enabled": False,
    },
    "nurse": {
        "password_hash": bcrypt.hashpw(b"nurse2026", bcrypt.gensalt()).decode(),
        "role": "nurse",
        "name": "Triage Nurse",
        "hospital_id": "default",
        "mfa_secret": pyotp.random_base32(),
        "mfa_enabled": False,
    },
    "physician": {
        "password_hash": bcrypt.hashpw(b"physician2026", bcrypt.gensalt()).decode(),
        "role": "physician",
        "name": "On-Call Physician",
        "hospital_id": "default",
        "mfa_secret": pyotp.random_base32(),
        "mfa_enabled": False,
    },
}


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    name: str
    mfa_required: bool = False
    mfa_enabled: bool = False


class MFASetupResponse(BaseModel):
    secret: str
    qr_code_base64: str
    backup_codes: list[str]


def create_token(username: str, role: str, mfa_verified: bool = False,
                 hospital_id: str = "default") -> str:
    payload = {
        "sub": username,
        "role": role,
        "mfa": mfa_verified,
        "hospital_id": hospital_id,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_pre_mfa_token(username: str) -> str:
    """Short-lived token issued after password check, before MFA verification."""
    payload = {
        "sub": username,
        "scope": "pre_mfa",
        "exp": datetime.utcnow() + timedelta(minutes=5),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("scope") == "pre_mfa":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA verification required")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_role(*roles):
    def checker(token: dict = Depends(verify_token)):
        if token.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return token
    return checker


def login(data: LoginRequest) -> TokenResponse:
    user = USERS_DB.get(data.username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not bcrypt.checkpw(data.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    mfa_enabled = user.get("mfa_enabled", False)

    # If MFA is enabled, verify TOTP code
    if mfa_enabled:
        if not data.totp_code:
            # Password correct but MFA needed — return pre-MFA token
            pre_token = create_pre_mfa_token(data.username)
            return TokenResponse(
                access_token=pre_token,
                token_type="bearer",
                role=user["role"],
                name=user["name"],
                mfa_required=True,
                mfa_enabled=True,
            )
        # Verify TOTP
        totp = pyotp.TOTP(user["mfa_secret"])
        if not totp.verify(data.totp_code, valid_window=1):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")

    token = create_token(data.username, user["role"], mfa_verified=mfa_enabled,
                         hospital_id=user.get("hospital_id", "default"))
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        name=user["name"],
        mfa_required=False,
        mfa_enabled=mfa_enabled,
    )


def setup_mfa(username: str) -> MFASetupResponse:
    user = USERS_DB.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    secret = user["mfa_secret"]
    app_name = "MediScan Gateway"
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name=app_name)

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    # Backup codes
    backup_codes = [pyotp.random_base32()[:8].lower() for _ in range(8)]

    return MFASetupResponse(secret=secret, qr_code_base64=qr_b64, backup_codes=backup_codes)


def enable_mfa(username: str, totp_code: str) -> bool:
    user = USERS_DB.get(username)
    if not user:
        return False
    totp = pyotp.TOTP(user["mfa_secret"])
    if totp.verify(totp_code, valid_window=1):
        user["mfa_enabled"] = True
        return True
    return False
