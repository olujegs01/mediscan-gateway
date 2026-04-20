import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

SECRET_KEY = os.getenv("SECRET_KEY", "mediscan-dev-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12

security = HTTPBearer()

# In production replace with a real database
USERS_DB = {
    "admin": {
        "password_hash": bcrypt.hashpw(b"mediscan2026", bcrypt.gensalt()).decode(),
        "role": "admin",
        "name": "System Admin",
    },
    "nurse": {
        "password_hash": bcrypt.hashpw(b"nurse2026", bcrypt.gensalt()).decode(),
        "role": "nurse",
        "name": "Triage Nurse",
    },
    "physician": {
        "password_hash": bcrypt.hashpw(b"physician2026", bcrypt.gensalt()).decode(),
        "role": "physician",
        "name": "On-Call Physician",
    },
}


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    name: str


def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
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
    token = create_token(data.username, user["role"])
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        name=user["name"],
    )
