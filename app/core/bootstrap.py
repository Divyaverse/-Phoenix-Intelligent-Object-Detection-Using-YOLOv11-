"""
System bootstrapping service for PHOENIX.
Safely creates default organizations and seeds initial role-based user accounts
with Argon2id password hashes into the database if the users table is uninitialized.
"""

from datetime import datetime, timezone
import logging
import os
from typing import Optional
from app.core.security import hash_password
from app.db.repositories import (
    SQLiteAuditEventRepository,
    SQLiteOrganizationRepository,
    SQLiteUserRepository,
)
from app.domain.enums import UserRole
from app.domain.models import AuditEvent, Organization, User

logger = logging.getLogger("phoenix.bootstrap")


def bootstrap_database_users() -> None:
    """
    Ensure the default organization and seed role accounts exist in the database.
    Does not overwrite existing user accounts or alter existing passwords.
    """
    org_repo = SQLiteOrganizationRepository()
    user_repo = SQLiteUserRepository()
    audit_repo = SQLiteAuditEventRepository()

    # 1. Ensure default organization
    default_org_id = os.getenv("PHOENIX_DEFAULT_ORG_ID", "org-phoenix-main")
    default_org_name = os.getenv("PHOENIX_DEFAULT_ORG_NAME", "PHOENIX Autonomous Command")
    if not org_repo.get(default_org_id):
        org = Organization(
            organization_id=default_org_id,
            name=default_org_name,
            created_at=datetime.now(timezone.utc),
        )
        org_repo.save(org)
        logger.info(f"Bootstrapped organization: {default_org_name} ({default_org_id})")

    # 2. Check if users already exist
    if user_repo.count() > 0:
        return

    # 3. Seed initial role accounts using secure Argon2id hashes
    seed_accounts = [
        {
            "user_id": "usr-admin-01",
            "email": os.getenv("PHOENIX_SUPERADMIN_EMAIL", "admin@phoenix.local"),
            "password": os.getenv("PHOENIX_SUPERADMIN_PASSWORD", "AdminPass123!"),
            "full_name": os.getenv("PHOENIX_SUPERADMIN_NAME", "System SuperAdmin"),
            "role": UserRole.SUPERADMIN,
        },
        {
            "user_id": "usr-mgr-01",
            "email": os.getenv("PHOENIX_MANAGER_EMAIL", "manager@phoenix.local"),
            "password": os.getenv("PHOENIX_MANAGER_PASSWORD", "ManagerPass123!"),
            "full_name": os.getenv("PHOENIX_MANAGER_NAME", "Facility Manager"),
            "role": UserRole.BUILDING_MANAGER,
        },
        {
            "user_id": "usr-resp-01",
            "email": os.getenv("PHOENIX_RESPONDER_EMAIL", "responder@phoenix.local"),
            "password": os.getenv("PHOENIX_RESPONDER_PASSWORD", "ResponderPass123!"),
            "full_name": os.getenv("PHOENIX_RESPONDER_NAME", "Emergency First Responder"),
            "role": UserRole.FIRST_RESPONDER,
        },
        {
            "user_id": "usr-occ-01",
            "email": os.getenv("PHOENIX_OCCUPANT_EMAIL", "occupant@phoenix.local"),
            "password": os.getenv("PHOENIX_OCCUPANT_PASSWORD", "OccupantPass123!"),
            "full_name": os.getenv("PHOENIX_OCCUPANT_NAME", "Building Occupant"),
            "role": UserRole.OCCUPANT,
        },
    ]

    for acc in seed_accounts:
        argon2_hash = hash_password(acc["password"], algorithm="argon2id")
        user = User(
            user_id=acc["user_id"],
            organization_id=default_org_id,
            email=acc["email"],
            hashed_password=argon2_hash,
            full_name=acc["full_name"],
            role=acc["role"],
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        user_repo.save(user)

        # Audit bootstrap action
        audit_repo.record_event(
            AuditEvent(
                audit_id=f"aud-bootstrap-{acc['user_id']}",
                timestamp=datetime.now(timezone.utc),
                organization_id=default_org_id,
                user_id="SYSTEM_BOOTSTRAP",
                action="USER_BOOTSTRAPPED",
                entity_type="User",
                entity_id=acc["user_id"],
                after_state={"email": acc["email"], "role": acc["role"].value},
                reason="Initial system role seeding",
            ),
            idempotency_key=f"idemp-bootstrap-{acc['user_id']}",
        )
        logger.info(f"Bootstrapped {acc['role'].value} account: {acc['email']}")
