"""
FastAPI Dependencies for Auth, RBAC, and Context Enforcement in PHOENIX.
"""

from typing import Annotated, Callable, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.domain.enums import UserRole

security_scheme = HTTPBearer(auto_error=False)


def get_current_user_payload(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    authorization: Optional[str] = Header(None),
) -> dict:
    """
    Extract and validate JWT token from Bearer header, Authorization header, or token query param.
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif request and request.query_params and "token" in request.query_params:
        token = request.query_params["token"]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
        return payload
    except UnauthorizedError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(allowed_roles: list[UserRole]) -> Callable:
    """
    Enforce backend RBAC server-side by checking the token claims against allowed roles.
    """
    def role_checker(payload: dict = Depends(get_current_user_payload)) -> dict:
        user_role_str = payload.get("role")
        try:
            user_role = UserRole(user_role_str)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid user role in token claim",
            )

        if user_role not in allowed_roles and user_role != UserRole.SUPERADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{user_role.value}' is not authorized for this resource",
            )
        return payload

    return role_checker


def get_current_active_user(payload: dict = Depends(get_current_user_payload)):
    """
    Look up user in persistent database and ensure account is active.
    """
    from app.db.repositories import SQLiteUserRepository
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject missing",
        )
    user = SQLiteUserRepository().find_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return user
