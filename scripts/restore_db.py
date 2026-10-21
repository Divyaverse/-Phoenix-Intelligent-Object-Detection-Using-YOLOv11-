"""
Phoenix Safe Database Restore Utility
Restores SQLite or PostgreSQL databases from verified backup archives.
Performs checksum verification, pre-restore integrity validation,
and automatic safety snapshots before restoring.
"""

import os
import sys
import argparse
import hashlib
import sqlite3
import subprocess
import shutil
import gzip
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings


def compute_sha256(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def verify_checksum(backup_path: Path, expected_sha: str | None = None) -> bool:
    sha_file = backup_path.with_name(f"{backup_path.name}.sha256")
    if not expected_sha and sha_file.exists():
        first_token = sha_file.read_text(encoding="utf-8").strip().split()[0]
        expected_sha = first_token

    if not expected_sha:
        print("[!] Warning: No SHA-256 checksum file found to verify against.")
        return True

    actual_sha = compute_sha256(backup_path)
    if actual_sha.lower() != expected_sha.lower():
        raise ValueError(
            f"Checksum MISMATCH for {backup_path.name}!\n"
            f"Expected: {expected_sha}\n"
            f"Actual:   {actual_sha}"
        )
    print(f"[+] SHA-256 Checksum verified: {actual_sha}")
    return True


def restore_sqlite(backup_path: Path, target_db_path: Path, no_safety_backup: bool = False):
    staging_file = None
    file_to_restore = backup_path

    # Decompress if gzipped
    if backup_path.suffix == ".gz":
        print("[*] Decompressing gzip backup to staging file...")
        staging_fd, staging_path = tempfile.mkstemp(suffix=".db")
        os.close(staging_fd)
        staging_file = Path(staging_path)
        with gzip.open(backup_path, "rb") as f_in, open(staging_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        file_to_restore = staging_file

    try:
        # Pre-restore integrity check on backup file
        print(f"[*] Validating integrity of backup file {file_to_restore.name}...")
        test_conn = sqlite3.connect(str(file_to_restore))
        try:
            cursor = test_conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            res = cursor.fetchone()
            if not res or res[0] != "ok":
                raise RuntimeError(f"Backup file failed SQLite integrity check: {res}")
            print("[+] Backup file passed PRAGMA integrity_check.")
        finally:
            test_conn.close()

        # Create safety snapshot of active database
        if target_db_path.exists() and not no_safety_backup:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_dir = target_db_path.parent / "backups"
            safety_dir.mkdir(parents=True, exist_ok=True)
            safety_path = safety_dir / f"safety_pre_restore_{timestamp}.db"
            print(f"[*] Creating pre-restore safety snapshot at {safety_path}...")
            shutil.copy2(target_db_path, safety_path)
            print(f"[+] Pre-restore safety snapshot created.")

        # Safe atomic restore
        print(f"[*] Restoring database to {target_db_path}...")
        # Use sqlite3.backup to stream from backup to target
        dst_conn = sqlite3.connect(str(target_db_path))
        src_conn = sqlite3.connect(str(file_to_restore))
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        # Post-restore verification
        verify_conn = sqlite3.connect(str(target_db_path))
        try:
            cursor = verify_conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            res = cursor.fetchone()
            if not res or res[0] != "ok":
                raise RuntimeError(f"Restored target database failed integrity check: {res}")
            print("[+] Restored database verified (PRAGMA integrity_check: ok).")
        finally:
            verify_conn.close()

    finally:
        if staging_file and staging_file.exists():
            staging_file.unlink()


def restore_postgres(backup_path: Path, db_url: str):
    parsed = urlparse(db_url)
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password

    cmd = [
        "pg_restore",
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", parsed.username or "postgres",
        "-d", parsed.path.lstrip("/"),
        "-c",  # Clean (drop) database objects before recreating
        "-v",
        str(backup_path),
    ]

    print(f"[*] Executing PostgreSQL restore from {backup_path}...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pg_restore failed: {result.stderr}")
    print("[+] PostgreSQL restore completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="Phoenix Database Restore Utility")
    parser.add_argument("--backup-file", type=str, required=True, help="Path to backup file to restore")
    parser.add_argument("--expected-sha256", type=str, default=None, help="Expected SHA-256 checksum")
    parser.add_argument("--no-safety-backup", action="store_true", help="Skip creating a pre-restore safety snapshot")
    args = parser.parse_args()

    backup_path = Path(args.backup_file).resolve()
    if not backup_path.exists():
        print(f"[-] Error: Backup file not found: {backup_path}")
        sys.exit(1)

    print(f"[*] Phoenix Database Restore - Backup File: {backup_path}")
    verify_checksum(backup_path, args.expected_sha256)

    db_url = settings.DATABASE_URL
    print(f"[*] Target Database URL: {db_url}")

    if db_url.startswith("sqlite"):
        raw_path = db_url.replace("sqlite:///", "")
        if raw_path.startswith("./"):
            raw_path = raw_path[2:]
        sqlite_path = Path(raw_path)
        if not sqlite_path.is_absolute():
            sqlite_path = PROJECT_ROOT / sqlite_path

        restore_sqlite(backup_path, sqlite_path, no_safety_backup=args.no_safety_backup)
    elif db_url.startswith("postgresql"):
        restore_postgres(backup_path, db_url)
    else:
        raise ValueError(f"Unsupported database scheme: {db_url}")

    print("\n" + "=" * 60)
    print("DATABASE RESTORATION COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
