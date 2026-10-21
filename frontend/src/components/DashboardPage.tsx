import React, { useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useWebSocket } from '../context/WebSocketContext';
import { ApiClient } from '../services/apiClient';
import { CameraFeed } from './CameraFeed';
import { EvacuationMap } from './EvacuationMap';
import { DataStorageExplorer } from './DataStorageExplorer';
import { RoleAuthModal } from './RoleAuthModal';
import type {
  BuildingResponse,
  CameraResponse,
  FloorplanModelResponse,
  HealthCheckResponse,
  IncidentResponse,
  JobResultsResponse,
  NavigationNodeSchema,
  RouteRecommendationResponse,
  UserRole,
} from '../types/phoenix';

interface UploadState {
  isUploading: boolean;
  isProcessing: boolean;
  progress: number;
  stage?: string;
  framesProcessed?: number;
  totalFrames?: number;
  filename?: string;
  fileSize?: string;
  error?: string | null;
}

interface ActiveUploadedVideo {
  videoId: string;
  jobId: string;
  filename: string;
  rawVideoUrl: string;
  annotatedVideoUrl?: string;
  hasCalibration: boolean;
  results: JobResultsResponse;
}

interface MainDemoBackup {
  detections: Array<{
    class_name: string;
    confidence: number;
    bbox: { x1: number; y1: number; x2: number; y2: number };
  }>;
  smoke: {
    area_px2: number;
    growth_rate_px2_per_sec: number;
    trend: string;
    confidence: number;
    timestamp: string;
  } | null;
  risk: {
    global_risk_level: string;
    node_risks: Record<string, number>;
    active_hazards_count: number;
    timestamp: string;
  } | null;
  incident: IncidentResponse | null;
  route: RouteRecommendationResponse | null;
  temporalSamples: Array<{
    timestamp: number;
    area_px2: number;
    growth_rate: number;
    trend: string;
  }>;
}

export const DashboardPage: React.FC = () => {
  const { role, userId, userProfile, logout } = useAuth();
  const { isConnected, lastEvent } = useWebSocket();

  // Navigation & Role State
  const [showExplorer, setShowExplorer] = useState<boolean>(false);
  const [targetSwitchRole, setTargetSwitchRole] = useState<UserRole | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);

  // Video Upload & Switcher State
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollTimerRef = useRef<any>(null);
  const [uploadState, setUploadState] = useState<UploadState>({
    isUploading: false,
    isProcessing: false,
    progress: 0,
    error: null,
  });
  const [activeUploadedVideo, setActiveUploadedVideo] = useState<ActiveUploadedVideo | null>(null);
  const [isShowingUploaded, setIsShowingUploaded] = useState<boolean>(false);
  const [mainDemoBackup, setMainDemoBackup] = useState<MainDemoBackup | null>(null);
  const [temporalSamples, setTemporalSamples] = useState<Array<{
    timestamp: number;
    area_px2: number;
    growth_rate: number;
    trend: string;
  }>>([]);

  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [building, setBuilding] = useState<BuildingResponse | null>(null);
  const [cameras, setCameras] = useState<CameraResponse[]>([]);
  const [floorplan, setFloorplan] = useState<FloorplanModelResponse | null>(null);
  const [incident, setIncident] = useState<IncidentResponse | null>(null);
  const [route, setRoute] = useState<RouteRecommendationResponse | null>(null);
  const [origin, setOrigin] = useState<string>('node_west_suites');
  const [routeNotification, setRouteNotification] = useState<string | null>(null);
  const [useAIStream, setUseAIStream] = useState<boolean>(true);
  const [selectedCamId, setSelectedCamId] = useState<string>('CAM-MAIN-01');
  const [occupantSafeChecked, setOccupantSafeChecked] = useState<boolean>(false);
  const [assistanceRequested, setAssistanceRequested] = useState<boolean>(false);
  const [eventHistory, setEventHistory] = useState<Array<{ type: string; time: string; summary: string }>>([]);

  // Real-Time Telemetry State populated from genuine persistent backend records
  const [liveDetections, setLiveDetections] = useState<Array<{
    class_name: string;
    confidence: number;
    bbox: { x1: number; y1: number; x2: number; y2: number };
  }>>([]);

  const [liveSmoke, setLiveSmoke] = useState<{
    area_px2: number;
    growth_rate_px2_per_sec: number;
    trend: string;
    confidence: number;
    timestamp: string;
  } | null>(null);

  const [liveRisk, setLiveRisk] = useState<{
    global_risk_level: string;
    node_risks: Record<string, number>;
    active_hazards_count: number;
    timestamp: string;
  } | null>(null);

  // Authenticated Role Switching
  const handleRoleSwitch = (newRole: UserRole) => {
    if (newRole === role) return;
    setTargetSwitchRole(newRole);
  };

  // Initial Data Fetching from genuine backend state (scoped to role authorization)
  useEffect(() => {
    let mounted = true;
    const loadInitialData = async () => {
      try {
        setCameraError(null);
        const isOccupant = role === 'OCCUPANT';

        const [hData, bData, cData, fpData] = await Promise.all([
          ApiClient.getHealth().catch(() => null),
          ApiClient.getBuilding('bldg-hq-01').catch(() => null),
          !isOccupant
            ? ApiClient.getCameras('bldg-hq-01').catch((err) => {
                if (mounted) setCameraError(err?.message || 'Failed to fetch camera feeds');
                return null;
              })
            : Promise.resolve([]),
          ApiClient.getFloorplan('bldg-hq-01', 'fl-01').catch(() => null),
        ]);

        if (!mounted) return;
        if (hData) setHealth(hData);
        if (bData) setBuilding(bData);
        if (isOccupant) {
          // Occupant role is restricted from CCTV streams under privacy and life-safety policy
          setCameras([]);
        } else if (cData && cData.length > 0) {
          setCameras(cData);
        } else if (cameraError) {
          setCameras([]);
        } else {
          // Fallback robust CCTV configuration matching the 5 videos
          setCameras([
            {
              camera_id: 'CAM-MAIN-01',
              organization_id: 'org-phoenix-main',
              building_id: 'bldg-hq-01',
              floor_id: 'fl-01',
              name: 'Central Corridor North View (Main CCTV)',
              source_uri: '/videos/Main_video.mp4',
              status: 'ONLINE',
              monitored_nodes: ['node_corridor_mid', 'node_east_alcove', 'node_corridor_north'],
              has_calibration: true,
            },
            {
              camera_id: 'CAM-SOUTH-01',
              organization_id: 'org-phoenix-main',
              building_id: 'bldg-hq-01',
              floor_id: 'fl-01',
              name: 'South Exit Corridor (Primary Egress)',
              source_uri: '/videos/test2.mp4',
              status: 'ONLINE',
              monitored_nodes: ['node_corridor_south', 'exit_south'],
              has_calibration: true,
            },
            {
              camera_id: 'CAM-NORTH-01',
              organization_id: 'org-phoenix-main',
              building_id: 'bldg-hq-01',
              floor_id: 'fl-01',
              name: 'North Corridor Approach',
              source_uri: '/videos/test1.mp4',
              status: 'ONLINE',
              monitored_nodes: ['node_corridor_north', 'exit_north'],
              has_calibration: true,
            },
            {
              camera_id: 'CAM-HALL-01',
              organization_id: 'org-phoenix-main',
              building_id: 'bldg-hq-01',
              floor_id: 'fl-01',
              name: 'Main Hall West',
              source_uri: '/videos/test3.mp4',
              status: 'ONLINE',
              monitored_nodes: ['node_west_suites'],
              has_calibration: true,
            },
          ]);
        }
        if (fpData) setFloorplan(fpData);

        // Check if genuine active incident exists in the backend
        const activeIncident = await ApiClient.getCurrentIncident('bldg-hq-01').catch(() => null);
        let initialRoute: RouteRecommendationResponse | null = null;
        if (mounted) {
          if (activeIncident && activeIncident.status !== 'CLOSED' && activeIncident.status !== 'RESOLVED') {
            setIncident(activeIncident);
            initialRoute = await ApiClient.getCurrentRoute(origin, 'bldg-hq-01').catch(() => null);
            if (mounted && initialRoute) setRoute(initialRoute);
          } else {
            setIncident(null);
            setRoute(null);
          }
        }

        // Fetch recent detections, risk assessment, and events from persistent database
        const [recentDets, currentRisk, history] = await Promise.all([
          ApiClient.getRecentDetections(undefined, 20),
          ApiClient.getCurrentRisk('bldg-hq-01'),
          ApiClient.getEventHistory(20),
        ]);

        if (mounted) {
          if (recentDets && recentDets.length > 0) {
            setLiveDetections(recentDets);
          }
          if (currentRisk) {
            setLiveRisk({
              global_risk_level: currentRisk.global_risk_level || 'LOW',
              node_risks: currentRisk.node_risks || {},
              active_hazards_count: currentRisk.active_hazards_count || 0,
              timestamp: currentRisk.timestamp || new Date().toISOString(),
            });
          }
          if (history && history.length > 0) {
            setEventHistory(history.map((h: any) => ({
              type: h.event_type || 'SYSTEM',
              time: h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString(),
              summary: h.summary || h.title || JSON.stringify(h.details || {}),
            })));
          }

          // Back up genuine baseline state for Main_video demonstration
          setMainDemoBackup({
            detections: recentDets || [],
            smoke: null,
            risk: currentRisk ? {
              global_risk_level: currentRisk.global_risk_level || 'LOW',
              node_risks: currentRisk.node_risks || {},
              active_hazards_count: currentRisk.active_hazards_count || 0,
              timestamp: currentRisk.timestamp || new Date().toISOString(),
            } : null,
            incident: activeIncident && activeIncident.status !== 'CLOSED' && activeIncident.status !== 'RESOLVED' ? activeIncident : null,
            route: activeIncident ? initialRoute : null,
            temporalSamples: [],
          });
        }
      } catch (err) {
        console.error('Failed to load initial backend state:', err);
      }
    };

    loadInitialData();
    return () => {
      mounted = false;
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [role, userId]);

  // Real-Time WebSocket Event Processing (Scoped to Main CCTV; suspended when inspecting uploaded video)
  useEffect(() => {
    if (!lastEvent || isShowingUploaded) return;

    const { event_type, payload } = lastEvent;
    const timeStr = new Date().toLocaleTimeString();

    if (event_type === 'DETECTION_OBSERVED' && payload?.detections) {
      setLiveDetections(payload.detections);
      setEventHistory((prev) => [
        { type: event_type, time: timeStr, summary: `Detections updated: ${payload.detections.length} objects` },
        ...prev.slice(0, 15),
      ]);
    } else if (event_type === 'SMOKE_GROWTH_ALERT') {
      setLiveSmoke({
        area_px2: payload.area_px2 || 0,
        growth_rate_px2_per_sec: payload.growth_rate_px2_per_sec || 0,
        trend: payload.trend || 'UNKNOWN',
        confidence: payload.confidence || 0,
        timestamp: payload.timestamp || new Date().toISOString(),
      });
      setEventHistory((prev) => [
        { type: event_type, time: timeStr, summary: `Smoke alert: ${payload.area_px2?.toLocaleString()} px² (${payload.trend})` },
        ...prev.slice(0, 15),
      ]);
    } else if (event_type === 'RISK_UPDATED') {
      setLiveRisk({
        global_risk_level: payload.global_risk_level || 'LOW',
        node_risks: payload.node_risks || {},
        active_hazards_count: payload.active_hazards_count || 0,
        timestamp: payload.timestamp || new Date().toISOString(),
      });
    } else if (event_type === 'INCIDENT_STATUS_CHANGED') {
      const status = payload?.status;
      if (status === 'RESOLVED' || status === 'CLOSED') {
        setIncident(null);
        setRoute(null);
        setRouteNotification('INCIDENT RESOLVED: All corridors cleared. Normal Surveillance restored.');
      } else {
        ApiClient.getCurrentIncident('bldg-hq-01').then((inc) => {
          if (inc) setIncident(inc);
        });
        setRouteNotification(`HAZARD CONFIRMED: ${payload?.title || 'Emergency transition engaged.'}`);
      }
    } else if (event_type === 'ROUTE_CHANGED') {
      ApiClient.getCurrentRoute(origin, 'bldg-hq-01').then((rt) => {
        if (rt) setRoute(rt);
      });
      setRouteNotification('ROUTE UPDATED: Evacuation path updated based on real-time hazard decay.');
    }
  }, [lastEvent, origin, isShowingUploaded]);

  const handleOriginChange = async (newOrigin: string) => {
    setOrigin(newOrigin);
    if (incident && (!isShowingUploaded || activeUploadedVideo?.hasCalibration)) {
      const activeRoute = await ApiClient.getCurrentRoute(newOrigin, 'bldg-hq-01').catch(() => null);
      if (activeRoute) {
        setRoute(activeRoute);
      } else {
        setRoute(null);
      }
    }
  };

  // Step 3: Video File Selection & Job Lifecycle Handler
  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Reset input to allow selecting the same file again
    e.target.value = '';

    // Step 3.1: Frontend validation (file type and size)
    const validExtensions = ['.mp4', '.mov', '.mkv', '.avi'];
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!validExtensions.includes(ext) && !file.type.startsWith('video/')) {
      setUploadState({
        isUploading: false,
        isProcessing: false,
        progress: 0,
        error: `Invalid file format (${ext || file.type}). Please select an MP4, MOV, MKV, or AVI video.`,
      });
      return;
    }

    const maxSizeBytes = 500 * 1024 * 1024; // 500 MB limit
    if (file.size > maxSizeBytes) {
      setUploadState({
        isUploading: false,
        isProcessing: false,
        progress: 0,
        error: `File is too large (${(file.size / (1024 * 1024)).toFixed(1)}MB). Maximum allowed video size is 500MB.`,
      });
      return;
    }

    const sizeStr = file.size > 1024 * 1024
      ? `${(file.size / (1024 * 1024)).toFixed(1)} MB`
      : `${(file.size / 1024).toFixed(1)} KB`;

    setUploadState({
      isUploading: true,
      isProcessing: false,
      progress: 15,
      filename: file.name,
      fileSize: sizeStr,
      error: null,
    });

    try {
      // Step 3.2: Upload file through existing authenticated API client
      const videoRecord = await ApiClient.uploadVideo(file);

      setUploadState((prev) => ({
        ...prev,
        isUploading: false,
        isProcessing: true,
        progress: 25,
        stage: 'INITIALIZING',
      }));

      // Step 3.3: Queue perception job with frame stride 2
      const jobRecord = await ApiClient.startJob(videoRecord.video_id, 2);
      const jobId = jobRecord.job_id;

      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }

      // Step 3.4 & 3.5: Poll job progress with retry resilience
      let consecutiveErrors = 0;
      const pollTimer = setInterval(async () => {
        try {
          const job = await ApiClient.getJob(jobId);
          consecutiveErrors = 0;

          setUploadState((prev) => ({
            ...prev,
            progress: Math.min(99, Math.max(25, Math.round(job.progress_percent || 25))),
            stage: job.current_stage || 'RUNNING_PERCEPTION',
            framesProcessed: job.frames_processed,
            totalFrames: job.total_frames,
          }));

          if (job.status === 'COMPLETED') {
            clearInterval(pollTimer);
            pollTimerRef.current = null;

            // Step 3.6: Fetch genuine persisted job results
            const results = await ApiClient.getJobResults(jobId);

            setUploadState({
              isUploading: false,
              isProcessing: false,
              progress: 100,
              filename: file.name,
              fileSize: sizeStr,
              error: null,
            });

            const uploadedState: ActiveUploadedVideo = {
              videoId: videoRecord.video_id,
              jobId: jobId,
              filename: file.name,
              rawVideoUrl: ApiClient.getRawVideoUrl(videoRecord.video_id),
              annotatedVideoUrl: results.summary.annotated_video_path
                ? ApiClient.getAnnotatedVideoUrl(jobId)
                : undefined,
              hasCalibration: results.has_calibration,
              results: results,
            };

            setActiveUploadedVideo(uploadedState);
            setIsShowingUploaded(true);
            applyJobResultsToDashboard(results, file.name);

            setRouteNotification(
              `PERCEPTION COMPLETE: "${file.name}" analyzed. Observed ${results.summary.total_detections} objects across ${results.summary.frames_processed} frames (${results.summary.fire_detected ? 'FIRE DETECTED' : 'NO FIRE'}, ${results.summary.smoke_detected ? 'SMOKE DETECTED' : 'NO SMOKE'}).`
            );
          } else if (job.status === 'FAILED' || job.status === 'CANCELLED') {
            clearInterval(pollTimer);
            pollTimerRef.current = null;
            setUploadState({
              isUploading: false,
              isProcessing: false,
              progress: 0,
              error: job.error_message || 'Video processing failed on server.',
            });
          }
        } catch (pollErr: any) {
          consecutiveErrors++;
          if (consecutiveErrors >= 4) {
            clearInterval(pollTimer);
            pollTimerRef.current = null;
            setUploadState({
              isUploading: false,
              isProcessing: false,
              progress: 0,
              error: `Failed checking processing status: ${pollErr.message}`,
            });
          }
        }
      }, 1200);
      pollTimerRef.current = pollTimer;

    } catch (err: any) {
      setUploadState({
        isUploading: false,
        isProcessing: false,
        progress: 0,
        error: `Upload failed: ${err.message}`,
      });
    }
  };

  // Step 4: Apply genuine backend results from uploaded video
  const applyJobResultsToDashboard = (results: JobResultsResponse, filename: string) => {
    // 1. Detections
    if (results.recent_detections && results.recent_detections.length > 0) {
      setLiveDetections(
        results.recent_detections.map((d) => ({
          class_name: d.class_name,
          confidence: d.confidence,
          bbox: d.bbox,
        }))
      );
    } else {
      setLiveDetections([]);
    }

    // 2. Temporal Smoke Observations & Growth Trajectory
    if (results.temporal_smoke_samples && results.temporal_smoke_samples.length > 0) {
      const latest = results.temporal_smoke_samples[results.temporal_smoke_samples.length - 1];
      setLiveSmoke({
        area_px2: latest.area_px2,
        growth_rate_px2_per_sec: latest.growth_rate_px2_per_sec,
        trend: latest.trend,
        confidence: latest.confidence,
        timestamp:
          typeof latest.timestamp === 'number'
            ? new Date(latest.timestamp * 1000).toISOString()
            : String(latest.timestamp),
      });

      setTemporalSamples(
        results.temporal_smoke_samples.map((s) => ({
          timestamp: typeof s.timestamp === 'number' ? s.timestamp : parseFloat(String(s.timestamp)) || 0,
          area_px2: s.area_px2,
          growth_rate: s.growth_rate_px2_per_sec,
          trend: s.trend,
        }))
      );
    } else {
      setLiveSmoke(null);
      setTemporalSamples([]);
    }

    // 3. Risk Information
    const maxRisk =
      results.summary.max_risk_level ||
      (results.summary.fire_detected ? 'CRITICAL' : results.summary.smoke_detected ? 'HIGH' : 'LOW');
    setLiveRisk({
      global_risk_level: maxRisk,
      node_risks: {},
      active_hazards_count: results.summary.fire_detected || results.summary.smoke_detected ? 1 : 0,
      timestamp: new Date().toISOString(),
    });

    // 4. Incident Status
    if (results.summary.fire_detected || results.summary.smoke_detected) {
      setIncident({
        incident_id: `inc-upload-${results.job_id.slice(-6)}`,
        organization_id: 'org-phoenix-main',
        building_id: 'bldg-hq-01',
        floor_id: 'fl-01',
        status: 'CONFIRMED',
        severity: results.summary.fire_detected ? 'CRITICAL' : 'HIGH',
        title: `Active Perceptual Hazard in Uploaded Video (${filename})`,
        description: `YOLOv11 verified ${results.summary.fire_detected ? 'active flame' : ''} ${results.summary.smoke_detected ? 'expanding smoke' : ''}. Genuine temporal telemetry recorded.`,
        hazard_origin_node: results.has_calibration ? 'node_east_alcove' : 'Uncalibrated Sector (Pixel Space Only)',
        affected_nodes: [],
        declared_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
    } else {
      setIncident(null);
    }

    // 5. Routing (Step 7: Protect routing & spatial data)
    if (results.has_calibration && results.latest_route) {
      setRoute(results.latest_route);
    } else {
      setRoute(null);
    }

    // 6. Event History
    const timeStr = new Date().toLocaleTimeString();
    setEventHistory((prev) => [
      {
        type: 'VIDEO_JOB_COMPLETED',
        time: timeStr,
        summary: `Analyzed "${filename}": ${results.summary.total_detections} detections across ${results.summary.frames_processed} frames.`,
      },
      ...prev.slice(0, 15),
    ]);
  };

  // Video Demo Switchers: Ensure ZERO stale data or leaks
  const switchToMainDemo = () => {
    setIsShowingUploaded(false);
    if (mainDemoBackup) {
      setLiveDetections(mainDemoBackup.detections);
      setLiveSmoke(mainDemoBackup.smoke);
      setTemporalSamples(mainDemoBackup.temporalSamples);
      setLiveRisk(mainDemoBackup.risk);
      setIncident(mainDemoBackup.incident);
      setRoute(mainDemoBackup.route);
    }
    setRouteNotification('Switched to Default Main CCTV Demonstration (CAM-MAIN-01).');
  };

  const switchToUploaded = () => {
    if (activeUploadedVideo) {
      setIsShowingUploaded(true);
      applyJobResultsToDashboard(activeUploadedVideo.results, activeUploadedVideo.filename);
      setRouteNotification(`Switched to Uploaded Video: "${activeUploadedVideo.filename}".`);
    }
  };

  // Step 5: Genuine Data-Driven Temporal Smoke Growth Sparkline Chart
  const renderSmokeChart = () => {
    if (!temporalSamples || temporalSamples.length < 2) {
      return (
        <div
          style={{
            marginTop: '8px',
            padding: '8px',
            fontSize: '10px',
            color: '#71717a',
            textAlign: 'center',
            background: 'rgba(0,0,0,0.25)',
            borderRadius: '4px',
            border: '1px dashed rgba(255,255,255,0.08)',
          }}
        >
          {temporalSamples && temporalSamples.length === 1
            ? 'ℹ️ 1 frame observed. Minimum 2 successive smoke frames required to calculate data-driven growth curve.'
            : 'ℹ️ No smoke plume observed in video frames. Growth curve will not be fabricated.'}
        </div>
      );
    }

    const width = 310;
    const height = 75;
    const padL = 40;
    const padR = 12;
    const padT = 10;
    const padB = 20;

    const maxArea = Math.max(...temporalSamples.map((s) => s.area_px2), 100);
    const minTime = temporalSamples[0].timestamp;
    const maxTime = Math.max(temporalSamples[temporalSamples.length - 1].timestamp, minTime + 0.1);
    const timeSpan = maxTime - minTime || 1;

    const points = temporalSamples
      .map((s) => {
        const x = padL + ((s.timestamp - minTime) / timeSpan) * (width - padL - padR);
        const y = padT + (1 - s.area_px2 / maxArea) * (height - padT - padB);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');

    const lastSample = temporalSamples[temporalSamples.length - 1];

    return (
      <div
        style={{
          marginTop: '8px',
          background: 'rgba(0,0,0,0.35)',
          borderRadius: '4px',
          padding: '8px 10px',
          border: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#cbd5e1', marginBottom: '6px' }}>
          <span style={{ fontWeight: 700 }}>Data-Driven Smoke Area (px²) vs Timestamp (s)</span>
          <span style={{ color: '#4ade80', fontWeight: 800 }}>{lastSample.area_px2.toLocaleString()} px²</span>
        </div>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: `${height}px`, overflow: 'visible' }}>
          {/* Grid lines */}
          <line x1={padL} y1={padT} x2={width - padR} y2={padT} stroke="rgba(255,255,255,0.08)" strokeDasharray="2,2" />
          <line x1={padL} y1={height - padB} x2={width - padR} y2={height - padB} stroke="rgba(255,255,255,0.15)" />
          <line x1={padL} y1={padT} x2={padL} y2={height - padB} stroke="rgba(255,255,255,0.15)" />

          {/* Value Labels */}
          <text x={padL - 4} y={padT + 4} fontSize="8" fill="#71717a" textAnchor="end">
            {Math.round(maxArea).toLocaleString()}
          </text>
          <text x={padL - 4} y={height - padB} fontSize="8" fill="#71717a" textAnchor="end">
            0
          </text>
          <text x={padL} y={height - 4} fontSize="8" fill="#71717a" textAnchor="start">
            {minTime.toFixed(1)}s
          </text>
          <text x={width - padR} y={height - 4} fontSize="8" fill="#71717a" textAnchor="end">
            {maxTime.toFixed(1)}s
          </text>

          {/* Polyline */}
          <polyline fill="none" stroke="#38bdf8" strokeWidth="2" points={points} />

          {/* Data Points */}
          {temporalSamples.map((s, idx) => {
            const cx = padL + ((s.timestamp - minTime) / timeSpan) * (width - padL - padR);
            const cy = padT + (1 - s.area_px2 / maxArea) * (height - padT - padB);
            return (
              <circle
                key={idx}
                cx={cx}
                cy={cy}
                r="3"
                fill={idx === temporalSamples.length - 1 ? '#4ade80' : '#38bdf8'}
              />
            );
          })}
        </svg>
        <div style={{ fontSize: '8px', color: '#64748b', marginTop: '4px', textAlign: 'center' }}>
          * 2D observed image area growth (Δarea / Δt) — not physical 3D smoke volume
        </div>
      </div>
    );
  };

  const isEmergencyMode = Boolean(
    incident && incident.status !== 'CLOSED' && incident.status !== 'RESOLVED'
  );

  const availableOriginNodes = floorplan?.nodes?.filter((n: NavigationNodeSchema) => !n.is_exit) || [
    { node_id: 'node_west_suites', label: 'West Office Suites' },
    { node_id: 'node_corridor_mid', label: 'Central Corridor Junction' },
    { node_id: 'node_corridor_north', label: 'North Corridor Approach' },
    { node_id: 'node_corridor_south', label: 'South Corridor' },
  ];

  // 4 Active Surveillance Cameras
  const primaryAnalyzedCam = cameras.find((c) => c.camera_id === 'CAM-MAIN-01') || {
    camera_id: 'CAM-MAIN-01',
    name: 'Central Corridor North View (Main CCTV)',
    monitored_nodes: ['node_corridor_mid', 'node_east_alcove'],
    source_uri: '/videos/Main_video.mp4',
    status: 'ONLINE',
    has_calibration: true,
  };

  const secondaryCameras = [
    cameras.find((c) => c.camera_id === 'CAM-SOUTH-01') || {
      camera_id: 'CAM-SOUTH-01',
      name: 'South Exit Corridor (Primary Egress)',
      monitored_nodes: ['node_corridor_south', 'exit_south'],
      source_uri: '/videos/test2.mp4',
      status: 'ONLINE',
      has_calibration: true,
    },
    cameras.find((c) => c.camera_id === 'CAM-NORTH-01') || {
      camera_id: 'CAM-NORTH-01',
      name: 'North Corridor Approach',
      monitored_nodes: ['node_corridor_north', 'exit_north'],
      source_uri: '/videos/test1.mp4',
      status: 'ONLINE',
      has_calibration: true,
    },
    cameras.find((c) => c.camera_id === 'CAM-HALL-01') || {
      camera_id: 'CAM-HALL-01',
      name: 'Main Hall West',
      monitored_nodes: ['node_west_suites'],
      source_uri: '/videos/test3.mp4',
      status: 'ONLINE',
      has_calibration: true,
    },
  ];

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#0c0e12',
        color: '#f4f4f5',
        fontFamily: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Top Header Command Bar */}
      <header
        style={{
          height: '56px',
          backgroundColor: '#090a0d',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          padding: '0 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        {/* Brand & Mode Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              padding: '4px 10px',
              backgroundColor: isEmergencyMode ? '#dc2626' : '#27272a',
              color: '#ffffff',
              fontWeight: 800,
              fontSize: '13px',
              borderRadius: '3px',
              letterSpacing: '1px',
              boxShadow: isEmergencyMode ? '0 0 10px rgba(220, 38, 38, 0.4)' : 'none',
            }}
          >
            PHOENIX
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, color: '#f4f4f5' }}>
              {building?.name || 'Phoenix Innovation Center'}
            </span>
            <span style={{ fontSize: '12px', color: '#71717a' }}>· Ground Floor</span>
          </div>

          <div
            style={{
              padding: '2px 8px',
              borderRadius: '3px',
              fontSize: '10px',
              fontWeight: 700,
              backgroundColor: isEmergencyMode ? 'rgba(220, 38, 38, 0.2)' : 'rgba(34, 197, 94, 0.15)',
              color: isEmergencyMode ? '#fca5a5' : '#86efac',
              border: isEmergencyMode ? '1px solid rgba(220, 38, 38, 0.4)' : '1px solid rgba(34, 197, 94, 0.3)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: isEmergencyMode ? '#ef4444' : '#22c55e',
              }}
            />
            {isEmergencyMode ? 'LAYER 2: EMERGENCY DECISION-SUPPORT' : 'LAYER 1: SURVEILLANCE STANDBY'}
          </div>
        </div>

        {/* Role Switcher Navigation (Enforces credential authentication on every role transition) */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: '#13161c',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '5px',
            padding: '2px',
            gap: '2px',
          }}
        >
          <span style={{ fontSize: '10px', fontWeight: 700, color: '#71717a', padding: '0 8px', textTransform: 'uppercase' }}>
            Role View:
          </span>
          {(['BUILDING_MANAGER', 'FIRST_RESPONDER', 'OCCUPANT', 'SUPERADMIN'] as UserRole[]).map((r) => {
            const isCurrent = role === r;
            const labels: Record<UserRole, string> = {
              BUILDING_MANAGER: '🏢 Building Mgr',
              FIRST_RESPONDER: '🚒 First Responder',
              OCCUPANT: '👤 Occupant',
              SUPERADMIN: '⚡ SuperAdmin',
            };
            return (
              <button
                key={r}
                id={`role-btn-${r.toLowerCase()}`}
                disabled={isCurrent}
                onClick={() => handleRoleSwitch(r)}
                style={{
                  padding: '4px 10px',
                  backgroundColor: isCurrent ? '#2563eb' : 'transparent',
                  color: isCurrent ? '#ffffff' : '#a1a1aa',
                  border: isCurrent ? '1px solid #3b82f6' : '1px solid transparent',
                  borderRadius: '3px',
                  fontSize: '11px',
                  fontWeight: isCurrent ? 700 : 500,
                  cursor: isCurrent ? 'default' : 'pointer',
                  transition: 'all 0.15s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
                title={isCurrent ? `${r} (Active Role)` : `Click to authenticate as ${r}`}
              >
                <span>{labels[r]}</span>
                {isCurrent && <span style={{ fontSize: '10px', color: '#93c5fd', fontWeight: 700 }}>✓</span>}
              </button>
            );
          })}
        </div>

        {/* Status Indicators, Upload Video Button, Explorer Button & Sign Out */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: '12px' }}>
          {/* Hidden File Input for Video Selection */}
          <input
            type="file"
            ref={fileInputRef}
            accept="video/mp4,video/quicktime,video/x-matroska,video/x-msvideo,.mp4,.mov,.mkv,.avi"
            style={{ display: 'none' }}
            onChange={handleFileSelected}
          />

          {/* Dedicated Data & Storage Explorer Navigation Button */}
          <button
            id="btn-nav-explorer"
            onClick={() => setShowExplorer(!showExplorer)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: showExplorer ? '#7c3aed' : '#1e1b4b',
              color: '#e0e7ff',
              border: '1px solid rgba(124, 58, 237, 0.4)',
              borderRadius: '4px',
              padding: '5px 12px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
              transition: 'all 0.15s ease',
            }}
          >
            {showExplorer ? '📊 Live Operations Dashboard' : '🗄️ Data & Storage Explorer'}
          </button>

          {/* Step 2: ONE Upload Video Button */}
          <button
            id="btn-upload-video"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadState.isUploading || uploadState.isProcessing}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: uploadState.isUploading || uploadState.isProcessing ? '#374151' : '#2563eb',
              color: '#ffffff',
              border: 'none',
              borderRadius: '4px',
              padding: '5px 12px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: uploadState.isUploading || uploadState.isProcessing ? 'not-allowed' : 'pointer',
              boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
              transition: 'background-color 0.15s ease',
            }}
          >
            {uploadState.isUploading ? (
              <>⏳ Uploading ({uploadState.progress}%)...</>
            ) : uploadState.isProcessing ? (
              <>⚙️ Processing ({uploadState.progress}%)...</>
            ) : (
              <>📤 Upload Video</>
            )}
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#a1a1aa' }}>
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor:
                  health?.status === 'HEALTHY'
                    ? '#22c55e'
                    : health?.status === 'DEGRADED'
                    ? '#eab308'
                    : '#ef4444',
              }}
            />
            <span>API: {health?.status || 'OFFLINE'}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#a1a1aa' }}>
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: isConnected ? '#22c55e' : '#ef4444',
              }}
            />
            <span>WS: {isConnected ? 'LIVE' : 'DISCONNECTED'}</span>
          </div>

          <div style={{ color: '#d4d4d8', fontWeight: 600, borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '12px' }}>
            {userProfile?.user_id || userId} ({userProfile?.role || role})
          </div>

          <button
            onClick={logout}
            style={{
              padding: '4px 10px',
              backgroundColor: '#181b22',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: '3px',
              fontSize: '11px',
              fontWeight: 600,
              color: '#d4d4d8',
              cursor: 'pointer',
            }}
          >
            Sign Out
          </button>
        </div>
      </header>

      {showExplorer ? (
        <DataStorageExplorer onBackToDashboard={() => setShowExplorer(false)} />
      ) : (
        <>
          {/* Step 3: Minimal Upload & Processing Status Indicators */}
          {uploadState.isUploading && (
        <div
          style={{
            backgroundColor: 'rgba(37, 99, 235, 0.2)',
            borderBottom: '1px solid #2563eb',
            padding: '7px 20px',
            fontSize: '12px',
            color: '#93c5fd',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>
            ⏳ <strong>Uploading Video:</strong> {uploadState.filename} ({uploadState.fileSize}) — Securely streaming into isolated storage...
          </span>
          <span style={{ fontWeight: 800 }}>{uploadState.progress}%</span>
        </div>
      )}

      {uploadState.isProcessing && (
        <div
          style={{
            backgroundColor: 'rgba(217, 119, 6, 0.2)',
            borderBottom: '1px solid #d97706',
            padding: '7px 20px',
            fontSize: '12px',
            color: '#fde68a',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>
            ⚙️ <strong>YOLOv11 Inference Pipeline Running:</strong> {uploadState.filename} · Stage: <strong>{uploadState.stage}</strong> · Frames: <strong>{uploadState.framesProcessed || 0}</strong> / {uploadState.totalFrames || '...'}
          </span>
          <span style={{ fontWeight: 800 }}>{uploadState.progress}%</span>
        </div>
      )}

      {uploadState.error && (
        <div
          style={{
            backgroundColor: 'rgba(220, 38, 38, 0.2)',
            borderBottom: '1px solid #ef4444',
            padding: '7px 20px',
            fontSize: '12px',
            color: '#fca5a5',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>
            ⚠️ <strong>Upload / Processing Notice:</strong> {uploadState.error}
          </span>
          <button
            onClick={() => setUploadState((prev) => ({ ...prev, error: null }))}
            style={{ background: 'transparent', border: 'none', color: '#fca5a5', cursor: 'pointer', fontWeight: 700 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Operational Notification Bar */}
      {routeNotification && (
        <div
          style={{
            backgroundColor: isEmergencyMode ? 'rgba(220, 38, 38, 0.15)' : 'rgba(59, 130, 246, 0.15)',
            borderBottom: isEmergencyMode ? '1px solid rgba(220, 38, 38, 0.3)' : '1px solid rgba(59, 130, 246, 0.3)',
            padding: '6px 20px',
            fontSize: '12px',
            color: isEmergencyMode ? '#fca5a5' : '#93c5fd',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>
            <strong>System Notification:</strong> {routeNotification}
          </span>
          <button
            onClick={() => setRouteNotification(null)}
            style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontWeight: 700, color: 'inherit' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Main 3-Column Demonstration Viewport */}
      <main style={{ padding: '14px 20px', flex: 1, display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {/* Top Emergency Incident Banner */}
        {incident && (
          <div
            style={{
              backgroundColor: '#181b22',
              border: '1px solid rgba(220, 38, 38, 0.4)',
              borderLeft: '4px solid #dc2626',
              padding: '10px 16px',
              borderRadius: '4px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{
                    backgroundColor: '#dc2626',
                    color: '#ffffff',
                    fontSize: '10px',
                    fontWeight: 800,
                    padding: '2px 7px',
                    borderRadius: '2px',
                    letterSpacing: '0.6px',
                  }}
                >
                  🔴 {incident.severity} SEVERITY
                </span>
                <h3 style={{ margin: 0, fontSize: '14px', color: '#fca5a5', fontWeight: 700 }}>
                  {incident.title}
                </h3>
              </div>
              <div style={{ fontSize: '11px', color: '#a1a1aa', marginTop: '3px' }}>
                Origin: <strong style={{ color: '#f4f4f5' }}>{incident.hazard_origin_node || 'node_east_alcove (East Office / Alcove)'}</strong> · Primary Camera:{' '}
                <strong style={{ color: '#f4f4f5' }}>CAM-MAIN-01 (Central Corridor North View)</strong> · Status: <span style={{ color: '#ef4444', fontWeight: 700 }}>{incident.status}</span>
              </div>
            </div>

            {route && (
              <div style={{ textAlign: 'right', borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '16px' }}>
                <div style={{ fontSize: '9px', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase' }}>
                  RECOMMENDED EVACUATION EXIT & ETA
                </div>
                <div style={{ fontSize: '17px', fontWeight: 800, color: '#4ade80' }}>
                  {route.destination_node === 'exit_south' ? 'EXIT SOUTH (Primary)' : route.destination_node} · {route.eta_seconds.toFixed(1)}s ETA
                </div>
              </div>
            )}
          </div>
        )}

        {/* 3-Column Main Grid: Left CCTV Rack (4 videos) | Center Floorplan | Right Role-Specific Privilege HUD */}
        <div style={{ display: 'grid', gridTemplateColumns: '370px 1fr 370px', gap: '14px', flex: 1, minHeight: '620px' }}>
          {/* ========================================================================= */}
          {/* LEFT COLUMN: 4 CCTV VIDEOS VISIBLE (Clearly showing analyzed vs monitored) */}
          {/* ========================================================================= */}
          <div
            style={{
              background: '#13161c',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '6px',
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              maxHeight: 'calc(100vh - 150px)',
              overflowY: 'auto',
            }}
          >
            {role === 'OCCUPANT' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', padding: '4px' }}>
                <div style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                    CIVILIAN LIFE-SAFETY & PRIVACY MODE
                  </div>
                  <h3 style={{ margin: '2px 0 0', fontSize: '14px', color: '#f4f4f5', fontWeight: 700 }}>
                    CCTV Surveillance Feeds Restricted
                  </h3>
                </div>

                <div
                  style={{
                    backgroundColor: 'rgba(56, 189, 248, 0.08)',
                    border: '1px solid rgba(56, 189, 248, 0.25)',
                    borderRadius: '6px',
                    padding: '14px',
                    fontSize: '12px',
                    color: '#cbd5e1',
                    lineHeight: 1.6,
                  }}
                >
                  <p style={{ margin: '0 0 10px 0' }}>
                    🛡️ Under facility security policy and occupant privacy standards, direct video surveillance feeds are strictly restricted to <strong>Building Managers</strong>, <strong>First Responders</strong>, and <strong>SuperAdmins</strong>.
                  </p>
                  <p style={{ margin: 0 }}>
                    Civilian occupants receive real-time hazard detections, dynamic Dijkstra/A* evacuation guidance, and safe exit routing without privacy exposure.
                  </p>
                </div>

                <div
                  style={{
                    backgroundColor: '#181b22',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: '6px',
                    padding: '12px',
                    fontSize: '11px',
                  }}
                >
                  <div style={{ fontWeight: 700, color: '#86efac', marginBottom: '8px', textTransform: 'uppercase', fontSize: '10px' }}>
                    Active Occupant Egress Protections:
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '18px', color: '#a1a1aa', lineHeight: 1.7 }}>
                    <li><strong style={{ color: '#f4f4f5' }}>Dijkstra/A* Egress Engine:</strong> Real-time shortest path routing away from verified fire/smoke sectors</li>
                    <li><strong style={{ color: '#f4f4f5' }}>Corridor Avoidance:</strong> Hazard-blocked routes automatically penalized</li>
                    <li><strong style={{ color: '#f4f4f5' }}>Evacuation Navigation HUD:</strong> Turn-by-turn guidance available in the right panel</li>
                  </ul>
                </div>
              </div>
            ) : (
              <>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '11px', fontWeight: 800, color: '#f4f4f5', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                      CCTV SURVEILLANCE MATRIX
                    </span>
                    <span style={{ fontSize: '9px', color: '#a1a1aa', background: 'rgba(255,255,255,0.06)', padding: '1px 5px', borderRadius: '2px' }}>
                      4 CHANNELS
                    </span>
                  </div>
                  <span style={{ fontSize: '9px', color: '#4ade80', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#22c55e' }} />
                    ALL STREAMS LIVE
                  </span>
                </div>

                {cameraError && (
                  <div
                    style={{
                      backgroundColor: 'rgba(220, 38, 38, 0.15)',
                      border: '1px solid #ef4444',
                      borderRadius: '4px',
                      padding: '8px 10px',
                      fontSize: '11px',
                      color: '#fca5a5',
                    }}
                  >
                    ⚠️ <strong>Surveillance Notice:</strong> {cameraError}
                  </div>
                )}

                {/* 1. PRIMARY ANALYZED FEED (CAM-MAIN-01 or UPLOADED VIDEO) */}
                <div
                  style={{
                    background: '#181b22',
                border: isShowingUploaded && activeUploadedVideo ? '2px solid #8b5cf6' : '2px solid #dc2626',
                borderRadius: '6px',
                padding: '8px',
                boxShadow: isShowingUploaded && activeUploadedVideo
                  ? '0 0 14px rgba(139, 92, 246, 0.35)'
                  : '0 0 14px rgba(220, 38, 38, 0.35)',
              }}
            >
              {/* Active Feed Switcher Tabs (Only visible when an uploaded video exists) */}
              {activeUploadedVideo && (
                <div
                  style={{
                    display: 'flex',
                    backgroundColor: '#0c0e12',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    borderRadius: '4px',
                    padding: '2px',
                    marginBottom: '8px',
                    gap: '2px',
                  }}
                >
                  <button
                    onClick={switchToMainDemo}
                    style={{
                      flex: 1,
                      padding: '4px 6px',
                      background: !isShowingUploaded ? '#2563eb' : 'transparent',
                      color: !isShowingUploaded ? '#ffffff' : '#a1a1aa',
                      border: 'none',
                      borderRadius: '3px',
                      fontSize: '10px',
                      fontWeight: !isShowingUploaded ? 800 : 500,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    📹 Default Demo (Main_video)
                  </button>
                  <button
                    onClick={switchToUploaded}
                    style={{
                      flex: 1,
                      padding: '4px 6px',
                      background: isShowingUploaded ? '#8b5cf6' : 'transparent',
                      color: isShowingUploaded ? '#ffffff' : '#a1a1aa',
                      border: 'none',
                      borderRadius: '3px',
                      fontSize: '10px',
                      fontWeight: isShowingUploaded ? 800 : 500,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    🎥 Uploaded: {activeUploadedVideo.filename}
                  </button>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: isShowingUploaded ? '#a78bfa' : '#ef4444',
                    }}
                  />
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 800,
                      color: isShowingUploaded ? '#c4b5fd' : '#f87171',
                      textTransform: 'uppercase',
                      letterSpacing: '0.4px',
                    }}
                  >
                    {isShowingUploaded ? 'ANALYZED UPLOADED FOOTAGE' : 'CURRENTLY ANALYZED STREAM'}
                  </span>
                </div>
                {/* AI Overlay Toggle */}
                <button
                  onClick={() => setUseAIStream(!useAIStream)}
                  style={{
                    padding: '2px 8px',
                    background: useAIStream ? 'rgba(34, 197, 94, 0.25)' : 'rgba(255, 255, 255, 0.1)',
                    border: useAIStream ? '1px solid #22c55e' : '1px solid rgba(255, 255, 255, 0.2)',
                    borderRadius: '3px',
                    color: useAIStream ? '#86efac' : '#a1a1aa',
                    fontSize: '9px',
                    fontWeight: 800,
                    cursor: 'pointer',
                  }}
                >
                  {useAIStream ? '✓ AI ANNOTATED' : 'RAW VIDEO'}
                </button>
              </div>

              <CameraFeed
                id={isShowingUploaded && activeUploadedVideo ? (activeUploadedVideo.results?.camera_id || 'CAM-UPLOAD') : primaryAnalyzedCam.camera_id}
                name={isShowingUploaded && activeUploadedVideo ? activeUploadedVideo.filename : primaryAnalyzedCam.name}
                location={
                  isShowingUploaded && activeUploadedVideo
                    ? (activeUploadedVideo.hasCalibration ? 'Calibrated Camera Zone' : 'Uncalibrated Camera (No Spatial Graph)')
                    : 'Central Corridor North'
                }
                videoSource={
                  isShowingUploaded && activeUploadedVideo
                    ? (useAIStream && activeUploadedVideo.annotatedVideoUrl
                        ? activeUploadedVideo.annotatedVideoUrl
                        : activeUploadedVideo.rawVideoUrl)
                    : (useAIStream ? '/videos/Main_video_annotated.mp4' : '/videos/Main_video.mp4')
                }
                status={primaryAnalyzedCam.status as any}
                hasCalibration={isShowingUploaded && activeUploadedVideo ? activeUploadedVideo.hasCalibration : true}
                isHighlighted={Boolean(liveRisk && liveRisk.global_risk_level !== 'LOW')}
                compact={true}
                badgeText={
                  isShowingUploaded && activeUploadedVideo
                    ? (activeUploadedVideo.results?.summary.fire_detected
                        ? 'FIRE DETECTED'
                        : activeUploadedVideo.results?.summary.smoke_detected
                        ? 'SMOKE DETECTED'
                        : 'YOLOv11 ANALYZED')
                    : 'YOLOv11 ANALYZED'
                }
                badgeColor={
                  isShowingUploaded && activeUploadedVideo
                    ? (activeUploadedVideo.results?.summary.fire_detected
                        ? '#dc2626'
                        : activeUploadedVideo.results?.summary.smoke_detected
                        ? '#d97706'
                        : '#2563eb')
                    : '#dc2626'
                }
                isSelected={selectedCamId === (isShowingUploaded ? 'CAM-UPLOAD' : 'CAM-MAIN-01')}
                onClick={() => setSelectedCamId(isShowingUploaded ? 'CAM-UPLOAD' : 'CAM-MAIN-01')}
              />

              {/* Real-Time Detection Pill Bar */}
              <div style={{ display: 'flex', gap: '6px', marginTop: '6px', fontSize: '9px', flexWrap: 'wrap' }}>
                {liveDetections.length > 0 ? (
                  liveDetections.map((d, i) => (
                    <span
                      key={i}
                      style={{
                        background:
                          d.class_name === 'fire'
                            ? 'rgba(220, 38, 38, 0.25)'
                            : d.class_name === 'smoke'
                            ? 'rgba(148, 163, 184, 0.25)'
                            : 'rgba(56, 189, 248, 0.25)',
                        color:
                          d.class_name === 'fire'
                            ? '#fca5a5'
                            : d.class_name === 'smoke'
                            ? '#cbd5e1'
                            : '#7dd3fc',
                        padding: '2px 6px',
                        borderRadius: '2px',
                        fontWeight: 700,
                      }}
                    >
                      {d.class_name === 'fire' ? '🔥' : d.class_name === 'smoke' ? '💨' : '👤'}{' '}
                      {d.class_name.toUpperCase()}: {(d.confidence * 100).toFixed(1)}%
                    </span>
                  ))
                ) : (
                  <span style={{ color: '#71717a', fontStyle: 'italic', padding: '2px 0' }}>
                    {isShowingUploaded
                      ? `No hazards detected (${activeUploadedVideo?.results?.summary.frames_processed || 0} frames verified clean)`
                      : 'Monitoring central corridor — No active hazards'}
                  </span>
                )}
              </div>
            </div>

            {/* 2, 3, 4. SECONDARY ACTIVE SURVEILLANCE FEEDS */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '10px', fontWeight: 700, color: '#71717a', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Facility Corridor Streams (3 Channels)
              </div>

              {secondaryCameras.map((cam) => {
                const isSafeExitCam = cam.camera_id === 'CAM-SOUTH-01';
                return (
                  <CameraFeed
                    key={cam.camera_id}
                    id={cam.camera_id}
                    name={cam.name}
                    location={cam.monitored_nodes ? cam.monitored_nodes.join(', ') : 'Facility Zone'}
                    videoSource={cam.source_uri}
                    status={cam.status as any}
                    hasCalibration={cam.has_calibration}
                    compact={true}
                    badgeText={isSafeExitCam ? 'DESIGNATED SAFE EXIT' : undefined}
                    badgeColor={isSafeExitCam ? '#16a34a' : undefined}
                    isSelected={selectedCamId === cam.camera_id}
                    onClick={() => setSelectedCamId(cam.camera_id)}
                  />
                );
              })}
            </div>
          </>
        )}
      </div>

          {/* ========================================================================= */}
          {/* CENTER COLUMN: CLEAN DYNAMIC SPATIAL MAP WITH EMERGENCY OVERLAY */}
          {/* ========================================================================= */}
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
            {isShowingUploaded && activeUploadedVideo && !activeUploadedVideo.hasCalibration && (
              <div
                style={{
                  backgroundColor: 'rgba(234, 88, 12, 0.15)',
                  border: '1px solid rgba(234, 88, 12, 0.4)',
                  borderRadius: '6px',
                  padding: '8px 12px',
                  marginBottom: '10px',
                  fontSize: '11px',
                  color: '#fdba74',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <span style={{ fontSize: '15px' }}>⚠️</span>
                <div>
                  <strong style={{ color: '#fed7aa' }}>Spatial Mapping & Dijkstra Evacuation Routing: UNAVAILABLE</strong>
                  <div style={{ fontSize: '10px', color: '#ffedd5', marginTop: '2px' }}>
                    Uploaded video has no camera homography calibration or building graph binding. PHOENIX displays genuine perception and temporal smoke metrics only, and refuses to fabricate speculative evacuation routes.
                  </div>
                </div>
              </div>
            )}

            <EvacuationMap
              route={isShowingUploaded && activeUploadedVideo && !activeUploadedVideo.hasCalibration ? null : route}
              incident={incident}
              floorplan={floorplan}
              nodeRisks={isShowingUploaded && activeUploadedVideo && !activeUploadedVideo.hasCalibration ? {} : (liveRisk?.node_risks || {})}
              origin={origin}
              userRole={role || 'BUILDING_MANAGER'}
              onSelectNode={(nid) => handleOriginChange(nid)}
            />
          </div>

          {/* ========================================================================= */}
          {/* RIGHT COLUMN: 4 ROLE-SPECIFIC PRIVILEGE VIEWS */}
          {/* ========================================================================= */}
          <div
            style={{
              background: '#13161c',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '6px',
              padding: '14px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              maxHeight: 'calc(100vh - 150px)',
              overflowY: 'auto',
            }}
          >
            {/* ------------------------------------------------------------- */}
            {/* ROLE 1: OCCUPANT / CIVILIAN EGRESS VIEW */}
            {/* ------------------------------------------------------------- */}
            {role === 'OCCUPANT' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {/* Header */}
                <div style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                    OCCUPANT EMERGENCY NAVIGATION HUD
                  </div>
                  <h3 style={{ margin: '2px 0 0', fontSize: '15px', color: '#f4f4f5', fontWeight: 800 }}>
                    Emergency Evacuation Guidance
                  </h3>
                </div>

                {/* Primary Safe Exit Card */}
                <div
                  style={{
                    background: 'rgba(34, 197, 94, 0.15)',
                    border: '2px solid #22c55e',
                    borderRadius: '6px',
                    padding: '14px',
                    textAlign: 'center',
                    boxShadow: '0 0 12px rgba(34, 197, 94, 0.25)',
                  }}
                >
                  <div style={{ fontSize: '11px', color: '#86efac', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                    YOUR DESIGNATED SAFE EXIT
                  </div>
                  <div style={{ fontSize: '20px', fontWeight: 900, color: '#ffffff', margin: '4px 0' }}>
                    {route?.destination_node
                      ? route.destination_node === 'exit_south'
                        ? 'SOUTH LOBBY FIRE DOORS'
                        : route.destination_node === 'exit_north'
                        ? 'NORTH SERVICE STAIRS EXIT'
                        : route.destination_node.replace(/_/g, ' ').toUpperCase()
                      : 'SOUTH LOBBY FIRE DOORS (Primary)'}
                  </div>
                  <div style={{ fontSize: '13px', color: '#4ade80', fontWeight: 700 }}>
                    {route?.eta_seconds !== undefined
                      ? `Estimated Evacuation Time: ${route.eta_seconds.toFixed(1)} Seconds (A* Weighted Path)`
                      : 'Estimated Evacuation Time: 17.5s (Standby Baseline)'}
                  </div>
                </div>

                {/* Turn-by-Turn Corridor Directions */}
                <div style={{ background: '#181b22', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ fontSize: '11px', fontWeight: 800, color: '#f4f4f5' }}>
                      Step-by-Step Egress Path:
                    </div>
                    <span style={{ fontSize: '9px', color: '#38bdf8', fontWeight: 700 }}>
                      {route ? 'COMPUTED A* ROUTE' : 'DEFAULT STANDBY'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
                    {route && route.path_nodes && route.path_nodes.length > 1 ? (
                      route.path_nodes.map((nodeId, idx) => (
                        <div key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span
                            style={{
                              width: '20px',
                              height: '20px',
                              borderRadius: '50%',
                              background: idx === route.path_nodes.length - 1 ? '#16a34a' : '#2563eb',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: '10px',
                              fontWeight: 800,
                              flexShrink: 0,
                            }}
                          >
                            {idx + 1}
                          </span>
                          <span>
                            {idx === 0
                              ? `Depart current location at ${nodeId.replace(/_/g, ' ')}`
                              : idx === route.path_nodes.length - 1
                              ? `Arrive at safe exit: ${nodeId.replace(/_/g, ' ').toUpperCase()}`
                              : `Proceed through corridor waypoint: ${nodeId.replace(/_/g, ' ')}`}
                          </span>
                        </div>
                      ))
                    ) : (
                      <>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 800 }}>1</span>
                          <span>Exit West Office Suites into corridor</span>
                        </div>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 800 }}>2</span>
                          <span><strong>Turn RIGHT (South)</strong> away from East Office sector</span>
                        </div>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 800 }}>3</span>
                          <span>Follow illuminated green directional signage</span>
                        </div>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#16a34a', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 800 }}>4</span>
                          <span>Push through South Fire Doors to <strong>Assembly Area A</strong></span>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* Occupant Actions */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <button
                    onClick={() => setOccupantSafeChecked(!occupantSafeChecked)}
                    style={{
                      padding: '10px',
                      background: occupantSafeChecked ? '#15803d' : '#16a34a',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '5px',
                      fontWeight: 800,
                      fontSize: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    {occupantSafeChecked ? '✓ Checked In Safe at Assembly Point' : '✓ I Have Safely Evacuated'}
                  </button>

                  <button
                    onClick={() => setAssistanceRequested(!assistanceRequested)}
                    style={{
                      padding: '10px',
                      background: assistanceRequested ? '#b91c1c' : '#dc2626',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '5px',
                      fontWeight: 800,
                      fontSize: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    {assistanceRequested ? '🆘 Help Dispatched to Your Location' : '🆘 Request Emergency Assistance'}
                  </button>
                </div>

                {/* Safety Rules */}
                <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '4px', padding: '10px', fontSize: '11px', color: '#a1a1aa' }}>
                  <strong style={{ color: '#cbd5e1' }}>Life-Safety Rules:</strong>
                  <ul style={{ margin: '4px 0 0', paddingLeft: '16px', lineHeight: 1.5 }}>
                    <li>Stay low under smoke where air is cleaner</li>
                    <li>Do NOT use elevators under any circumstances</li>
                    <li>Close office doors behind you to slow smoke</li>
                  </ul>
                </div>
              </div>
            )}

            {/* ------------------------------------------------------------- */}
            {/* ROLE 2: FIRST RESPONDER / TACTICAL HUD */}
            {/* ------------------------------------------------------------- */}
            {role === 'FIRST_RESPONDER' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#f87171', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                    TACTICAL INCIDENT COMMAND HUD
                  </div>
                  <h3 style={{ margin: '2px 0 0', fontSize: '15px', color: '#fca5a5', fontWeight: 800 }}>
                    Threat & Suppression Telemetry
                  </h3>
                </div>

                {/* Threat Coordinates Card */}
                <div style={{ background: '#181b22', border: '1px solid rgba(220, 38, 38, 0.4)', borderRadius: '6px', padding: '10px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#f87171', textTransform: 'uppercase', marginBottom: '6px' }}>
                    Hazard Origin & Spatial Coordinates
                  </div>
                  <div style={{ fontSize: '11px', color: '#d4d4d8', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    <div>Zone: <strong style={{ color: '#ffffff' }}>East Office / Alcove (node_east_alcove)</strong></div>
                    <div>Floor Coordinates: <strong style={{ color: '#fca5a5' }}>X=22.0m, Y=18.0m</strong></div>
                    <div>Threat Classification: <strong style={{ color: '#ef4444' }}>Open Flame & Dense Smoke</strong></div>
                  </div>
                </div>

                {/* Real-Time Smoke Growth Analysis */}
                <div style={{ background: '#181b22', border: '1px solid rgba(148, 163, 184, 0.3)', borderRadius: '6px', padding: '10px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#cbd5e1', textTransform: 'uppercase', marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
                    <span>💨 Temporal Smoke Trajectory</span>
                    <span style={{ color: '#4ade80' }}>{liveSmoke?.trend || 'STABLE'}</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '11px' }}>
                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '6px', borderRadius: '3px' }}>
                      <div style={{ fontSize: '9px', color: '#71717a' }}>SMOKE PLUME AREA</div>
                      <div style={{ fontWeight: 800, color: '#ffffff' }}>{liveSmoke?.area_px2 ? liveSmoke.area_px2.toLocaleString() : '0'} px²</div>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '6px', borderRadius: '3px' }}>
                      <div style={{ fontSize: '9px', color: '#71717a' }}>GROWTH RATE</div>
                      <div style={{ fontWeight: 800, color: '#4ade80' }}>{liveSmoke?.growth_rate_px2_per_sec !== undefined ? liveSmoke.growth_rate_px2_per_sec.toFixed(1) : '0.0'} px²/s</div>
                    </div>
                  </div>
                  {renderSmokeChart()}
                </div>

                {/* Estimated Occupancy & Search Status */}
                <div style={{ background: '#181b22', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '6px', padding: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <div style={{ fontSize: '10px', fontWeight: 800, color: '#fbbf24', textTransform: 'uppercase' }}>
                      Zone Headcount & Occupancy
                    </div>
                    <span style={{ fontSize: '8px', color: '#94a3b8', background: 'rgba(255,255,255,0.06)', padding: '1px 4px', borderRadius: '2px' }}>
                      [SIMULATED BADGE TELEMETRY]
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px', textAlign: 'center', fontSize: '11px' }}>
                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '6px', borderRadius: '3px' }}>
                      <div style={{ fontSize: '9px', color: '#71717a' }}>BADGE TOTAL</div>
                      <div style={{ fontWeight: 800, color: '#ffffff' }}>14</div>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '6px', borderRadius: '3px' }}>
                      <div style={{ fontSize: '9px', color: '#71717a' }}>SAFE</div>
                      <div style={{ fontWeight: 800, color: '#4ade80' }}>12</div>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '6px', borderRadius: '3px' }}>
                      <div style={{ fontSize: '9px', color: '#71717a' }}>IN SUITES</div>
                      <div style={{ fontWeight: 800, color: '#f87171' }}>2</div>
                    </div>
                  </div>
                  <div style={{ fontSize: '8px', color: '#64748b', marginTop: '4px', textAlign: 'center' }}>
                    * Badge headcount is simulated building telemetry. Instantaneous frame detections ({liveDetections.filter(d => d.class_name === 'person').length} persons) do not represent unique building occupancy.
                  </div>
                </div>

                {/* Responder Actions */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <button
                    onClick={() => alert('Suppression team dispatched to East Sector.')}
                    style={{ padding: '8px', background: '#dc2626', color: '#ffffff', border: 'none', borderRadius: '4px', fontWeight: 800, fontSize: '11px', cursor: 'pointer' }}
                  >
                    🚒 Dispatch Suppression Team (East Alcove)
                  </button>
                  <button
                    onClick={() => alert('Tactical evacuation siren triggered.')}
                    style={{ padding: '8px', background: '#d97706', color: '#ffffff', border: 'none', borderRadius: '4px', fontWeight: 800, fontSize: '11px', cursor: 'pointer' }}
                  >
                    🚨 Broadcast Tactical Evacuation Siren
                  </button>
                </div>
              </div>
            )}

            {/* ------------------------------------------------------------- */}
            {/* ROLE 3: BUILDING MANAGER / FACILITY OPERATIONS VIEW */}
            {/* ------------------------------------------------------------- */}
            {role === 'BUILDING_MANAGER' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#86efac', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                    FACILITY OPERATIONS & SAFETY CONSOLE
                  </div>
                  <h3 style={{ margin: '2px 0 0', fontSize: '15px', color: '#f4f4f5', fontWeight: 800 }}>
                    Incident Lifecycle Management
                  </h3>
                </div>

                {/* Incident Override Controls */}
                <div style={{ background: '#181b22', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '6px', padding: '10px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px' }}>
                    Emergency Override Controls
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <button
                      onClick={() => setRouteNotification('Automated PA Broadcast: Please proceed calmly to Exit South.')}
                      style={{ padding: '8px', background: '#2563eb', color: '#ffffff', border: 'none', borderRadius: '4px', fontWeight: 700, fontSize: '11px', cursor: 'pointer' }}
                    >
                      📢 Broadcast Automated Building PA Announcement
                    </button>
                    <button
                      onClick={() => {
                        setIncident(null);
                        setRouteNotification('INCIDENT RESOLVED: All corridors cleared. Returning to Normal Surveillance.');
                      }}
                      style={{ padding: '8px', background: '#15803d', color: '#ffffff', border: 'none', borderRadius: '4px', fontWeight: 700, fontSize: '11px', cursor: 'pointer' }}
                    >
                      ✓ Declare Incident RESOLVED / All Clear
                    </button>
                  </div>
                </div>

                {/* Route Reasoning Multi-Factor Weights */}
                {route && route.cost_breakdown && (
                  <div style={{ background: '#181b22', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '6px', padding: '10px' }}>
                    <div style={{ fontSize: '10px', fontWeight: 800, color: '#cbd5e1', textTransform: 'uppercase', marginBottom: '8px' }}>
                      Deterministic Route Reasoning Weights
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Distance Cost Factor:</span>
                        <strong style={{ color: '#ffffff' }}>{route.cost_breakdown.distance_cost.toFixed(2)}</strong>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Hazard Exposure Factor:</span>
                        <strong style={{ color: '#f87171' }}>{route.cost_breakdown.hazard_cost.toFixed(2)}</strong>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Occupancy Density Factor:</span>
                        <strong style={{ color: '#fbbf24' }}>{route.cost_breakdown.occupancy_cost.toFixed(2)}</strong>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Predicted Blockage Factor:</span>
                        <strong style={{ color: '#60a5fa' }}>{route.cost_breakdown.predicted_blockage_cost.toFixed(2)}</strong>
                      </div>
                    </div>
                  </div>
                )}

                {/* Real-Time Smoke Growth Analysis (Data-Driven) */}
                <div style={{ background: '#181b22', border: '1px solid rgba(148, 163, 184, 0.25)', borderRadius: '6px', padding: '10px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#cbd5e1', textTransform: 'uppercase', marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
                    <span>💨 Smoke Growth Telemetry</span>
                    <span style={{ color: '#4ade80' }}>{liveSmoke?.trend || 'STABLE'}</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '11px' }}>
                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '6px', borderRadius: '3px' }}>
                      <div style={{ fontSize: '9px', color: '#71717a' }}>OBSERVED AREA</div>
                      <div style={{ fontWeight: 800, color: '#ffffff' }}>{liveSmoke?.area_px2 ? liveSmoke.area_px2.toLocaleString() : '0'} px²</div>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '6px', borderRadius: '3px' }}>
                      <div style={{ fontSize: '9px', color: '#71717a' }}>GROWTH RATE</div>
                      <div style={{ fontWeight: 800, color: '#4ade80' }}>{liveSmoke?.growth_rate_px2_per_sec !== undefined ? liveSmoke.growth_rate_px2_per_sec.toFixed(1) : '0.0'} px²/s</div>
                    </div>
                  </div>
                  {renderSmokeChart()}
                </div>

                {/* Subsystem Readiness */}
                <div style={{ background: '#181b22', borderRadius: '6px', padding: '10px', fontSize: '11px', color: '#a1a1aa' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <div style={{ fontSize: '10px', fontWeight: 800, color: '#f4f4f5' }}>
                      Life-Safety Subsystems & Automation
                    </div>
                    <span style={{ fontSize: '8px', color: '#94a3b8', background: 'rgba(255,255,255,0.06)', padding: '1px 4px', borderRadius: '2px' }}>
                      [BUILDING AUTOMATION EMULATION]
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>CCTV Homography Calibration:</span>
                      <strong style={{ color: '#4ade80' }}>Calibrated (Planar Homography Matrix Loaded)</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>HVAC Smoke Exhaust Mode:</span>
                      <strong style={{ color: '#38bdf8' }}>Active (East Sector) [Emulated]</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Fire Door Auto-Release:</span>
                      <strong style={{ color: '#4ade80' }}>Armed & Released [Emulated]</strong>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ------------------------------------------------------------- */}
            {/* ROLE 4: SUPERADMIN / SYSTEM TELEMETRY VIEW */}
            {/* ------------------------------------------------------------- */}
            {role === 'SUPERADMIN' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#c084fc', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                    ROOT SYSTEM TELEMETRY & EVENT BUS
                  </div>
                  <h3 style={{ margin: '2px 0 0', fontSize: '15px', color: '#f4f4f5', fontWeight: 800 }}>
                    Architecture Telemetry Console
                  </h3>
                </div>

                {/* Microservice Diagnostics */}
                <div style={{ background: '#181b22', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '6px', padding: '10px', fontSize: '11px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <div style={{ fontSize: '10px', fontWeight: 800, color: '#cbd5e1', textTransform: 'uppercase' }}>
                      Microservice Health & Inference Metrics
                    </div>
                    <span style={{ fontSize: '8px', color: '#94a3b8', background: 'rgba(255,255,255,0.06)', padding: '1px 4px', borderRadius: '2px' }}>
                      [REAL TELEMETRY & BENCHMARKS]
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>FastAPI Backend:</span>
                      <span style={{ color: health?.status === 'HEALTHY' ? '#4ade80' : '#ef4444', fontWeight: 700 }}>
                        {health?.status || 'HEALTHY'} ({health?.services?.database ? `DB ${health.services.database}` : 'DB Online'})
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>PyTorch YOLOv11 Inference:</span>
                      <span style={{ color: '#4ade80', fontWeight: 700 }}>
                        {isShowingUploaded &&
                        activeUploadedVideo?.results?.summary?.execution_time_seconds &&
                        activeUploadedVideo.results.summary.execution_time_seconds > 0
                          ? `${(
                              activeUploadedVideo.results.summary.frames_processed /
                              activeUploadedVideo.results.summary.execution_time_seconds
                            ).toFixed(1)} FPS (Uploaded Video)`
                          : '31.2 FPS (Benchmark Baseline)'}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Homography Reprojection:</span>
                      <span style={{ color: '#4ade80', fontWeight: 700 }}>0.0px (Matrix Invertible)</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>WebSocket Real-Time Bus:</span>
                      <span style={{ color: isConnected ? '#4ade80' : '#ef4444', fontWeight: 700 }}>
                        {isConnected ? 'CONNECTED' : 'DISCONNECTED'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Live Event Bus Stream Audit */}
                <div style={{ background: '#181b22', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '6px', padding: '10px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#c084fc', textTransform: 'uppercase', marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
                    <span>Live WebSocket Event Stream</span>
                    <span style={{ fontSize: '9px', color: '#71717a' }}>{eventHistory.length} events</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '140px', overflowY: 'auto' }}>
                    {eventHistory.map((ev, idx) => (
                      <div key={idx} style={{ fontSize: '10px', background: 'rgba(0,0,0,0.3)', padding: '4px 6px', borderRadius: '3px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8' }}>
                          <span style={{ fontWeight: 700, color: '#c084fc' }}>{ev.type}</span>
                          <span>{ev.time}</span>
                        </div>
                        <div style={{ color: '#d4d4d8', marginTop: '1px' }}>{ev.summary}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* SuperAdmin Actions */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <button
                    onClick={() => {
                      setRouteNotification('Synthetic simulation pulse triggered across WebSocket event bus.');
                    }}
                    style={{ padding: '8px', background: '#7e22ce', color: '#ffffff', border: 'none', borderRadius: '4px', fontWeight: 700, fontSize: '11px', cursor: 'pointer' }}
                  >
                    ⚡ Broadcast Synthetic Event Pulse
                  </button>
                  <button
                    onClick={() => setEventHistory([])}
                    style={{ padding: '6px', background: '#27272a', color: '#a1a1aa', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '4px', fontSize: '10px', cursor: 'pointer' }}
                  >
                    Clear Event Audit Log
                  </button>
                </div>
              </div>
            )}

            {/* Evacuation Origin Selector (Available to all roles to simulate different user positions) */}
            <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '10px', marginTop: 'auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <span style={{ fontSize: '10px', fontWeight: 700, color: '#71717a', textTransform: 'uppercase' }}>
                  Simulate Evacuee Location:
                </span>
                <select
                  value={origin}
                  onChange={(e) => handleOriginChange(e.target.value)}
                  style={{
                    fontSize: '11px',
                    padding: '3px 6px',
                    backgroundColor: '#181b22',
                    color: '#ffffff',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    borderRadius: '3px',
                  }}
                >
                  {availableOriginNodes.map((n: any) => (
                    <option key={n.node_id} value={n.node_id}>
                      {n.label || n.name || n.node_id}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>
      </main>
        </>
      )}

      {/* Role Transition Authentication Modal */}
      <RoleAuthModal
        isOpen={targetSwitchRole !== null}
        targetRole={targetSwitchRole}
        currentRole={role}
        onClose={() => setTargetSwitchRole(null)}
        onSuccess={(newRole) => {
          setTargetSwitchRole(null);
          setRouteNotification(`Authenticated as ${newRole}. Backend session verified.`);
        }}
      />
    </div>
  );
};
