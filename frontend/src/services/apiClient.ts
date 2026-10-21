import type {
  BuildingResponse,
  CameraResponse,
  FloorplanModelResponse,
  HealthCheckResponse,
  IncidentResponse,
  JobResultsResponse,
  LoginRequest,
  ProcessingJobResponse,
  ReadinessResponse,
  RouteRecommendationResponse,
  TokenResponse,
  UserResponse,
  StorageOverviewResponse,
  UserInventoryResponse,
  DatabaseInventoryResponse,
  JobsInventoryResponse,
  JobSampleResponse,
  VideoSourceResponse,
} from '../types/phoenix';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export class ApiClient {
  private static token: string | null = localStorage.getItem('phoenix_token');

  public static setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('phoenix_token', token);
    } else {
      localStorage.removeItem('phoenix_token');
    }
  }

  public static getToken(): string | null {
    return this.token;
  }

  private static async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const isFormData = options.body instanceof FormData;
    const headers: Record<string, string> = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      if (response.status === 401 && endpoint !== '/auth/login') {
        this.setToken(null);
        localStorage.removeItem('phoenix_user_id');
        localStorage.removeItem('phoenix_role');
        localStorage.removeItem('phoenix_org_id');
        window.dispatchEvent(new Event('auth_expired'));
      }
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || `API Error ${response.status}`);
    }

    return response.json();
  }

  public static async authenticate(req: LoginRequest): Promise<TokenResponse> {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || `Authentication failed (${response.status})`);
    }

    return response.json();
  }

  public static async fetchProfileWithToken(token: string): Promise<UserResponse> {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || `Failed to fetch profile (${response.status})`);
    }

    return response.json();
  }

  public static async logoutUser(): Promise<void> {
    if (this.token) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({}),
        });
      } catch (err) {
        console.warn('Backend logout call notification failed:', err);
      }
    }
    this.setToken(null);
    localStorage.removeItem('phoenix_user_id');
    localStorage.removeItem('phoenix_role');
    localStorage.removeItem('phoenix_org_id');
  }

  public static async login(req: LoginRequest): Promise<TokenResponse> {
    const res = await this.request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(req),
    });
    this.setToken(res.access_token);
    return res;
  }

  public static async getHealth(): Promise<HealthCheckResponse> {
    return this.request<HealthCheckResponse>('/system/health');
  }

  public static async getReadiness(): Promise<ReadinessResponse> {
    return this.request<ReadinessResponse>('/system/ready');
  }

  public static async getCurrentIncident(buildingId?: string): Promise<IncidentResponse | null> {
    const query = buildingId ? `?building_id=${encodeURIComponent(buildingId)}` : '';
    return this.request<IncidentResponse>(`/incidents/current${query}`);
  }

  public static async getCurrentRoute(origin: string = 'room_101', buildingId: string = 'bldg-hq-01'): Promise<RouteRecommendationResponse | null> {
    const query = `?origin=${encodeURIComponent(origin)}&building_id=${encodeURIComponent(buildingId)}`;
    return this.request<RouteRecommendationResponse | null>(`/routes/current${query}`);
  }


  public static async getBuilding(buildingId: string): Promise<BuildingResponse> {
    return this.request<BuildingResponse>(`/buildings/${encodeURIComponent(buildingId)}`);
  }

  public static async getCameras(buildingId?: string): Promise<CameraResponse[]> {
    const query = buildingId ? `?building_id=${encodeURIComponent(buildingId)}` : '';
    return this.request<CameraResponse[]>(`/cameras${query}`);
  }

  public static async getFloorplan(buildingId: string, floorId: string): Promise<FloorplanModelResponse | null> {
    return this.request<FloorplanModelResponse>(`/spatial/floorplans/${encodeURIComponent(buildingId)}/${encodeURIComponent(floorId)}`).catch(() => null);
  }

  public static async calibrateScale(payload: {
    building_id: string;
    floor_id: string;
    point1: { x: number; y: number };
    point2: { x: number; y: number };
    known_distance_meters: number;
  }): Promise<FloorplanModelResponse> {
    return this.request<FloorplanModelResponse>('/spatial/calibrate-scale', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  public static async getRecentDetections(cameraId?: string, limit: number = 50): Promise<any[]> {
    const query = `?limit=${limit}${cameraId ? `&camera_id=${encodeURIComponent(cameraId)}` : ''}`;
    return this.request<any[]>(`/detections/recent${query}`).catch(() => []);
  }

  public static async getCurrentRisk(buildingId: string = 'bldg-hq-01'): Promise<any | null> {
    return this.request<any>(`/risk/current?building_id=${encodeURIComponent(buildingId)}`).catch(() => null);
  }

  public static async getEventHistory(limit: number = 50): Promise<any[]> {
    return this.request<any[]>(`/events/history?limit=${limit}`).catch(() => []);
  }

  public static async listJobs(videoId?: string): Promise<any[]> {
    const query = videoId ? `?video_id=${encodeURIComponent(videoId)}` : '';
    return this.request<any[]>(`/jobs${query}`).catch(() => []);
  }

  public static async uploadVideo(file: File): Promise<VideoSourceResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return this.request<VideoSourceResponse>('/videos/upload', {
      method: 'POST',
      body: formData,
    });
  }

  public static async startJob(
    videoId: string,
    stride: number = 2,
    cameraId?: string
  ): Promise<ProcessingJobResponse> {
    const camQuery = cameraId ? `&camera_id=${encodeURIComponent(cameraId)}` : '&camera_id=CAM-UPLOAD';
    return this.request<ProcessingJobResponse>(
      `/videos/${encodeURIComponent(videoId)}/jobs?stride=${stride}${camQuery}`,
      {
        method: 'POST',
      }
    );
  }

  public static async getJob(jobId: string): Promise<ProcessingJobResponse> {
    return this.request<ProcessingJobResponse>(`/jobs/${encodeURIComponent(jobId)}`);
  }

  public static async getJobResults(jobId: string): Promise<JobResultsResponse> {
    return this.request<JobResultsResponse>(`/jobs/${encodeURIComponent(jobId)}/results`);
  }

  public static async getCurrentUser(): Promise<UserResponse> {
    return this.request<UserResponse>('/auth/me');
  }

  public static async getExplorerOverview(): Promise<StorageOverviewResponse> {
    return this.request<StorageOverviewResponse>('/explorer/overview');
  }

  public static async getExplorerUsers(): Promise<UserInventoryResponse> {
    return this.request<UserInventoryResponse>('/explorer/users');
  }

  public static async getExplorerDatabase(): Promise<DatabaseInventoryResponse> {
    return this.request<DatabaseInventoryResponse>('/explorer/database');
  }

  public static async getExplorerJobs(limit: number = 25, offset: number = 0, status?: string): Promise<JobsInventoryResponse> {
    const statusParam = status ? `&status=${encodeURIComponent(status)}` : '';
    return this.request<JobsInventoryResponse>(`/explorer/jobs?limit=${limit}&offset=${offset}${statusParam}`);
  }

  public static async getExplorerJobSample(jobId: string): Promise<JobSampleResponse> {
    return this.request<JobSampleResponse>(`/explorer/jobs/${encodeURIComponent(jobId)}/sample`);
  }

  public static getExplorerExportUrl(): string {
    const token = this.getToken();
    return `${API_BASE_URL}/explorer/export${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  }

  public static getAnnotatedVideoUrl(jobId: string): string {
    const token = this.getToken();
    return `${API_BASE_URL}/jobs/${encodeURIComponent(jobId)}/annotated-video${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  }

  public static getRawVideoUrl(videoId: string): string {
    const token = this.getToken();
    return `${API_BASE_URL}/videos/${encodeURIComponent(videoId)}/stream${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  }
}


