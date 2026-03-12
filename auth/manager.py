"""
auth/manager.py — Security & Identity Manager
===============================================
Handles JWT generation, password hashing, and token validation.
Uses python-jose and passlib for industry-standard security.
"""

import uuid
from datetime import datetime, timedelta, UTC
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from config.settings import settings

# ── Security Config ──────────────────────────────────────────
# Argon2 is superior to bcrypt for modern auth
# Explicitly set bcrypt backend to 'bcrypt' to avoid passlib auto-detection issues
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__backend="bcrypt")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None

class SecurityManager:
    """
    Handles all cryptographic operations.
    """

    @staticmethod
    def hash_password(password: str) -> str:
        # Bcrypt has a 72-byte limit. Passlib usually handles this, 
        # but explicit truncation prevents library-level ValueError crashes.
        return pwd_context.hash(password[:72])

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        if not hashed_password:
            return False
        return pwd_context.verify(plain_password[:72], hashed_password)

    @staticmethod
    def create_access_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Optional[TokenData]:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            email: str = payload.get("email")
            if user_id is None:
                return None
            return TokenData(user_id=user_id, email=email)
        except JWTError:
            return None
