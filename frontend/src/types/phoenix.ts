export type UserRole = 'SUPERADMIN' | 'BUILDING_MANAGER' | 'FIRST_RESPONDER' | 'OCCUPANT';

export type CameraStatus = 'ONLINE' | 'OFFLINE' | 'DEGRADED' | 'CALIBRATION_REQUIRED';

export type IncidentSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type IncidentStatus = 'REPORTED' | 'CONFIRMED' | 'EVACUATING' | 'CONTAINED' | 'RESOLVED' | 'CLOSED';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'BLOCKED';

export type RouteStatus = 'VALID' | 'NO_VALID_ROUTE' | 'NO_VALID_EXIT' | 'DEGRADED';

export type EventType = 
  | 'DETECTION_OBSERVED'
  | 'SMOKE_GROWTH_ALERT'
  | 'RISK_UPDATED'
  | 'ROUTE_CHANGED'
  | 'CAMERA_STATUS_CHANGED'
  | 'INCIDENT_STATUS_CHANGED'
  | 'SYSTEM_ALERT';

export interface LoginRequest {
  email: string;
  password?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  role: UserRole;
  organization_id: string;
  expires_in_seconds: number;
}

export interface FloorSchema {
  floor_id: string;
  building_id: string;
  floor_number: number;
  name: string;
  width_meters: number;
  height_meters: number;
  floorplan_image_url?: string;
}

export interface BuildingResponse {
  building_id: string;
  organization_id: string;
  name: string;
  address: string;
  floors: FloorSchema[];
}

export interface CameraResponse {
  camera_id: string;
  organization_id: string;
  building_id: string;
  floor_id: string;
  name: string;
  source_uri: string;
  status: CameraStatus;
  monitored_nodes: string[];
  has_calibration: boolean;
  last_seen_at?: string;
}

export interface IncidentResponse {
  incident_id: string;
  organization_id: string;
  building_id: string;
  floor_id: string;
  status: IncidentStatus;
  severity: IncidentSeverity;
  title: string;
  description?: string;
  hazard_origin_node?: string;
  affected_nodes: string[];
  declared_at: string;
  updated_at: string;
  resolved_at?: string;
}

export interface RouteCostReasonSchema {
  distance_cost: number;
  hazard_cost: number;
  occupancy_cost: number;
  predicted_blockage_cost: number;
  total_cost: number;
}

export interface RouteRecommendationResponse {
  route_id: string;
  building_id: string;
  floor_id: string;
  origin_node: string;
  destination_node: string;
  path_nodes: string[];
  path_edges: string[];
  status: RouteStatus;
  eta_seconds: number;
  total_cost: number;
  cost_breakdown: RouteCostReasonSchema;
  algorithm_version: string;
  is_degraded: boolean;
  computed_at: string;
}

export interface EventEnvelope {
  event_id: string;
  event_type: EventType;
  sequence: number;
  timestamp: string;
  scope: Record<string, any>;
  payload: Record<string, any>;
}

export interface HealthCheckResponse {
  status: string;
  timestamp: string;
  version: string;
  environment: string;
  services: Record<string, string>;
}

export interface ReadinessResponse {
  ready: boolean;
  ai_status: string;
  persistence_status: string;
  timestamp: string;
}

export type MeasurementProvenance = 
  | 'MEASURED'
  | 'CALCULATED'
  | 'CALIBRATED'
  | 'CONFIGURED'
  | 'ESTIMATED'
  | 'PREDICTED';

export type SpatialRegionType = 
  | 'ROOM'
  | 'CORRIDOR'
  | 'HALL'
  | 'LOBBY'
  | 'STAIRWELL'
  | 'EXIT'
  | 'DOOR'
  | 'ZONE';

export interface Point2D {
  x: number;
  y: number;
}

export interface SpatialRegionSchema {
  region_id: string;
  name: string;
  region_type: SpatialRegionType;
  polygon_points?: Point2D[];
  polygon?: Point2D[];
  centroid?: Point2D;
  center?: Point2D;
  is_navigable?: boolean;
  is_exit?: boolean;
  capacity?: number;
  provenance?: MeasurementProvenance;
  metadata?: Record<string, any>;
}

export interface ScaleReferenceSchema {
  point1?: Point2D;
  point2?: Point2D;
  point_a?: Point2D;
  point_b?: Point2D;
  known_distance_meters: number;
  pixel_distance?: number;
  meters_per_pixel?: number;
  is_calibrated?: boolean;
  provenance?: MeasurementProvenance;
}

export interface NavigationNodeSchema {
  node_id: string;
  building_id?: string;
  floor_id?: string;
  label?: string;
  name?: string;
  node_type?: string;
  x: number;
  y: number;
  is_exit: boolean;
  region_id?: string;
  provenance?: MeasurementProvenance;
}

export interface NavigationEdgeSchema {
  edge_id: string;
  from_node: string;
  to_node: string;
  length_meters: number;
  is_blocked?: boolean;
  hazard_score?: number;
  occupancy_count?: number;
  predicted_blockage_score?: number;
  provenance?: MeasurementProvenance;
}

export interface FloorplanModelResponse {
  floorplan_id: string;
  building_id: string;
  floor_id: string;
  name: string;
  image_url?: string;
  image_width_px?: number;
  image_height_px?: number;
  width_meters?: number;
  height_meters?: number;
  physical_width_meters?: number;
  physical_height_meters?: number;
  is_scale_calibrated?: boolean;
  scale_reference?: ScaleReferenceSchema;
  provenance?: MeasurementProvenance;
  regions?: SpatialRegionSchema[];
  nodes?: NavigationNodeSchema[];
  edges?: NavigationEdgeSchema[];
  created_at?: string;
}

export interface VideoSourceResponse {
  video_id: string;
  organization_id: string;
  original_filename: string;
  stored_filename: string;
  storage_path: string;
  mime_type: string;
  file_size_bytes: number;
  duration_seconds?: number;
  fps?: number;
  width?: number;
  height?: number;
  status: string;
  created_at: string;
}

export interface ProcessingJobResponse {
  job_id: string;
  video_id: string;
  organization_id: string;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  current_stage?: string;
  progress_percent?: number;
  frames_processed?: number;
  total_frames?: number;
  detections_count?: number;
  fire_detected?: boolean;
  smoke_detected?: boolean;
  max_risk_level?: string;
  error_message?: string;
  execution_time_seconds?: number;
  annotated_video_path?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface JobResultsResponse {
  job_id: string;
  video_id: string;
  camera_id?: string;
  original_filename?: string;
  status: string;
  has_calibration: boolean;
  summary: {
    frames_processed: number;
    total_detections: number;
    fire_detected: boolean;
    smoke_detected: boolean;
    max_risk_level: string;
    execution_time_seconds?: number;
    annotated_video_path?: string;
  };
  counts: {
    detections: number;
    temporal_analyses: number;
    risk_events: number;
    routes_computed: number;
    keyframes_saved: number;
  };
  latest_route?: RouteRecommendationResponse | null;
  recent_detections: Array<{
    detection_id?: string;
    class_name: string;
    confidence: number;
    bbox: { x1: number; y1: number; x2: number; y2: number };
    timestamp_seconds?: number;
    area_px2?: number;
  }>;
  temporal_smoke_samples: Array<{
    analysis_id?: string;
    timestamp: number | string;
    area_px2: number;
    growth_rate_px2_per_sec: number;
    trend: string;
    confidence: number;
  }>;
  risk_history: Array<{
    snapshot_id?: string;
    timestamp: string;
    global_risk_level: string;
    node_risks: Record<string, number>;
    active_hazards_count: number;
  }>;
  keyframes: Array<{
    frame_id: string;
    frame_index: number;
    timestamp_seconds: number;
    frame_image_path?: string;
    detections_count: number;
  }>;
}

export interface UserResponse {
  user_id: string;
  organization_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface StorageOverviewResponse {
  audit_timestamp: string;
  database: {
    path: string;
    exists: boolean;
    size_bytes: number;
    last_modified: string | null;
    journal_mode: string;
    database_type: string;
  };
  directories: Record<string, {
    path: string;
    exists: boolean;
    file_count: number;
    total_size_bytes: number;
    last_modified: string | null;
  }>;
  key_artifacts: Record<string, {
    path: string;
    exists: boolean;
    size_bytes: number;
    last_modified: string | null;
  }>;
  authenticated_reviewer: {
    user_id: string;
    role: UserRole;
    organization_id: string;
  };
}

export interface UserInventoryResponse {
  total_users: number;
  users: Array<{
    user_id: string;
    organization_id: string;
    email: string;
    full_name: string;
    role: UserRole;
    is_active: boolean;
    created_at: string;
    updated_at?: string;
  }>;
  identity_architecture_explanation: {
    user_id: string;
    role: string;
    access_token: string;
    storage_security: string;
  };
}

export interface DatabaseInventoryResponse {
  database_file: string;
  total_tables: number;
  total_records: number;
  tables: Array<{
    table_name: string;
    exists: boolean;
    row_count: number;
    primary_key: string;
    description: string;
  }>;
}

export interface JobsInventoryResponse {
  total_jobs: number;
  limit: number;
  offset: number;
  jobs: Array<{
    job_id: string;
    video_id: string;
    camera_id: string;
    original_filename: string;
    file_size_bytes?: number;
    sha256_checksum?: string;
    source_exists: boolean;
    status: string;
    progress_percent: number;
    current_stage: string;
    frames_processed: number;
    total_frames: number;
    detections_count: number;
    fire_detected: boolean;
    smoke_detected: boolean;
    max_risk_level: string;
    execution_time_seconds?: number;
    annotated_video_path?: string;
    annotated_video_exists: boolean;
    created_at: string;
    completed_at?: string;
  }>;
}

export interface JobSampleResponse {
  job: Record<string, any>;
  sample_detections: Array<{
    detection_id: string;
    frame_id: string;
    class_name: string;
    confidence: number;
    bbox: { x1: number; y1: number; x2: number; y2: number } | null;
    floor_point: { x: number; y: number } | null;
    timestamp: string;
  }>;
  sample_temporal_analyses: Array<{
    analysis_id: string;
    timestamp: string;
    area_px2: number;
    growth_rate_px2_per_sec: number;
    trend: string;
    confidence: number;
  }>;
  sample_routes: Array<{
    route_id: string;
    origin_node: string;
    destination_node: string;
    path_nodes: string[];
    eta_seconds: number;
    total_cost: number;
    algorithm_version: string;
    computed_at: string;
  }>;
}

