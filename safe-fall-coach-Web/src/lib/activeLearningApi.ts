const DEFAULT_BASE_URL = import.meta.env.VITE_ACTIVE_LEARNING_API_URL || 'http://127.0.0.1:8000';
const API_BASE_URL = DEFAULT_BASE_URL.replace(/\/$/, '');

interface ApiErrorShape {
  error?: unknown;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  const text = await response.text();
  let data: unknown = null;

  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    const message = typeof data === 'object' && data !== null && 'error' in (data as ApiErrorShape)
      ? String((data as ApiErrorShape).error)
      : 'Request failed';
    throw new Error(message);
  }

  return data as T;
}

export interface HealthResponse {
  status: string;
  components?: Record<string, unknown>;
  camera_running?: boolean;
  session_active?: boolean;
  mobile_clients?: number;
}

export interface SessionStartResponse {
  status: string;
  session_id: string;
  participant_id: string;
  qr_data?: {
    session_id: string;
    ws_url: string;
  } | null;
}

export interface BodyLandmark {
  index: number;
  x: number;
  y: number;
  score: number;
}

export interface BodyLandmarkPerson {
  landmarks: BodyLandmark[];
}

export interface BodyLandmarkPayload {
  frame_width: number;
  frame_height: number;
  people: BodyLandmarkPerson[];
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

export async function startCamera(cameraIndex = 0): Promise<{ status: string; camera_index: number; session_resumed: boolean }> {
  return request('/camera/start', {
    method: 'POST',
    body: JSON.stringify({ camera_index: cameraIndex }),
  });
}

export async function startSession(participantId = '', useClientCamera = true): Promise<SessionStartResponse> {
  return request('/session/start', {
    method: 'POST',
    body: JSON.stringify({ participant_id: participantId, use_client_camera: useClientCamera }),
  });
}

export async function stopSession(): Promise<unknown> {
  return request('/session/stop', {
    method: 'POST',
  });
}

/**
 * Live state pushed by the server over /ws/state at ~10Hz.
 * Mirrors the dict built in server.py `_build_state()`.
 */
export interface StateMessage {
  type?: string; // present and "ping" for keep-alive frames
  session_active?: boolean;
  paused?: boolean;
  duration_str?: string;
  duration_seconds?: number;
  fall_count?: number;
  pose_score?: number;
  fall_confidence?: number;
  body_landmarks?: BodyLandmarkPayload;
  latest_feedback?: string;
  feedback_id?: number;
  severity?: 'info' | 'warning' | 'success' | 'error' | string;
  component_health?: Record<string, unknown>;
  mobile_clients?: number;
  camera_fps?: number;
  camera_running?: boolean;
}

export function getVideoFeedUrl(): string {
  return `${API_BASE_URL}/video_feed`;
}

export function createStateSocket(): WebSocket {
  const wsProtocol = API_BASE_URL.startsWith('https://') ? 'wss://' : 'ws://';
  const wsOrigin = API_BASE_URL.replace(/^https?:\/\//, '');
  return new WebSocket(`${wsProtocol}${wsOrigin}/ws/state`);
}

/**
 * Webcam ingest socket — pushes this device's camera frames TO the server's
 * /ws/ingest endpoint (used when the engine machine has no local camera).
 * Protocol: one JSON "hello" text frame, then binary JPEG frames. The server
 * runs them through the pipeline and returns feedback via /ws/state.
 */
export function createIngestSocket(): WebSocket {
  const wsProtocol = API_BASE_URL.startsWith('https://') ? 'wss://' : 'ws://';
  const wsOrigin = API_BASE_URL.replace(/^https?:\/\//, '');
  return new WebSocket(`${wsProtocol}${wsOrigin}/ws/ingest`);
}
