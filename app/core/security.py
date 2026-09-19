"""
VaidyaMD HMS — Enterprise Security, Cryptography & Authentication Utilities
"""

import base64
import hashlib
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Any
from jose import jwt, JWTError
from cryptography.fernet import Fernet
from app.config import settings

# --- PII Symmetric Encryption Setup ---
def _get_fernet_cipher() -> Fernet:
    """Derive a URL-safe base64-encoded 32-byte key for Fernet symmetric encryption from JWT secret."""
    key_bytes = hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest()
    urlsafe_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(urlsafe_key)

_cipher = _get_fernet_cipher()


def encrypt_pii(plain_text: Optional[str]) -> Optional[str]:
    """Encrypt sensitive PII string (e.g. Aadhaar, PAN, SSN) using AES-128-CBC/Fernet."""
    if not plain_text:
        return None
    try:
        # Check if already encrypted with Fernet (starts with gAAAAA)
        if plain_text.startswith("gAAAAA"):
            return plain_text
        return _cipher.encrypt(plain_text.strip().encode("utf-8")).decode("utf-8")
    except Exception as e:
        print(f"⚠️ Encryption warning: {e}")
        return plain_text


def decrypt_pii(cipher_text: Optional[str]) -> Optional[str]:
    """Decrypt sensitive PII string."""
    if not cipher_text:
        return None
    try:
        if not cipher_text.startswith("gAAAAA"):
            return cipher_text
        return _cipher.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        return cipher_text


def mask_pii(val: Optional[str], visible_digits: int = 4) -> Optional[str]:
    """Mask PII (e.g. XXXX-XXXX-1234). Decrypts first if ciphertext."""
    if not val:
        return None
    raw = decrypt_pii(val) or val
    clean = raw.replace("-", "").replace(" ", "").strip()
    if len(clean) <= visible_digits:
        return "****"
    return f"XXXX-XXXX-{clean[-visible_digits:]}"


# --- Password Hashing via Direct Bcrypt ---
def hash_password(plain_password: str) -> str:
    """Hash password using bcrypt with automatic salt."""
    # Bcrypt limit is 72 bytes
    pwd_bytes = plain_password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify plain password against hashed password using bcrypt.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        if hashed_password.startswith(("$2b$", "$2a$", "$2y$")):
            return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
        return False
    except Exception as e:
        print(f"⚠️ Password verification error: {e}")
        return False


# --- JWT Token Utilities ---
def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT token."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
