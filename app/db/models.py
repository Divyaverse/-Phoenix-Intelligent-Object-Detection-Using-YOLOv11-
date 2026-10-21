"""
SQLAlchemy ORM Data Models for PHOENIX.
Supports SQLite and PostgreSQL with proper relationships, foreign keys, indexes, and constraints.
"""

from datetime import datetime, timezone
import json
from typing import Any, Optional
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class OrganizationModel(Base):
    """Tenant organization entity."""
    __tablename__ = "organizations"

    organization_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(String(64), nullable=False)

    users = relationship("UserModel", back_populates="organization", cascade="all, delete-orphan")
    buildings = relationship("BuildingModel", back_populates="organization", cascade="all, delete-orphan")


class UserModel(Base):
    """User account entity with role-based access control and account status."""
    __tablename__ = "users"

    user_id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(512), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="OCCUPANT")
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=True)

    organization = relationship("OrganizationModel", back_populates="users")
    sessions = relationship("AuthSessionModel", back_populates="user", cascade="all, delete-orphan")
    uploaded_videos = relationship("VideoSourceModel", back_populates="uploader")


class AuthSessionModel(Base):
    """Authenticated user session and revocable refresh token records."""
    __tablename__ = "auth_sessions"

    session_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, index=True)
    device_info = Column(String(255), nullable=True)
    user_agent = Column(String(255), nullable=True)
    ip_address = Column(String(64), nullable=True)
    expires_at = Column(String(64), nullable=False)
    is_revoked = Column(Integer, nullable=False, default=0, index=True)
    revoked_at = Column(String(64), nullable=True)
    created_at = Column(String(64), nullable=False)
    last_used_at = Column(String(64), nullable=False)

    user = relationship("UserModel", back_populates="sessions")


class BuildingModel(Base):
    """Physical building asset."""
    __tablename__ = "buildings"

    building_id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    address = Column(String(512), nullable=False)
    created_at = Column(String(64), nullable=True)

    organization = relationship("OrganizationModel", back_populates="buildings")
    floors = relationship("FloorModel", back_populates="building", cascade="all, delete-orphan")
    cameras = relationship("CameraModel", back_populates="building", cascade="all, delete-orphan")


class FloorModel(Base):
    """Floor of a building."""
    __tablename__ = "floors"

    floor_id = Column(String(64), primary_key=True)
    building_id = Column(String(64), ForeignKey("buildings.building_id", ondelete="CASCADE"), nullable=False, index=True)
    floor_number = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    width_meters = Column(Float, nullable=False)
    height_meters = Column(Float, nullable=False)
    floorplan_image_url = Column(String(1024), nullable=True)
    created_at = Column(String(64), nullable=True)

    building = relationship("BuildingModel", back_populates="floors")


class CameraModel(Base):
    """CCTV/IP Camera surveillance feed configuration."""
    __tablename__ = "cameras"

    camera_id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    building_id = Column(String(64), ForeignKey("buildings.building_id", ondelete="CASCADE"), nullable=False, index=True)
    floor_id = Column(String(64), ForeignKey("floors.floor_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    source_uri = Column(String(1024), nullable=False)
    status = Column(String(32), nullable=False, default="ONLINE")
    monitored_nodes_json = Column(Text, nullable=True)
    last_seen_at = Column(String(64), nullable=True)
    calibration_id = Column(String(64), nullable=True)
    created_at = Column(String(64), nullable=True)

    building = relationship("BuildingModel", back_populates="cameras")


class CalibrationModel(Base):
    """Planar homography camera-to-floor calibration metadata."""
    __tablename__ = "calibrations"

    calibration_id = Column(String(64), primary_key=True)
    camera_id = Column(String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    building_id = Column(String(64), ForeignKey("buildings.building_id", ondelete="CASCADE"), nullable=False)
    floor_id = Column(String(64), ForeignKey("floors.floor_id", ondelete="CASCADE"), nullable=False)
    matrix_3x3_json = Column(Text, nullable=False)
    points_json = Column(Text, nullable=True)
    reprojection_error = Column(Float, nullable=False, default=0.0)
    is_valid = Column(Integer, nullable=False, default=1)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=True)


class FloorplanModelDB(Base):
    """Spatial topology and navigation graph definition for a floor."""
    __tablename__ = "floorplans"

    floorplan_id = Column(String(64), primary_key=True)
    building_id = Column(String(64), ForeignKey("buildings.building_id", ondelete="CASCADE"), nullable=False, index=True)
    floor_id = Column(String(64), ForeignKey("floors.floor_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    image_url = Column(String(1024), nullable=True)
    image_width_px = Column(Integer, nullable=False, default=1000)
    image_height_px = Column(Integer, nullable=False, default=800)
    scale_reference_json = Column(Text, nullable=True)
    physical_width_meters = Column(Float, nullable=True)
    physical_height_meters = Column(Float, nullable=True)
    is_scale_calibrated = Column(Integer, nullable=False, default=0)
    regions_json = Column(Text, nullable=True)
    walls_json = Column(Text, nullable=True)
    doors_json = Column(Text, nullable=True)
    exits_json = Column(Text, nullable=True)
    nodes_json = Column(Text, nullable=True)
    edges_json = Column(Text, nullable=True)
    graph_version = Column(String(32), nullable=False, default="1.0.0")
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)


class VideoSourceModel(Base):
    """Original uploaded video file record and metadata."""
    __tablename__ = "video_sources"

    video_id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    uploader_user_id = Column(String(64), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    storage_path = Column(String(1024), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(64), nullable=False)
    sha256_checksum = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="UPLOADED", index=True)
    fps = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    resolution = Column(String(32), nullable=True)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)

    uploader = relationship("UserModel", back_populates="uploaded_videos")
    jobs = relationship("ProcessingJobModel", back_populates="video", cascade="all, delete-orphan")


class ProcessingJobModel(Base):
    """Video perception processing execution job."""
    __tablename__ = "processing_jobs"

    job_id = Column(String(64), primary_key=True)
    video_id = Column(String(64), ForeignKey("video_sources.video_id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    building_id = Column(String(64), ForeignKey("buildings.building_id", ondelete="CASCADE"), nullable=False, index=True)
    floor_id = Column(String(64), ForeignKey("floors.floor_id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    progress_pct = Column(Float, nullable=False, default=0.0)
    current_frame = Column(Integer, nullable=False, default=0)
    total_frames = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)
    error_details_json = Column(Text, nullable=True)
    annotated_video_path = Column(String(1024), nullable=True)
    started_at = Column(String(64), nullable=True)
    completed_at = Column(String(64), nullable=True)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)

    video = relationship("VideoSourceModel", back_populates="jobs")
    frames = relationship("VideoFrameModel", back_populates="job", cascade="all, delete-orphan")
    detections = relationship("DetectionModel", back_populates="job", cascade="all, delete-orphan")
    temporal_analyses = relationship("TemporalAnalysisModel", back_populates="job", cascade="all, delete-orphan")
    risk_events = relationship("RiskEventModel", back_populates="job", cascade="all, delete-orphan")
    routes = relationship("RouteRecommendationModel", back_populates="job", cascade="all, delete-orphan")


class VideoFrameModel(Base):
    """Processed frame record from video stream."""
    __tablename__ = "video_frames"

    frame_id = Column(String(64), primary_key=True)
    job_id = Column(String(64), ForeignKey("processing_jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(64), ForeignKey("video_sources.video_id", ondelete="CASCADE"), nullable=False, index=True)
    frame_index = Column(Integer, nullable=False, index=True)
    timestamp_seconds = Column(Float, nullable=False)
    frame_image_path = Column(String(1024), nullable=True)
    inference_latency_ms = Column(Float, nullable=True)
    created_at = Column(String(64), nullable=False)

    job = relationship("ProcessingJobModel", back_populates="frames")


class DetectionModel(Base):
    """Perception detection bounding box and confidence score."""
    __tablename__ = "detections"

    detection_id = Column(String(64), primary_key=True)
    job_id = Column(String(64), ForeignKey("processing_jobs.job_id", ondelete="CASCADE"), nullable=True, index=True)
    frame_id = Column(String(64), nullable=False, index=True)
    camera_id = Column(String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(String(64), nullable=False)
    class_name = Column(String(32), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    bbox_json = Column(Text, nullable=False)
    floor_point_json = Column(Text, nullable=True)
    model_version = Column(String(64), nullable=True, default="yolov11-dual")

    job = relationship("ProcessingJobModel", back_populates="detections")


class TemporalAnalysisModel(Base):
    """Temporal smoke progression measurement record."""
    __tablename__ = "temporal_analyses"

    analysis_id = Column(String(64), primary_key=True)
    job_id = Column(String(64), ForeignKey("processing_jobs.job_id", ondelete="CASCADE"), nullable=True, index=True)
    camera_id = Column(String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(String(64), nullable=False)
    area_px2 = Column(Float, nullable=False)
    delta_area_px2 = Column(Float, nullable=False, default=0.0)
    dt_seconds = Column(Float, nullable=False, default=0.0)
    growth_rate_px2_per_sec = Column(Float, nullable=False, default=0.0)
    smoothed_growth_rate = Column(Float, nullable=False, default=0.0)
    trend = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(String(64), nullable=False)

    job = relationship("ProcessingJobModel", back_populates="temporal_analyses")


class RiskEventModel(Base):
    """Spatial risk snapshot across floor nodes."""
    __tablename__ = "risk_events"

    snapshot_id = Column(String(64), primary_key=True)
    job_id = Column(String(64), ForeignKey("processing_jobs.job_id", ondelete="CASCADE"), nullable=True, index=True)
    building_id = Column(String(64), ForeignKey("buildings.building_id", ondelete="CASCADE"), nullable=False, index=True)
    floor_id = Column(String(64), ForeignKey("floors.floor_id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(String(64), nullable=False)
    global_risk_level = Column(String(32), nullable=False)
    node_risks_json = Column(Text, nullable=False)
    active_hazards_count = Column(Integer, nullable=False, default=0)
    created_at = Column(String(64), nullable=False)

    job = relationship("ProcessingJobModel", back_populates="risk_events")


class RouteRecommendationModel(Base):
    """Evacuation route calculation record."""
    __tablename__ = "route_recommendations"

    route_id = Column(String(64), primary_key=True)
    job_id = Column(String(64), ForeignKey("processing_jobs.job_id", ondelete="CASCADE"), nullable=True, index=True)
    building_id = Column(String(64), ForeignKey("buildings.building_id", ondelete="CASCADE"), nullable=False, index=True)
    floor_id = Column(String(64), ForeignKey("floors.floor_id", ondelete="CASCADE"), nullable=False, index=True)
    graph_version = Column(String(32), nullable=False, default="1.0.0")
    origin_node = Column(String(64), nullable=False, index=True)
    destination_node = Column(String(64), nullable=False)
    path_nodes_json = Column(Text, nullable=False)
    path_edges_json = Column(Text, nullable=False)
    status = Column(String(32), nullable=False)
    eta_seconds = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    cost_breakdown_json = Column(Text, nullable=False)
    algorithm_version = Column(String(64), nullable=False)
    calculation_assumptions_json = Column(Text, nullable=True)
    is_degraded = Column(Integer, nullable=False, default=0)
    computed_at = Column(String(64), nullable=False)

    job = relationship("ProcessingJobModel", back_populates="routes")


class IncidentModel(Base):
    """Emergency incident record."""
    __tablename__ = "incidents"

    incident_id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False)
    building_id = Column(String(64), ForeignKey("buildings.building_id", ondelete="CASCADE"), nullable=False, index=True)
    floor_id = Column(String(64), ForeignKey("floors.floor_id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    severity = Column(String(32), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    hazard_origin_node = Column(String(64), nullable=True)
    affected_nodes_json = Column(Text, nullable=True)
    declared_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)
    resolved_at = Column(String(64), nullable=True)


class AuditEventModel(Base):
    """Immutable audit trail for security, configuration, and emergency actions."""
    __tablename__ = "audit_events"

    audit_id = Column(String(64), primary_key=True)
    timestamp = Column(String(64), nullable=False)
    organization_id = Column(String(64), ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(64), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False, index=True)
    before_state_json = Column(Text, nullable=True)
    after_state_json = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)


# Compound Indexes for high query performance
Index("ix_detections_job_class", DetectionModel.job_id, DetectionModel.class_name)
Index("ix_temporal_job_camera", TemporalAnalysisModel.job_id, TemporalAnalysisModel.camera_id)
Index("ix_routes_building_origin", RouteRecommendationModel.building_id, RouteRecommendationModel.origin_node)
Index("ix_jobs_video_status", ProcessingJobModel.video_id, ProcessingJobModel.status)
Index("ix_frames_job_index", VideoFrameModel.job_id, VideoFrameModel.frame_index)
