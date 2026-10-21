"""
Unit tests for security, password hashing, and JWT token authentication.
"""

from datetime import timedelta
import pytest
from app.core.errors import UnauthorizedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.domain.enums import UserRole


def test_password_hashing_and_verification():
    """Verify Argon2id and PBKDF2 password hashing is robust and verifiable."""
    raw_pwd = "SecurePhoenixPassword123!"
    
    # Default Argon2id hashing
    argon2_hash = hash_password(raw_pwd)
    assert argon2_hash.startswith("$argon2id$")
    assert verify_password(raw_pwd, argon2_hash) is True
    assert verify_password("WrongPassword!", argon2_hash) is False
    assert verify_password("", argon2_hash) is False

    # Legacy PBKDF2 compatibility
    pbkdf2_hash = hash_password(raw_pwd, algorithm="pbkdf2")
    assert pbkdf2_hash.startswith("pbkdf2_sha256$100000$")
    assert verify_password(raw_pwd, pbkdf2_hash) is True
    assert verify_password("WrongPassword!", pbkdf2_hash) is False


def test_jwt_token_generation_and_decoding():
    """Verify JWT access token creation and claim extraction."""
    user_id = "usr_001"
    role = UserRole.FIRST_RESPONDER.value
    org_id = "org_city_safety"

    token = create_access_token(
        subject=user_id,
        role=role,
        organization_id=org_id,
        expires_delta=timedelta(minutes=15),
    )

    claims = decode_access_token(token)
    assert claims["sub"] == user_id
    assert claims["role"] == role
    assert claims["org_id"] == org_id
    assert "exp" in claims
    assert "iat" in claims


def test_jwt_token_expired_fails():
    """Verify expired JWT tokens raise UnauthorizedError."""
    token = create_access_token(
        subject="usr_test",
        role=UserRole.OCCUPANT.value,
        organization_id="org_test",
        expires_delta=timedelta(seconds=-10), # Expired 10 seconds ago
    )

    with pytest.raises(UnauthorizedError, match="expired"):
        decode_access_token(token)


def test_jwt_token_invalid_signature_fails():
    """Verify malformed or tampered tokens raise UnauthorizedError."""
    with pytest.raises(UnauthorizedError, match="Invalid authentication token"):
        decode_access_token("invalid.token.payload")
