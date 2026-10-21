"""
End-to-End Pipeline Verification Script for PHOENIX.
Tests ingestion of videos/Main_video.mp4, runs genuine dual-model YOLOv11 perception,
and verifies database persistence across all core entities.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys

# Ensure root dir in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.video_service import VideoProcessingService
from app.db.sqlite import get_connection


async def main():
    print("=== STARTING END-TO-END PIPELINE VERIFICATION ===")
    service = VideoProcessingService()

    source_path = Path("videos/Main_video.mp4")
    if not source_path.is_file():
        print(f"Error: {source_path} does not exist!")
        sys.exit(1)

    print(f"1. Validating and storing video: {source_path}...")
    video_record = service.validate_and_store_video(
        source_file_path=source_path,
        original_filename="Main_video.mp4",
        user_id="usr-admin-01",
        organization_id="org-phoenix-main",
    )
    video_id = video_record["video_id"]
    print(f"   Video stored: ID={video_id}, Size={video_record['file_size_bytes']} bytes, SHA256={video_record['sha256_checksum'][:16]}...")

    print(f"2. Creating processing job for video {video_id}...")
    job_record = service.create_job(
        video_id=video_id,
        user_id="usr-admin-01",
        organization_id="org-phoenix-main",
    )
    job_id = job_record["job_id"]
    print(f"   Job created: ID={job_id}, Status={job_record['status']}")

    print(f"3. Executing real YOLOv11 perception & decision pipeline on {job_id} (sample stride=3)...")
    final_job = await service.execute_job(
        job_id=job_id,
        building_id="bldg-hq-01",
        floor_id="fl-01",
        camera_id="CAM-MAIN-01",
        stride_frames=3,
        generate_annotated_video=True,
    )
    print(f"   Execution finished with Status: {final_job['status']}")
    print(f"   Frames processed: {final_job['frames_processed']}")
    print(f"   Total detections: {final_job['detections_count']}")
    print(f"   Fire detected: {bool(final_job['fire_detected'])}, Smoke detected: {bool(final_job['smoke_detected'])}")
    print(f"   Max Risk Level: {final_job['max_risk_level']}")
    print(f"   Execution Time: {final_job['execution_time_seconds']}s")
    print(f"   Annotated Video Path: {final_job.get('annotated_video_path')}")

    print("\n4. Verifying Database Entity Persistence in SQLite (phoenix.db):")
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM video_sources WHERE video_id = ?", (video_id,))
    v_count = cur.fetchone()[0]
    print(f"   - video_sources record: {v_count} row (Expected: 1)")

    cur.execute("SELECT COUNT(*) FROM processing_jobs WHERE job_id = ?", (job_id,))
    j_count = cur.fetchone()[0]
    print(f"   - processing_jobs record: {j_count} row (Expected: 1)")

    cur.execute("SELECT COUNT(*) FROM detections WHERE job_id = ?", (job_id,))
    d_count = cur.fetchone()[0]
    print(f"   - detections records: {d_count} rows")

    cur.execute("SELECT COUNT(*) FROM video_frames WHERE job_id = ?", (job_id,))
    f_count = cur.fetchone()[0]
    print(f"   - video_frames records: {f_count} rows")

    cur.execute("SELECT COUNT(*) FROM temporal_analyses WHERE job_id = ?", (job_id,))
    t_count = cur.fetchone()[0]
    print(f"   - temporal_analyses records: {t_count} rows")

    cur.execute("SELECT COUNT(*) FROM risk_events WHERE job_id = ?", (job_id,))
    r_count = cur.fetchone()[0]
    print(f"   - risk_events records: {r_count} rows")

    cur.execute("SELECT COUNT(*), graph_version FROM route_recommendations WHERE job_id = ? GROUP BY graph_version", (job_id,))
    route_rows = cur.fetchall()
    print(f"   - route_recommendations records: {route_rows}")

    cur.execute("SELECT COUNT(*) FROM audit_events WHERE entity_id IN (?, ?)", (video_id, job_id))
    a_count = cur.fetchone()[0]
    print(f"   - audit_events records: {a_count} rows")

    assert v_count == 1, "Video record missing!"
    assert j_count == 1, "Job record missing!"
    assert d_count > 0, "No detections persisted for job!"
    assert f_count > 0, "No frame records persisted!"
    assert len(route_rows) > 0, "No route recommendation persisted!"
    assert a_count >= 2, "Audit events missing!"

    print("\n=== END-TO-END PIPELINE VERIFICATION PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    asyncio.run(main())
