"""Supabase and JWT authentication module."""
import os
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import jwt
from jwt import PyJWKClient, PyJWKClientError
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None

logger = logging.getLogger("auth")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

JWT_SECRET = os.environ.get("JWT_SECRET", "recraftr_jwt_secret_key_2026")
JWT_ALGO = "HS256"
JWT_EXPIRY_DAYS = 30

bearer = HTTPBearer(auto_error=False)

# Initialize Supabase JWKS client for fast local token verification
_jwks_client: Optional[PyJWKClient] = None
if SUPABASE_URL:
    jwks_url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, max_cached_keys=16)
    except Exception as exc:
        logger.warning(f"Could not initialize PyJWKClient: {exc}")

# Initialize Supabase Python client for administrative or fallback operations
supabase_admin: Optional[Client] = None
if create_client and SUPABASE_URL and (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY):
    try:
        supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY)
    except Exception as exc:
        logger.warning(f"Could not initialize Supabase admin client: {exc}")


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
    """Create legacy local JWT token (used during transition)."""
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
    """
    Decodes and validates a JWT token.
    1. Checks Supabase JWKS (ES256/RS256)
    2. Fallback to Supabase GoTrue API (get_user)
    3. Fallback to legacy local HS256 JWT secrets
    Returns user UUID/ID or None if invalid.
    """
    if not token:
        return None

    # 1. Primary: Verify Supabase JWT via JWKS
    if _jwks_client:
        try:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256", "HS256"],
                options={"verify_aud": False},
            )
            sub = payload.get("sub")
            if sub:
                return str(sub)
        except Exception:
            pass

    # 2. Secondary fallback: Verify directly via Supabase Auth API
    if supabase_admin:
        try:
            user_resp = supabase_admin.auth.get_user(token)
            if user_resp and user_resp.user and user_resp.user.id:
                return str(user_resp.user.id)
        except Exception:
            pass

    # 3. Tertiary fallback: Legacy local HS256 tokens during transition
    seen = set()
    for secret in FALLBACK_SECRETS:
        if not secret or secret in seen:
            continue
        seen.add(secret)
        try:
            payload = jwt.decode(token, secret, algorithms=[JWT_ALGO])
            sub = payload.get("sub")
            if sub:
                return str(sub)
        except jwt.ExpiredSignatureError:
            return None
        except jwt.PyJWTError:
            continue

    return None


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> str:
    """Returns verified user_id from Bearer JWT. Raises 401 if invalid."""
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
