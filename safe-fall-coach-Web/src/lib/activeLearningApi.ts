import { supabase } from './supabaseClient';

const DEFAULT_BASE_URL = import.meta.env.VITE_ACTIVE_LEARNING_API_URL || 'http://127.0.0.1:8000';
const API_BASE_URL = DEFAULT_BASE_URL.replace(/\/$/, '');
const ACTIVE_LEARNING_DAILY_SECONDS_LIMIT = 30 * 60;
const ACTIVE_LEARNING_DAILY_SESSION_LIMIT = 20;

interface ApiErrorShape {
  error?: unknown;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch {
    throw new Error(
      `Cannot reach the Active Learning server at ${API_BASE_URL}. Make sure the SSH tunnel is open and the server is running.`
    );
  }

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

export interface ActiveLearningAccess {
  participant_id: string;
  request_status: 'none' | 'pending' | 'approved' | 'rejected' | string;
  enabled: boolean;
  requested_at?: string | null;
  reviewed_at?: string | null;
  daily_limit_seconds: number;
  daily_session_limit: number;
  daily_seconds_used: number;
  daily_seconds_remaining: number;
  daily_sessions_used: number;
  daily_sessions_remaining: number;
}

export interface ActiveLearningAdminList {
  users: ActiveLearningAccess[];
}

type ActiveLearningRequestRow = {
  id: string;
  user_id: string;
  status: string;
  requested_at: string;
  reviewed_at: string | null;
};

type ActiveLearningUserRow = {
  user_id: string;
  active_learning_enabled: boolean | null;
};

function accessFromRows(
  participantId: string,
  requestRow: ActiveLearningRequestRow | null,
  userRow: ActiveLearningUserRow | null,
): ActiveLearningAccess {
  const secondsUsed = 0;
  const sessionsUsed = 0;

  return {
    participant_id: participantId,
    request_status: requestRow?.status ?? 'none',
    enabled: Boolean(userRow?.active_learning_enabled),
    requested_at: requestRow?.requested_at ?? null,
    reviewed_at: requestRow?.reviewed_at ?? null,
    daily_limit_seconds: ACTIVE_LEARNING_DAILY_SECONDS_LIMIT,
    daily_session_limit: ACTIVE_LEARNING_DAILY_SESSION_LIMIT,
    daily_seconds_used: secondsUsed,
    daily_seconds_remaining: ACTIVE_LEARNING_DAILY_SECONDS_LIMIT - secondsUsed,
    daily_sessions_used: sessionsUsed,
    daily_sessions_remaining: ACTIVE_LEARNING_DAILY_SESSION_LIMIT - sessionsUsed,
  };
}

async function loadActiveLearningAccess(participantId: string): Promise<ActiveLearningAccess> {
  const [{ data: requestRow, error: requestError }, { data: userRow, error: userError }] = await Promise.all([
    supabase
      .from('active_learning_requests')
      .select('id, user_id, status, requested_at, reviewed_at')
      .eq('user_id', participantId)
      .maybeSingle(),
    supabase
      .from('users')
      .select('user_id, active_learning_enabled')
      .eq('user_id', participantId)
      .maybeSingle(),
  ]);

  if (requestError) throw requestError;
  if (userError) throw userError;

  return accessFromRows(
    participantId,
    requestRow as ActiveLearningRequestRow | null,
    userRow as ActiveLearningUserRow | null,
  );
}

export interface AnalyticsDashboard {
  activity: {
    dau: number;
    wau: number;
    mau: number;
    growth_trend: Array<{ date: string; active_users: number }>;
  };
  journey: {
    registration_to_onboarding: number;
    onboarding_to_first_training: number;
    first_training_to_week_one: number;
    week_one_to_month_one: number;
  };
  engagement: {
    most_active_days: Array<{ day: string; activity: number }>;
    most_active_times: Array<{ hour: string; activity: number }>;
    session_frequency_patterns: Array<{ bucket: string; users: number }>;
  };
  training: {
    sessions_started: number;
    sessions_completed: number;
    average_completion_rate: number;
    drop_off_rate: number;
  };
  demo_notes: string[];
}

const DEMO_ANALYTICS_DASHBOARD: AnalyticsDashboard = {
  activity: {
    dau: 18,
    wau: 64,
    mau: 148,
    growth_trend: [
      { date: 'Jun 01', active_users: 22 },
      { date: 'Jun 08', active_users: 31 },
      { date: 'Jun 15', active_users: 44 },
      { date: 'Jun 22', active_users: 58 },
      { date: 'Jun 29', active_users: 71 },
      { date: 'Jul 06', active_users: 86 },
    ],
  },
  journey: {
    registration_to_onboarding: 82.4,
    onboarding_to_first_training: 74.1,
    first_training_to_week_one: 66.7,
    week_one_to_month_one: 48.9,
  },
  engagement: {
    most_active_days: [
      { day: 'Mon', activity: 21 },
      { day: 'Tue', activity: 34 },
      { day: 'Wed', activity: 29 },
      { day: 'Thu', activity: 41 },
      { day: 'Fri', activity: 25 },
      { day: 'Sat', activity: 16 },
      { day: 'Sun', activity: 12 },
    ],
    most_active_times: [
      { hour: '8 AM', activity: 12 },
      { hour: '10 AM', activity: 24 },
      { hour: '12 PM', activity: 18 },
      { hour: '2 PM', activity: 31 },
      { hour: '4 PM', activity: 27 },
      { hour: '6 PM', activity: 15 },
    ],
    session_frequency_patterns: [
      { bucket: '1x/week', users: 33 },
      { bucket: '2-3x/week', users: 51 },
      { bucket: '4+x/week', users: 24 },
    ],
  },
  training: {
    sessions_started: 126,
    sessions_completed: 98,
    average_completion_rate: 77.8,
    drop_off_rate: 22.2,
  },
  demo_notes: [
    'Frontend demo analytics are shown when the backend analytics service is unavailable.',
    'Training videos play locally and do not require Active Learning access.',
  ],
};

function demoAnalyticsDashboard(): AnalyticsDashboard {
  return structuredClone(DEMO_ANALYTICS_DASHBOARD);
}

type AnalyticsUserRow = {
  user_id: string;
  created_at: string | null;
  last_login: string | null;
  is_active: boolean | null;
  last_survey_submitted_at: string | null;
  active_learning_enabled: boolean | null;
};

type VideoProgressRow = {
  user_id: string;
  last_watched_at: string | null;
  updated_at: string | null;
  progress_percentage: number | null;
  is_completed: boolean | null;
};

type FallRow = {
  user_id: string | null;
  timestamp: string;
};

type AnalyticsAccessRequestRow = {
  user_id: string;
  status: string;
  requested_at: string;
  reviewed_at: string | null;
};

function asDate(value: string | null | undefined) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function daysAgo(days: number) {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date;
}

function dayKey(date: Date) {
  return date.toISOString().slice(0, 10);
}

function percentOf(numerator: number, denominator: number) {
  return denominator > 0 ? Math.round((numerator / denominator) * 1000) / 10 : 0;
}

function dateLabel(date: Date) {
  return date.toLocaleDateString(undefined, { month: 'short', day: '2-digit' });
}

function buildDatabaseAnalyticsDashboard(
  users: AnalyticsUserRow[],
  progressRows: VideoProgressRow[],
  fallRows: FallRow[],
  requestRows: AnalyticsAccessRequestRow[],
): AnalyticsDashboard {
  const now = new Date();
  const today = dayKey(now);
  const weekStart = daysAgo(6);
  const monthStart = daysAgo(29);
  const userById = new Map(users.map((user) => [user.user_id, user]));

  const activityEvents: Array<{ userId: string; date: Date }> = [];
  for (const user of users) {
    const lastLogin = asDate(user.last_login);
    if (lastLogin) activityEvents.push({ userId: user.user_id, date: lastLogin });
    const createdAt = asDate(user.created_at);
    if (createdAt) activityEvents.push({ userId: user.user_id, date: createdAt });
  }
  for (const row of progressRows) {
    const watchedAt = asDate(row.last_watched_at) ?? asDate(row.updated_at);
    if (watchedAt) activityEvents.push({ userId: row.user_id, date: watchedAt });
  }
  for (const row of fallRows) {
    const timestamp = asDate(row.timestamp);
    if (timestamp && row.user_id) activityEvents.push({ userId: row.user_id, date: timestamp });
  }
  for (const row of requestRows) {
    const requestedAt = asDate(row.requested_at);
    if (requestedAt) activityEvents.push({ userId: row.user_id, date: requestedAt });
  }

  const uniqueUsersSince = (start: Date) => new Set(
    activityEvents
      .filter((event) => event.date >= start)
      .map((event) => event.userId)
  ).size;

  const dau = new Set(
    activityEvents
      .filter((event) => dayKey(event.date) === today)
      .map((event) => event.userId)
  ).size;

  const growthTrend = Array.from({ length: 6 }, (_, index) => {
    const start = daysAgo((5 - index) * 7);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    const activeUsers = new Set(
      activityEvents
        .filter((event) => event.date >= start && event.date <= end)
        .map((event) => event.userId)
    ).size;
    return { date: dateLabel(start), active_users: activeUsers };
  });

  const activeOrLoggedInUsers = users.filter((user) => user.is_active || user.last_login).length;
  const firstTrainingUsers = new Set(progressRows.map((row) => row.user_id));
  const completedUsers = new Set(progressRows.filter((row) => row.is_completed).map((row) => row.user_id));
  const weekOneUsers = new Set(
    progressRows
      .filter((row) => {
        const user = userById.get(row.user_id);
        const createdAt = asDate(user?.created_at);
        const watchedAt = asDate(row.last_watched_at) ?? asDate(row.updated_at);
        if (!createdAt || !watchedAt) return false;
        const sevenDaysAfter = new Date(createdAt);
        sevenDaysAfter.setDate(createdAt.getDate() + 7);
        return watchedAt <= sevenDaysAfter;
      })
      .map((row) => row.user_id)
  );

  const dayCounts = new Map(['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => [day, 0]));
  const hourCounts = new Map<string, number>();
  for (const event of activityEvents) {
    const day = event.date.toLocaleDateString(undefined, { weekday: 'short' });
    dayCounts.set(day, (dayCounts.get(day) ?? 0) + 1);
    const hour = event.date.toLocaleTimeString(undefined, { hour: 'numeric' });
    hourCounts.set(hour, (hourCounts.get(hour) ?? 0) + 1);
  }

  const progressCountByUser = new Map<string, number>();
  for (const row of progressRows) {
    progressCountByUser.set(row.user_id, (progressCountByUser.get(row.user_id) ?? 0) + 1);
  }

  const watchedCounts = [...progressCountByUser.values()];
  const sessionsStarted = progressRows.length;
  const sessionsCompleted = progressRows.filter((row) => row.is_completed).length;
  const progressValues = progressRows
    .map((row) => Number(row.progress_percentage ?? 0))
    .filter((value) => Number.isFinite(value));
  const averageCompletionRate = progressValues.length > 0
    ? Math.round((progressValues.reduce((sum, value) => sum + value, 0) / progressValues.length) * 10) / 10
    : 0;

  return {
    activity: {
      dau,
      wau: uniqueUsersSince(weekStart),
      mau: uniqueUsersSince(monthStart),
      growth_trend: growthTrend,
    },
    journey: {
      registration_to_onboarding: percentOf(activeOrLoggedInUsers, users.length),
      onboarding_to_first_training: percentOf(firstTrainingUsers.size, activeOrLoggedInUsers),
      first_training_to_week_one: percentOf(weekOneUsers.size, firstTrainingUsers.size),
      week_one_to_month_one: percentOf(completedUsers.size, weekOneUsers.size),
    },
    engagement: {
      most_active_days: [...dayCounts.entries()].map(([day, activity]) => ({ day, activity })),
      most_active_times: [...hourCounts.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 6)
        .map(([hour, activity]) => ({ hour, activity })),
      session_frequency_patterns: [
        { bucket: '1 lesson', users: watchedCounts.filter((count) => count === 1).length },
        { bucket: '2-3 lessons', users: watchedCounts.filter((count) => count >= 2 && count <= 3).length },
        { bucket: '4+ lessons', users: watchedCounts.filter((count) => count >= 4).length },
      ],
    },
    training: {
      sessions_started: sessionsStarted,
      sessions_completed: sessionsCompleted,
      average_completion_rate: averageCompletionRate,
      drop_off_rate: percentOf(Math.max(0, sessionsStarted - sessionsCompleted), sessionsStarted),
    },
    demo_notes: [
      `Using ${users.length} users, ${progressRows.length} video progress rows, ${fallRows.length} falls, and ${requestRows.length} access requests from Supabase.`,
      'Active user counts are based on logins, signups, video progress, falls, and access-request activity.',
    ],
  };
}

async function getDatabaseAnalyticsDashboard(): Promise<AnalyticsDashboard> {
  const [{ data: users, error: usersError }, { data: progress, error: progressError }, { data: falls, error: fallsError }, { data: requests, error: requestsError }] = await Promise.all([
    supabase
      .from('users')
      .select('user_id, created_at, last_login, is_active, last_survey_submitted_at, active_learning_enabled'),
    supabase
      .from('video_progress')
      .select('user_id, last_watched_at, updated_at, progress_percentage, is_completed'),
    supabase
      .from('falls')
      .select('user_id, timestamp'),
    supabase
      .from('active_learning_requests')
      .select('user_id, status, requested_at, reviewed_at'),
  ]);

  if (usersError) throw usersError;
  if (progressError) throw progressError;
  if (fallsError) throw fallsError;
  if (requestsError) throw requestsError;

  return buildDatabaseAnalyticsDashboard(
    (users ?? []) as AnalyticsUserRow[],
    (progress ?? []) as VideoProgressRow[],
    (falls ?? []) as FallRow[],
    (requests ?? []) as AnalyticsAccessRequestRow[],
  );
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

export async function getActiveLearningAccess(participantId: string): Promise<ActiveLearningAccess> {
  return loadActiveLearningAccess(participantId);
}

export async function requestActiveLearningAccess(participantId: string): Promise<ActiveLearningAccess> {
  const now = new Date().toISOString();
  const { data: existing, error: loadError } = await supabase
    .from('active_learning_requests')
    .select('id, status')
    .eq('user_id', participantId)
    .maybeSingle();

  if (loadError) throw loadError;

  if (existing) {
    if (existing.status !== 'approved') {
      const { error } = await supabase
        .from('active_learning_requests')
        .update({ status: 'pending', requested_at: now, reviewed_at: null, reviewed_by: null, notes: null })
        .eq('id', existing.id);
      if (error) throw error;
    }
  } else {
    const { error } = await supabase
      .from('active_learning_requests')
      .insert({ id: crypto.randomUUID(), user_id: participantId, status: 'pending', requested_at: now });
    if (error) throw error;
  }

  return loadActiveLearningAccess(participantId);
}

export async function listActiveLearningRequests(): Promise<ActiveLearningAdminList> {
  const [{ data: requestRows, error: requestError }, { data: userRows, error: userError }] = await Promise.all([
    supabase
      .from('active_learning_requests')
      .select('id, user_id, status, requested_at, reviewed_at'),
    supabase
      .from('users')
      .select('user_id, active_learning_enabled'),
  ]);

  if (requestError) throw requestError;
  if (userError) throw userError;

  const usersById = new Map(
    ((userRows ?? []) as ActiveLearningUserRow[]).map((row) => [row.user_id, row])
  );
  const requestByUserId = new Map(
    ((requestRows ?? []) as ActiveLearningRequestRow[]).map((row) => [row.user_id, row])
  );
  const participantIds = new Set([...usersById.keys(), ...requestByUserId.keys()]);

  return {
    users: [...participantIds]
      .sort()
      .map((participantId) => accessFromRows(
        participantId,
        requestByUserId.get(participantId) ?? null,
        usersById.get(participantId) ?? null,
      )),
  };
}

export async function decideActiveLearningRequest(
  participantId: string,
  status: 'pending' | 'approved' | 'rejected',
): Promise<ActiveLearningAccess> {
  const now = new Date().toISOString();
  const { data: existing, error: loadError } = await supabase
    .from('active_learning_requests')
    .select('id')
    .eq('user_id', participantId)
    .maybeSingle();

  if (loadError) throw loadError;

  if (existing) {
    const { error } = await supabase
      .from('active_learning_requests')
      .update({ status, reviewed_at: now })
      .eq('id', existing.id);
    if (error) throw error;
  } else {
    const { error } = await supabase
      .from('active_learning_requests')
      .insert({
        id: crypto.randomUUID(),
        user_id: participantId,
        status,
        requested_at: now,
        reviewed_at: now,
      });
    if (error) throw error;
  }

  const { error: userError } = await supabase
    .from('users')
    .update({ active_learning_enabled: status === 'approved' })
    .eq('user_id', participantId);
  if (userError) throw userError;

  return loadActiveLearningAccess(participantId);
}

export async function setActiveLearningEnabled(participantId: string, enabled: boolean): Promise<ActiveLearningAccess> {
  const { error } = await supabase
    .from('users')
    .update({ active_learning_enabled: enabled })
    .eq('user_id', participantId);
  if (error) throw error;

  if (enabled) {
    const access = await loadActiveLearningAccess(participantId);
    if (access.request_status === 'none') {
      return decideActiveLearningRequest(participantId, 'approved');
    }
  }

  return loadActiveLearningAccess(participantId);
}

export async function getAnalyticsDashboard(): Promise<AnalyticsDashboard> {
  try {
    return await getDatabaseAnalyticsDashboard();
  } catch {
    return demoAnalyticsDashboard();
  }
}

export async function recordAnalyticsEvent(
  eventType: string,
  participantId = '',
  metadata: Record<string, unknown> = {},
): Promise<AnalyticsDashboard> {
  try {
    return await request('/analytics/events', {
      method: 'POST',
      body: JSON.stringify({ event_type: eventType, participant_id: participantId, metadata }),
    });
  } catch {
    return demoAnalyticsDashboard();
  }
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
