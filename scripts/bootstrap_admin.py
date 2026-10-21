#!/usr/bin/env python3
"""
CLI Script to securely create or update a SuperAdmin user in PHOENIX.
Usage:
    python scripts/bootstrap_admin.py --email admin@example.com --password "MySecretPass123!" --name "Lead Admin"
    Or via environment variables:
    PHOENIX_SUPERADMIN_EMAIL=admin@example.com PHOENIX_SUPERADMIN_PASSWORD=... python scripts/bootstrap_admin.py
"""

import argparse
from datetime import datetime, timezone
import os
import sys
import uuid

# Ensure root dir in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.security import hash_password
from app.db.repositories import SQLiteOrganizationRepository, SQLiteUserRepository, SQLiteAuditEventRepository
from app.domain.enums import UserRole
from app.domain.models import AuditEvent, Organization, User


def main():
    parser = argparse.ArgumentParser(description="Bootstrap PHOENIX SuperAdmin Account")
    parser.add_argument("--email", default=os.getenv("PHOENIX_SUPERADMIN_EMAIL"), help="SuperAdmin Email")
    parser.add_argument("--password", default=os.getenv("PHOENIX_SUPERADMIN_PASSWORD"), help="SuperAdmin Password")
    parser.add_argument("--name", default=os.getenv("PHOENIX_SUPERADMIN_NAME", "System SuperAdmin"), help="Full name")
    parser.add_argument("--org-id", default=os.getenv("PHOENIX_DEFAULT_ORG_ID", "org-phoenix-main"), help="Organization ID")
    parser.add_argument("--org-name", default=os.getenv("PHOENIX_DEFAULT_ORG_NAME", "PHOENIX Autonomous Command"), help="Organization Name")
    args = parser.parse_args()

    if not args.email or not args.password:
        print("Error: Both --email and --password (or env PHOENIX_SUPERADMIN_EMAIL/PHOENIX_SUPERADMIN_PASSWORD) are required.")
        sys.exit(1)

    org_repo = SQLiteOrganizationRepository()
    user_repo = SQLiteUserRepository()
    audit_repo = SQLiteAuditEventRepository()

    # Ensure organization
    if not org_repo.get(args.org_id):
        org = Organization(
            organization_id=args.org_id,
            name=args.org_name,
            created_at=datetime.now(timezone.utc),
        )
        org_repo.save(org)
        print(f"Created organization: {args.org_name} ({args.org_id})")

    # Check if user already exists
    existing = user_repo.find_by_email(args.email)
    user_id = existing.user_id if existing else f"usr-admin-{uuid.uuid4().hex[:8]}"
    argon2_hash = hash_password(args.password, algorithm="argon2id")

    user = User(
        user_id=user_id,
        organization_id=args.org_id,
        email=args.email.lower(),
        hashed_password=argon2_hash,
        full_name=args.name,
        role=UserRole.SUPERADMIN,
        is_active=True,
        created_at=existing.created_at if existing else datetime.now(timezone.utc),
    )
    user_repo.save(user)

    audit_repo.record_event(
        AuditEvent(
            audit_id=f"aud-cli-bootstrap-{user_id}-{int(datetime.now(timezone.utc).timestamp())}",
            timestamp=datetime.now(timezone.utc),
            organization_id=args.org_id,
            user_id="CLI_BOOTSTRAP",
            action="SUPERADMIN_PROVISIONED",
            entity_type="User",
            entity_id=user_id,
            after_state={"email": args.email.lower(), "role": "superadmin"},
            reason="Operator manual bootstrap",
        )
    )
    print(f"Successfully provisioned SuperAdmin user: {args.email} (ID: {user_id}) with Argon2id.")


if __name__ == "__main__":
    main()
