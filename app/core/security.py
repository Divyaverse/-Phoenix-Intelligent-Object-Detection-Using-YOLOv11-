"""
Security, authentication, Argon2id password hashing, and JWT token management for PHOENIX.
Enforces Argon2id hashing, revocable session tracking, and JWT claim verification.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets
from typing import Any, Optional
import jwt

try:
    import argon2
    _argon2_hasher = argon2.PasswordHasher(
        time_cost=2,
        memory_cost=65536,
        parallelism=2,
        hash_len=32,
        type=argon2.Type.ID,
    )
except ImportError:
    _argon2_hasher = None

from app.core.config import settings
from app.core.errors import UnauthorizedError


def hash_password(password: str, algorithm: str = "argon2id") -> str:
    """
    Hash password using Argon2id (OWASP recommended standard) by default.
    Falls back to PBKDF2-HMAC-SHA256 if argon2 is unavailable or if explicitly requested.
    """
    if algorithm == "argon2id" and _argon2_hasher is not None:
        return _argon2_hasher.hash(password)

    # Fallback or explicit PBKDF2
    salt_bytes = os.urandom(16)
    salt_hex = salt_bytes.hex()
    iterations = 100_000
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    )
    return f"pbkdf2_sha256${iterations}${salt_hex}${derived.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against stored hash format in constant time.
    Supports both modern Argon2id hashes and legacy PBKDF2-SHA256 hashes.
    """
    if not hashed_password or not plain_password:
        return False

    # Check Argon2id hash format
    if hashed_password.startswith("$argon2id$") or hashed_password.startswith("$argon2"):
        if _argon2_hasher is None:
            return False
        try:
            return _argon2_hasher.verify(hashed_password, plain_password)
        except Exception:
            return False

    # Check legacy PBKDF2 format
    if hashed_password.startswith("pbkdf2_sha256$"):
        try:
            parts = hashed_password.split("$")
            if len(parts) != 4:
                return False
            iterations = int(parts[1])
            salt_hex = parts[2]
            expected_hash = parts[3]

            derived = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                iterations,
            )
            return hmac.compare_digest(derived.hex(), expected_hash)
        except Exception:
            return False

    return False


def create_access_token(
    subject: str,
    role: str,
    organization_id: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Generate signed JWT access token containing subject user ID, role, and organization scope.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "org_id": organization_id,
        "token_use": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.
    Raises UnauthorizedError on expired or invalid tokens.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "role", "org_id"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Authentication token has expired")
    except jwt.InvalidTokenError as e:
        raise UnauthorizedError(f"Invalid authentication token: {str(e)}")


def create_refresh_token() -> tuple[str, str]:
    """
    Generate a high-entropy cryptographically secure refresh token.
    Returns: (raw_token_for_client, sha256_hash_for_database_storage)
    Raw token is never stored in the database.
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_refresh_token(raw_token)
    return raw_token, token_hash


def hash_refresh_token(raw_token: str) -> str:
    """Compute SHA-256 hash of refresh token for safe database lookups."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
