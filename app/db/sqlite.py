"""
SQLite Database Connection, Schema Initialization, and Transaction Management for PHOENIX.
Provides backward-compatible raw sqlite3 transactions alongside unified SQLAlchemy integration.
"""

import contextlib
import logging
import os
import sqlite3
from typing import Generator
from app.core.config import settings
from app.core.errors import PersistenceUnavailableError

logger = logging.getLogger("phoenix.db.sqlite")


def get_db_path() -> str:
    """Extract SQLite database file path from database_url setting."""
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    elif url.startswith("sqlite://"):
        return url.replace("sqlite://", "")
    return "phoenix.db"


def get_connection() -> sqlite3.Connection:
    """
    Connect to SQLite database with WAL mode and foreign key constraints enabled.
    """
    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn
    except sqlite3.Error as e:
        raise PersistenceUnavailableError(f"Failed to connect to SQLite database at {db_path}: {str(e)}")


get_db_connection = get_connection


@contextlib.contextmanager
def db_transaction() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager providing an atomic SQLite database transaction.
    Commits on success, rolls back on error.
    Does NOT claim persistence until transaction is committed.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise PersistenceUnavailableError(f"SQLite transaction failed and rolled back: {str(e)}")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def _safe_add_column(conn: sqlite3.Connection, table: str, col_def: str) -> None:
    """Safely add a column to an existing table if it does not already exist."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def};")
    except sqlite3.OperationalError:
        pass  # Column already exists


def init_db() -> None:
    """Initialize database tables according to PHOENIX Entity Data Architecture."""
    url = settings.database_url

    # If using SQLAlchemy for PostgreSQL or custom engine, also initialize SQLAlchemy metadata
    try:
        from app.db.session import init_db as sqlalchemy_init_db
        sqlalchemy_init_db()
    except Exception as e:
        logger.warning(f"SQLAlchemy metadata init warning: {e}")

    # For SQLite databases, ensure all raw SQLite tables, constraints, and migrations are applied
    if url.startswith("sqlite"):
        schema_sql = """
        CREATE TABLE IF NOT EXISTS organizations (
            organization_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'OCCUPANT',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (organization_id) REFERENCES organizations(organization_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS auth_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            device_info TEXT,
            ip_address TEXT,
            expires_at TEXT NOT NULL,
            is_revoked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            last_used_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS buildings (
            building_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (organization_id) REFERENCES organizations(organization_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS floors (
            floor_id TEXT PRIMARY KEY,
            building_id TEXT NOT NULL,
            floor_number INTEGER NOT NULL,
            name TEXT NOT NULL,
            width_meters REAL NOT NULL,
            height_meters REAL NOT NULL,
            floorplan_image_url TEXT,
            created_at TEXT,
            FOREIGN KEY (building_id) REFERENCES buildings(building_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS cameras (
            camera_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            building_id TEXT NOT NULL,
            floor_id TEXT NOT NULL,
            name TEXT NOT NULL,
            source_uri TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ONLINE',
            monitored_nodes_json TEXT,
            last_seen_at TEXT,
            calibration_id TEXT,
            created_at TEXT,
            FOREIGN KEY (organization_id) REFERENCES organizations(organization_id) ON DELETE CASCADE,
            FOREIGN KEY (building_id) REFERENCES buildings(building_id) ON DELETE CASCADE,
            FOREIGN KEY (floor_id) REFERENCES floors(floor_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS calibrations (
            calibration_id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL,
            building_id TEXT NOT NULL,
            floor_id TEXT NOT NULL,
            matrix_3x3_json TEXT NOT NULL,
            points_json TEXT,
            reprojection_error REAL NOT NULL DEFAULT 0.0,
            is_valid INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
            FOREIGN KEY (building_id) REFERENCES buildings(building_id) ON DELETE CASCADE,
            FOREIGN KEY (floor_id) REFERENCES floors(floor_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS floorplans (
            floorplan_id TEXT PRIMARY KEY,
            building_id TEXT NOT NULL,
            floor_id TEXT NOT NULL,
            name TEXT NOT NULL,
            image_url TEXT,
            image_width_px INTEGER NOT NULL DEFAULT 1000,
            image_height_px INTEGER NOT NULL DEFAULT 800,
            scale_reference_json TEXT,
            physical_width_meters REAL,
            physical_height_meters REAL,
            is_scale_calibrated INTEGER NOT NULL DEFAULT 0,
            regions_json TEXT,
            walls_json TEXT,
            doors_json TEXT,
            exits_json TEXT,
            nodes_json TEXT,
            edges_json TEXT,
            graph_version TEXT NOT NULL DEFAULT '1.0.0',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (building_id) REFERENCES buildings(building_id) ON DELETE CASCADE,
            FOREIGN KEY (floor_id) REFERENCES floors(floor_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS video_sources (
            video_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            uploader_user_id TEXT,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            mime_type TEXT NOT NULL,
            sha256_checksum TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'UPLOADED',
            fps REAL,
            duration_seconds REAL,
            resolution TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (organization_id) REFERENCES organizations(organization_id) ON DELETE CASCADE,
            FOREIGN KEY (uploader_user_id) REFERENCES users(user_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS processing_jobs (
            job_id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            building_id TEXT NOT NULL,
            floor_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            progress_pct REAL NOT NULL DEFAULT 0.0,
            current_frame INTEGER NOT NULL DEFAULT 0,
            total_frames INTEGER NOT NULL DEFAULT 0,
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            error_message TEXT,
            error_details_json TEXT,
            annotated_video_path TEXT,
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (video_id) REFERENCES video_sources(video_id) ON DELETE CASCADE,
            FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
            FOREIGN KEY (building_id) REFERENCES buildings(building_id) ON DELETE CASCADE,
            FOREIGN KEY (floor_id) REFERENCES floors(floor_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS video_frames (
            frame_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            video_id TEXT NOT NULL,
            frame_index INTEGER NOT NULL,
            timestamp_seconds REAL NOT NULL,
            frame_image_path TEXT,
            inference_latency_ms REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES processing_jobs(job_id) ON DELETE CASCADE,
            FOREIGN KEY (video_id) REFERENCES video_sources(video_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS detections (
            detection_id TEXT PRIMARY KEY,
            job_id TEXT,
            frame_id TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            class_name TEXT NOT NULL,
            confidence REAL NOT NULL,
            bbox_json TEXT NOT NULL,
            floor_point_json TEXT,
            model_version TEXT DEFAULT 'yolov11-dual',
            FOREIGN KEY (job_id) REFERENCES processing_jobs(job_id) ON DELETE CASCADE,
            FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS temporal_analyses (
            analysis_id TEXT PRIMARY KEY,
            job_id TEXT,
            camera_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            area_px2 REAL NOT NULL,
            delta_area_px2 REAL NOT NULL DEFAULT 0.0,
            dt_seconds REAL NOT NULL DEFAULT 0.0,
            growth_rate_px2_per_sec REAL NOT NULL DEFAULT 0.0,
            smoothed_growth_rate REAL NOT NULL DEFAULT 0.0,
            trend TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES processing_jobs(job_id) ON DELETE CASCADE,
            FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS risk_events (
            snapshot_id TEXT PRIMARY KEY,
            job_id TEXT,
            building_id TEXT NOT NULL,
            floor_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            global_risk_level TEXT NOT NULL,
            node_risks_json TEXT NOT NULL,
            active_hazards_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES processing_jobs(job_id) ON DELETE CASCADE,
            FOREIGN KEY (building_id) REFERENCES buildings(building_id) ON DELETE CASCADE,
            FOREIGN KEY (floor_id) REFERENCES floors(floor_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS incidents (
            incident_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            building_id TEXT NOT NULL,
            floor_id TEXT NOT NULL,
            status TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            hazard_origin_node TEXT,
            affected_nodes_json TEXT,
            declared_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY (organization_id) REFERENCES organizations(organization_id) ON DELETE CASCADE,
            FOREIGN KEY (building_id) REFERENCES buildings(building_id) ON DELETE CASCADE,
            FOREIGN KEY (floor_id) REFERENCES floors(floor_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS route_recommendations (
            route_id TEXT PRIMARY KEY,
            job_id TEXT,
            building_id TEXT NOT NULL,
            floor_id TEXT NOT NULL,
            graph_version TEXT NOT NULL DEFAULT '1.0.0',
            origin_node TEXT NOT NULL,
            destination_node TEXT NOT NULL,
            path_nodes_json TEXT NOT NULL,
            path_edges_json TEXT NOT NULL,
            status TEXT NOT NULL,
            eta_seconds REAL NOT NULL,
            total_cost REAL NOT NULL,
            cost_breakdown_json TEXT NOT NULL,
            algorithm_version TEXT NOT NULL,
            calculation_assumptions_json TEXT,
            is_degraded INTEGER NOT NULL DEFAULT 0,
            computed_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES processing_jobs(job_id) ON DELETE CASCADE,
            FOREIGN KEY (building_id) REFERENCES buildings(building_id) ON DELETE CASCADE,
            FOREIGN KEY (floor_id) REFERENCES floors(floor_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            audit_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            organization_id TEXT NOT NULL,
            user_id TEXT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            before_state_json TEXT,
            after_state_json TEXT,
            reason TEXT,
            metadata_json TEXT,
            idempotency_key TEXT UNIQUE,
            FOREIGN KEY (organization_id) REFERENCES organizations(organization_id) ON DELETE CASCADE
        );

        """
        with db_transaction() as conn:
            conn.executescript(schema_sql)

            # Safely migrate existing tables if any columns are missing BEFORE creating indexes
            _safe_add_column(conn, "detections", "job_id TEXT")
            _safe_add_column(conn, "detections", "model_version TEXT DEFAULT 'yolov11-dual'")
            _safe_add_column(conn, "floorplans", "graph_version TEXT DEFAULT '1.0.0'")
            _safe_add_column(conn, "cameras", "calibration_id TEXT")
            _safe_add_column(conn, "cameras", "created_at TEXT")
            _safe_add_column(conn, "buildings", "created_at TEXT")
            _safe_add_column(conn, "floors", "created_at TEXT")
            _safe_add_column(conn, "route_recommendations", "job_id TEXT")
            _safe_add_column(conn, "route_recommendations", "graph_version TEXT DEFAULT '1.0.0'")
            _safe_add_column(conn, "route_recommendations", "calculation_assumptions_json TEXT")
            _safe_add_column(conn, "users", "updated_at TEXT")
            _safe_add_column(conn, "video_sources", "original_filename TEXT")
            _safe_add_column(conn, "video_sources", "stored_filename TEXT")
            _safe_add_column(conn, "video_sources", "uploaded_by_user_id TEXT")
            _safe_add_column(conn, "video_sources", "width INTEGER")
            _safe_add_column(conn, "video_sources", "height INTEGER")
            _safe_add_column(conn, "video_sources", "error_message TEXT")
            _safe_add_column(conn, "processing_jobs", "current_stage TEXT DEFAULT 'INITIALIZING'")
            _safe_add_column(conn, "processing_jobs", "frames_processed INTEGER DEFAULT 0")
            _safe_add_column(conn, "processing_jobs", "detections_count INTEGER DEFAULT 0")
            _safe_add_column(conn, "processing_jobs", "fire_detected INTEGER DEFAULT 0")
            _safe_add_column(conn, "processing_jobs", "smoke_detected INTEGER DEFAULT 0")
            _safe_add_column(conn, "processing_jobs", "max_risk_level TEXT DEFAULT 'LOW'")
            _safe_add_column(conn, "processing_jobs", "progress_percent REAL DEFAULT 0.0")
            _safe_add_column(conn, "processing_jobs", "execution_time_seconds REAL")
            _safe_add_column(conn, "processing_jobs", "output_metadata_json TEXT")
            _safe_add_column(conn, "processing_jobs", "created_by_user_id TEXT")
            _safe_add_column(conn, "processing_jobs", "organization_id TEXT")
            _safe_add_column(conn, "video_frames", "detections_count INTEGER DEFAULT 0")
            _safe_add_column(conn, "video_frames", "has_hazard INTEGER DEFAULT 0")
            _safe_add_column(conn, "calibrations", "condition_number REAL DEFAULT 1.0")
            _safe_add_column(conn, "auth_sessions", "user_agent TEXT")
            _safe_add_column(conn, "auth_sessions", "device_info TEXT")
            _safe_add_column(conn, "auth_sessions", "ip_address TEXT")
            _safe_add_column(conn, "auth_sessions", "revoked_at TEXT")
            _safe_add_column(conn, "auth_sessions", "last_used_at TEXT")

            # Performance Indexes
            indexes_sql = """
            CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id);
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON auth_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_hash ON auth_sessions(token_hash);
            CREATE INDEX IF NOT EXISTS idx_jobs_video ON processing_jobs(video_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON processing_jobs(status);
            CREATE INDEX IF NOT EXISTS idx_frames_job ON video_frames(job_id, frame_index);
            CREATE INDEX IF NOT EXISTS idx_detections_job ON detections(job_id);
            CREATE INDEX IF NOT EXISTS idx_detections_cam ON detections(camera_id);
            CREATE INDEX IF NOT EXISTS idx_detections_class ON detections(class_name);
            CREATE INDEX IF NOT EXISTS idx_temporal_job ON temporal_analyses(job_id);
            CREATE INDEX IF NOT EXISTS idx_risk_job ON risk_events(job_id);
            CREATE INDEX IF NOT EXISTS idx_routes_bldg_origin ON route_recommendations(building_id, origin_node);
            CREATE INDEX IF NOT EXISTS idx_routes_job ON route_recommendations(job_id);
            """
            conn.executescript(indexes_sql)

            # Ensure default organization, building, floor, and cameras exist for foreign key integrity
            conn.execute("""
            INSERT OR IGNORE INTO organizations (organization_id, name, created_at)
            VALUES ('org-phoenix-main', 'Phoenix Main Organization', datetime('now'));
            """)
            conn.execute("""
            INSERT OR IGNORE INTO buildings (building_id, organization_id, name, address, created_at)
            VALUES ('bldg-hq-01', 'org-phoenix-main', 'Phoenix Innovation Center', '100 Tech Blvd, Building A', datetime('now'));
            """)
            conn.execute("""
            INSERT OR IGNORE INTO floors (floor_id, building_id, floor_number, name, width_meters, height_meters, created_at)
            VALUES ('fl-01', 'bldg-hq-01', 1, 'Ground Floor Main Lobby', 50.0, 40.0, datetime('now'));
            """)
            conn.execute("""
            INSERT OR IGNORE INTO cameras (
                camera_id, organization_id, building_id, floor_id, name, source_uri, status, created_at
            ) VALUES (
                'CAM-UPLOAD', 'org-phoenix-main', 'bldg-hq-01', 'fl-01',
                'Uploaded Video Stream (Uncalibrated)', '/videos/uploaded', 'ONLINE', datetime('now')
            );
            """)
