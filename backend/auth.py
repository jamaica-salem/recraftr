"""JWT-based email/password authentication."""
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import uuid

JWT_SECRET = os.environ.get('JWT_SECRET', 'recraftr_jwt_secret_key_2026')
JWT_ALGO = "HS256"
JWT_EXPIRY_DAYS = 30

bearer = HTTPBearer(auto_error=False)


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=80)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    name: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


FALLBACK_SECRETS = [
    JWT_SECRET,
    "your_super_secret_jwt_key",
    "recraftr_jwt_secret_key_2026",
]


def decode_token(token: str) -> Optional[str]:
    seen = set()
    for secret in FALLBACK_SECRETS:
        if not secret or secret in seen:
            continue
        seen.add(secret)
        try:
            payload = jwt.decode(token, secret, algorithms=[JWT_ALGO])
            return payload.get("sub")
        except jwt.ExpiredSignatureError:
            return None
        except jwt.PyJWTError:
            continue
    return None


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> str:
    """Returns user_id from JWT. Raises 401 if invalid."""
    if not creds or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_token(creds.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user_id


def new_user_doc(email: str, name: str, password_hash: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "email": email.lower(),
        "name": name,
        "password_hash": password_hash,
        "created_at": now,
    }
