"""
Extended tests for auth.py — covers edge cases not hit by the existing test_auth.py.
"""
import pytest
import jwt as pyjwt
from fastapi import HTTPException

import auth
from auth import (
    create_token,
    create_pre_mfa_token,
    verify_token,
    require_role,
    login,
    setup_mfa,
    enable_mfa,
    disable_mfa,
    _get_user,
    LoginRequest,
    SECRET_KEY,
    ALGORITHM,
)


# ── create_token ──────────────────────────────────────────────────────────────

def test_create_token_contains_hospital_id():
    token = create_token("nurse", "nurse", hospital_id="hospital-abc")
    payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["hospital_id"] == "hospital-abc"


def test_create_token_mfa_verified():
    token = create_token("admin", "admin", mfa_verified=True)
    payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["mfa"] is True


def test_create_token_mfa_not_verified():
    token = create_token("admin", "admin", mfa_verified=False)
    payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["mfa"] is False


# ── create_pre_mfa_token ──────────────────────────────────────────────────────

def test_create_pre_mfa_token_has_scope():
    token = create_pre_mfa_token("admin")
    payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["scope"] == "pre_mfa"
    assert payload["sub"] == "admin"


# ── verify_token ──────────────────────────────────────────────────────────────

class FakeCredentials:
    def __init__(self, token):
        self.credentials = token


def test_verify_token_valid():
    token = create_token("admin", "admin")
    creds = FakeCredentials(token)
    payload = verify_token(creds)
    assert payload["sub"] == "admin"


def test_verify_token_expired():
    import jwt
    payload = {
        "sub": "admin",
        "role": "admin",
        "mfa": False,
        "hospital_id": "default",
        "exp": 1,  # Unix epoch — immediately expired
        "iat": 1,
    }
    expired_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    creds = FakeCredentials(expired_token)
    with pytest.raises(HTTPException) as exc_info:
        verify_token(creds)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_verify_token_invalid():
    creds = FakeCredentials("totally.invalid.token")
    with pytest.raises(HTTPException) as exc_info:
        verify_token(creds)
    assert exc_info.value.status_code == 401


def test_verify_token_rejects_pre_mfa_scope():
    token = create_pre_mfa_token("admin")
    creds = FakeCredentials(token)
    with pytest.raises(HTTPException) as exc_info:
        verify_token(creds)
    assert exc_info.value.status_code == 401
    assert "MFA" in exc_info.value.detail


# ── require_role ──────────────────────────────────────────────────────────────

def test_require_role_passes():
    checker = require_role("admin", "nurse")
    token = {"role": "admin", "sub": "admin"}
    result = checker(token)
    assert result["role"] == "admin"


def test_require_role_fails():
    checker = require_role("admin")
    token = {"role": "nurse", "sub": "nurse"}
    with pytest.raises(HTTPException) as exc_info:
        checker(token)
    assert exc_info.value.status_code == 403


# ── _get_user ─────────────────────────────────────────────────────────────────

def test_get_user_from_memory():
    user = _get_user("admin")
    assert user is not None
    assert user["role"] == "admin"


def test_get_user_missing_returns_none():
    user = _get_user("nonexistent_user_xyz")
    assert user is None


def test_get_user_with_db_none():
    user = _get_user("nurse", db=None)
    assert user is not None
    assert user["role"] == "nurse"


# ── login ──────────────────────────────────────────────────────────────────────

def test_login_success():
    req = LoginRequest(username="admin", password="mediscan2026")
    result = login(req)
    assert result.access_token is not None
    assert result.role == "admin"
    assert result.mfa_required is False


def test_login_wrong_user():
    req = LoginRequest(username="nobody", password="pass")
    with pytest.raises(HTTPException) as exc_info:
        login(req)
    assert exc_info.value.status_code == 401


def test_login_wrong_password():
    req = LoginRequest(username="admin", password="wrongpass")
    with pytest.raises(HTTPException) as exc_info:
        login(req)
    assert exc_info.value.status_code == 401


def test_login_mfa_required_when_enabled():
    # Enable MFA on a copy of the user
    original = auth.USERS_DB["admin"].copy()
    auth.USERS_DB["admin"]["mfa_enabled"] = True
    try:
        req = LoginRequest(username="admin", password="mediscan2026")
        result = login(req)
        # No TOTP → should return pre-MFA token
        assert result.mfa_required is True
    finally:
        auth.USERS_DB["admin"] = original


def test_login_mfa_invalid_code():
    original = auth.USERS_DB["admin"].copy()
    auth.USERS_DB["admin"]["mfa_enabled"] = True
    try:
        req = LoginRequest(username="admin", password="mediscan2026", totp_code="000000")
        with pytest.raises(HTTPException) as exc_info:
            login(req)
        assert exc_info.value.status_code == 401
        assert "MFA" in exc_info.value.detail
    finally:
        auth.USERS_DB["admin"] = original


# ── setup_mfa ─────────────────────────────────────────────────────────────────

def test_setup_mfa_returns_qr():
    result = setup_mfa("admin")
    assert result.secret is not None
    assert result.qr_code_base64 is not None
    assert len(result.backup_codes) == 8


def test_setup_mfa_unknown_user():
    with pytest.raises(HTTPException) as exc_info:
        setup_mfa("unknownxyz")
    assert exc_info.value.status_code == 404


# ── enable_mfa / disable_mfa ──────────────────────────────────────────────────

def test_enable_mfa_invalid_code():
    result = enable_mfa("admin", "000000")
    assert result is False


def test_enable_mfa_unknown_user():
    result = enable_mfa("nosuchuser", "000000")
    assert result is False


def test_disable_mfa_success():
    result = disable_mfa("admin")
    assert result is True


def test_disable_mfa_unknown_user():
    result = disable_mfa("nosuchuser")
    assert result is False
