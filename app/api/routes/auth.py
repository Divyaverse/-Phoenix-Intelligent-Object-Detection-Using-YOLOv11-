"""
Authentication and User Management API routes for PHOENIX.
Persists users and revocable sessions securely with Argon2id hashing and token rotation.
"""

from datetime import datetime, timedelta, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import get_current_active_user, get_current_user_payload, require_role
from app.api.schemas.contracts import (
    CreateUserRequest,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
    UpdateUserStatusRequest,
    UserResponse,
)
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.repositories import (
    SQLiteAuditEventRepository,
    SQLiteAuthSessionRepository,
    SQLiteUserRepository,
)
from app.domain.enums import UserRole
from app.domain.models import AuditEvent, User

router = APIRouter(prefix="/auth", tags=["Auth"])

user_repo = SQLiteUserRepository()
session_repo = SQLiteAuthSessionRepository()
audit_repo = SQLiteAuditEventRepository()


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, req: Request) -> TokenResponse:
    """
    Authenticate user against persistent database, return signed JWT access token
    and a revocable refresh token, storing the hashed session record.
    """
    user = user_repo.find_by_email(request.email.lower())
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email credentials or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact an administrator.",
        )

    token_expire = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        subject=user.user_id,
        role=user.role.value,
        organization_id=user.organization_id,
        expires_delta=token_expire,
    )

    # Generate revocable refresh token (30 days validity)
    raw_refresh_token, refresh_hash = create_refresh_token()
    session_id = f"sess_{uuid.uuid4().hex}"
    refresh_expires_at = datetime.now(timezone.utc) + timedelta(days=getattr(settings, "refresh_token_expire_days", 30))

    client_ip = req.client.host if req.client else None
    user_agent = req.headers.get("user-agent")

    session_repo.create_session(
        session_id=session_id,
        user_id=user.user_id,
        token_hash=refresh_hash,
        expires_at=refresh_expires_at,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    # Record login audit event
    audit_repo.record_event(
        AuditEvent(
            audit_id=f"aud-login-{user.user_id}-{int(datetime.now(timezone.utc).timestamp())}",
            timestamp=datetime.now(timezone.utc),
            organization_id=user.organization_id,
            user_id=user.user_id,
            action="USER_LOGIN_SUCCESS",
            entity_type="User",
            entity_id=user.user_id,
            reason=f"Authenticated from {client_ip or 'unknown IP'}",
        )
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.user_id,
        role=user.role,
        organization_id=user.organization_id,
        expires_in_seconds=int(token_expire.total_seconds()),
        refresh_token=raw_refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshTokenRequest, req: Request) -> TokenResponse:
    """
    Exchange valid refresh token for a new access token and rotated refresh token.
    Enforces token rotation and revocation verification.
    """
    token_hash = hash_refresh_token(request.refresh_token)
    session = session_repo.find_by_token_hash(token_hash)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    expires_at = datetime.fromisoformat(session["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        session_repo.revoke_session(session["session_id"])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )

    user = user_repo.find_by_id(session["user_id"])
    if not user or not user.is_active:
        session_repo.revoke_session(session["session_id"])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer active",
        )

    # Token Rotation: Revoke old refresh token
    session_repo.revoke_session(session["session_id"])

    # Issue new access token and new rotated refresh token
    token_expire = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        subject=user.user_id,
        role=user.role.value,
        organization_id=user.organization_id,
        expires_delta=token_expire,
    )

    new_raw_refresh, new_refresh_hash = create_refresh_token()
    new_session_id = f"sess_{uuid.uuid4().hex}"
    refresh_expires_at = datetime.now(timezone.utc) + timedelta(days=getattr(settings, "refresh_token_expire_days", 30))

    client_ip = req.client.host if req.client else None
    user_agent = req.headers.get("user-agent")

    session_repo.create_session(
        session_id=new_session_id,
        user_id=user.user_id,
        token_hash=new_refresh_hash,
        expires_at=refresh_expires_at,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.user_id,
        role=user.role,
        organization_id=user.organization_id,
        expires_in_seconds=int(token_expire.total_seconds()),
        refresh_token=new_raw_refresh,
    )


@router.post("/logout")
def logout(request: LogoutRequest = LogoutRequest(), payload: dict = Depends(get_current_user_payload)) -> dict:
    """
    Revoke current user session or all sessions on explicit logout.
    """
    user_id = payload.get("sub")
    revoked_count = 0

    if request.refresh_token:
        token_hash = hash_refresh_token(request.refresh_token)
        if session_repo.revoke_by_token_hash(token_hash):
            revoked_count += 1
    elif user_id:
        revoked_count = session_repo.revoke_all_user_sessions(user_id)

    if user_id:
        audit_repo.record_event(
            AuditEvent(
                audit_id=f"aud-logout-{user_id}-{int(datetime.now(timezone.utc).timestamp())}",
                timestamp=datetime.now(timezone.utc),
                organization_id=payload.get("org_id", "org-phoenix-main"),
                user_id=user_id,
                action="USER_LOGOUT",
                entity_type="User",
                entity_id=user_id,
                reason="User initiated logout",
            )
        )

    return {"status": "SUCCESS", "message": f"Successfully logged out. Revoked {revoked_count} active session(s)."}


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(user: User = Depends(get_current_active_user)) -> UserResponse:
    """
    Get profile information of the currently authenticated user.
    Never exposes hashed password or secrets.
    """
    return UserResponse(
        user_id=user.user_id,
        organization_id=user.organization_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


# --- Administrative User Management Endpoints (SuperAdmin Only) ---

@router.get("/users", response_model=list[UserResponse])
def list_users(
    payload: dict = Depends(require_role([UserRole.SUPERADMIN])),
) -> list[UserResponse]:
    """List all registered system users. Restricted to SuperAdmin."""
    users = user_repo.list_all()
    return [
        UserResponse(
            user_id=u.user_id,
            organization_id=u.organization_id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    req: CreateUserRequest,
    payload: dict = Depends(require_role([UserRole.SUPERADMIN])),
) -> UserResponse:
    """Create a new user with Argon2id password hashing. Restricted to SuperAdmin."""
    existing = user_repo.find_by_email(req.email.lower())
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{req.email}' already exists.",
        )

    org_id = req.organization_id or payload.get("org_id", "org-phoenix-main")
    user_id = f"usr-{uuid.uuid4().hex[:10]}"
    argon2_hash = hash_password(req.password, algorithm="argon2id")

    user = User(
        user_id=user_id,
        organization_id=org_id,
        email=req.email.lower(),
        hashed_password=argon2_hash,
        full_name=req.full_name,
        role=req.role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    user_repo.save(user)

    audit_repo.record_event(
        AuditEvent(
            audit_id=f"aud-user-create-{user_id}",
            timestamp=datetime.now(timezone.utc),
            organization_id=org_id,
            user_id=payload.get("sub"),
            action="USER_CREATED",
            entity_type="User",
            entity_id=user_id,
            after_state={"email": user.email, "role": user.role.value},
            reason="Created by administrator",
        )
    )

    return UserResponse(
        user_id=user.user_id,
        organization_id=user.organization_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.patch("/users/{user_id}/status", response_model=dict)
def update_user_status(
    user_id: str,
    req: UpdateUserStatusRequest,
    payload: dict = Depends(require_role([UserRole.SUPERADMIN])),
) -> dict:
    """Activate or deactivate user account and revoke sessions if deactivated. Restricted to SuperAdmin."""
    user = user_repo.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_repo.update_status(user_id, req.is_active)
    if not req.is_active:
        session_repo.revoke_all_user_sessions(user_id)

    audit_repo.record_event(
        AuditEvent(
            audit_id=f"aud-user-status-{user_id}-{int(datetime.now(timezone.utc).timestamp())}",
            timestamp=datetime.now(timezone.utc),
            organization_id=user.organization_id,
            user_id=payload.get("sub"),
            action="USER_STATUS_UPDATED",
            entity_type="User",
            entity_id=user_id,
            after_state={"is_active": req.is_active},
            reason="Status updated by administrator",
        )
    )

    return {"status": "SUCCESS", "user_id": user_id, "is_active": req.is_active}


@router.delete("/users/{user_id}", response_model=dict)
def delete_user(
    user_id: str,
    payload: dict = Depends(require_role([UserRole.SUPERADMIN])),
) -> dict:
    """Delete a user account and invalidate their sessions. Restricted to SuperAdmin."""
    user = user_repo.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent deleting self
    if user_id == payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete currently authenticated administrator account",
        )

    session_repo.revoke_all_user_sessions(user_id)
    user_repo.delete(user_id)

    audit_repo.record_event(
        AuditEvent(
            audit_id=f"aud-user-del-{user_id}-{int(datetime.now(timezone.utc).timestamp())}",
            timestamp=datetime.now(timezone.utc),
            organization_id=user.organization_id,
            user_id=payload.get("sub"),
            action="USER_DELETED",
            entity_type="User",
            entity_id=user_id,
            reason="Deleted by administrator",
        )
    )

    return {"status": "SUCCESS", "message": f"User {user_id} deleted successfully."}
