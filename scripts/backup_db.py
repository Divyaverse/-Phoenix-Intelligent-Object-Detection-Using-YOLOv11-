"""
Phoenix Safe Database Backup Utility
Supports SQLite (using atomic sqlite3.backup API) and PostgreSQL (via pg_dump).
Generates SHA-256 integrity checksums, validates integrity, and manages retention.
"""

import os
import sys
import argparse
import hashlib
import sqlite3
import subprocess
import shutil
import gzip
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


def backup_sqlite(db_path: Path, output_dir: Path, compress: bool = False) -> tuple[Path, str, int]:
    if not db_path.exists():
        raise FileNotFoundError(f"Source database file not found: {db_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"phoenix_backup_{timestamp}.db"
    backup_path = output_dir / backup_filename

    print(f"[*] Starting atomic SQLite backup from {db_path} to {backup_path}...")

    # Use SQLite online backup API for ACID safety during active connections
    src_conn = sqlite3.connect(str(db_path))
    dst_conn = sqlite3.connect(str(backup_path))
    try:
        with dst_conn:
            src_conn.backup(dst_conn, pages=100, progress=None)
    finally:
        dst_conn.close()
        src_conn.close()

    # Integrity verification
    verify_conn = sqlite3.connect(str(backup_path))
    try:
        cursor = verify_conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if not result or result[0] != "ok":
            backup_path.unlink(missing_ok=True)
            raise RuntimeError(f"Database backup failed integrity check: {result}")
        print("[+] Backup integrity verified (PRAGMA integrity_check: ok).")
    finally:
        verify_conn.close()

    # Optional compression
    final_backup_path = backup_path
    if compress:
        compressed_path = output_dir / f"{backup_filename}.gz"
        print(f"[*] Compressing backup to {compressed_path}...")
        with open(backup_path, "rb") as f_in, gzip.open(compressed_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        backup_path.unlink()
        final_backup_path = compressed_path

    # Generate checksum
    checksum = compute_sha256(final_backup_path)
    checksum_file = final_backup_path.with_name(f"{final_backup_path.name}.sha256")
    checksum_file.write_text(f"{checksum}  {final_backup_path.name}\n", encoding="utf-8")

    size_bytes = final_backup_path.stat().st_size
    return final_backup_path, checksum, size_bytes


def backup_postgres(db_url: str, output_dir: Path) -> tuple[Path, str, int]:
    parsed = urlparse(db_url)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"phoenix_backup_{timestamp}.sql"
    backup_path = output_dir / backup_filename

    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password

    cmd = [
        "pg_dump",
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", parsed.username or "postgres",
        "-F", "c",  # custom pg_dump archive format
        "-b",
        "-v",
        "-f", str(backup_path),
        parsed.path.lstrip("/"),
    ]

    print(f"[*] Executing PostgreSQL dump to {backup_path}...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr}")

    checksum = compute_sha256(backup_path)
    checksum_file = backup_path.with_name(f"{backup_path.name}.sha256")
    checksum_file.write_text(f"{checksum}  {backup_path.name}\n", encoding="utf-8")

    size_bytes = backup_path.stat().st_size
    return backup_path, checksum, size_bytes


def prune_backups(output_dir: Path, keep_count: int):
    if keep_count <= 0:
        return
    backups = sorted(
        [p for p in output_dir.glob("phoenix_backup_*") if not p.name.endswith(".sha256")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if len(backups) > keep_count:
        to_delete = backups[keep_count:]
        for p in to_delete:
            print(f"[*] Pruning old backup: {p.name}")
            p.unlink(missing_ok=True)
            sha_file = p.with_name(f"{p.name}.sha256")
            sha_file.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Phoenix Database Backup Utility")
    parser.add_argument("--dest-dir", type=str, default="./backups", help="Target backup directory")
    parser.add_argument("--compress", action="store_true", help="Compress backup using gzip")
    parser.add_argument("--keep", type=int, default=10, help="Number of recent backups to retain")
    args = parser.parse_args()

    dest_dir = Path(args.dest_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    db_url = settings.DATABASE_URL
    print(f"[*] Phoenix Database Backup - Target URL: {db_url}")

    if db_url.startswith("sqlite"):
        # Extract sqlite path
        raw_path = db_url.replace("sqlite:///", "")
        if raw_path.startswith("./"):
            raw_path = raw_path[2:]
        sqlite_path = Path(raw_path)
        if not sqlite_path.is_absolute():
            sqlite_path = PROJECT_ROOT / sqlite_path

        backup_file, checksum, size = backup_sqlite(sqlite_path, dest_dir, compress=args.compress)
    elif db_url.startswith("postgresql"):
        backup_file, checksum, size = backup_postgres(db_url, dest_dir)
    else:
        raise ValueError(f"Unsupported database scheme in URL: {db_url}")

    prune_backups(dest_dir, args.keep)

    print("\n" + "=" * 60)
    print("BACKUP COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print(f"File:     {backup_file}")
    print(f"Size:     {size:,} bytes ({size / (1024 * 1024):.2f} MB)")
    print(f"SHA-256:  {checksum}")
    print("=" * 60)


if __name__ == "__main__":
    main()
