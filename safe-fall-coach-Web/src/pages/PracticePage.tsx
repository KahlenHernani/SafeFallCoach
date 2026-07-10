import '../styles/page-practice.css';
import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, MessageCircle } from 'lucide-react';
import { SectionCard } from '../components/SectionCard';
import {
  createStateSocket,
  startSession,
  stopSession,
  type BodyLandmarkPayload,
  type StateMessage,
} from '../lib/activeLearningApi';
import { useWebcamStream } from '../lib/useWebcamStream';

interface FeedbackItem {
  id: number;
  message: string;
  severity: string;
}

type SkeletonGroup = 'left' | 'middle' | 'right';

const MIN_LANDMARK_SCORE = 0.5;
const SKELETON_COLORS: Record<SkeletonGroup, string> = {
  left: '#2563eb',
  middle: '#f97316',
  right: '#16a34a',
};
const LANDMARK_FALLBACK_COLOR = '#e11d48';
const LANDMARK_GROUPS: Record<SkeletonGroup, number[]> = {
  left: [5, 7, 9, 11, 13, 15],
  middle: [0, 1, 2, 3, 4],
  right: [6, 8, 10, 12, 14, 16],
};
const SKELETON_CONNECTIONS: Array<[number, number, SkeletonGroup]> = [
  [5, 7, 'left'],
  [7, 9, 'left'],
  [11, 13, 'left'],
  [13, 15, 'left'],
  [6, 8, 'right'],
  [8, 10, 'right'],
  [12, 14, 'right'],
  [14, 16, 'right'],
  [0, 1, 'middle'],
  [0, 2, 'middle'],
  [1, 3, 'middle'],
  [2, 4, 'middle'],
  [5, 6, 'middle'],
  [11, 12, 'middle'],
  [5, 11, 'middle'],
  [6, 12, 'middle'],
];
const PARTICIPANT_STORAGE_KEY = 'safefall.participantId';

function drawBodyLandmarks(
  canvas: HTMLCanvasElement,
  video: HTMLVideoElement | null,
  payload: BodyLandmarkPayload | undefined,
) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(rect.width * dpr));
  canvas.height = Math.max(1, Math.round(rect.height * dpr));

  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);

  if (!payload || payload.frame_width <= 0 || payload.frame_height <= 0 || payload.people.length === 0) {
    return;
  }

  const sourceWidth = payload.frame_width || video?.videoWidth || 640;
  const sourceHeight = payload.frame_height || video?.videoHeight || 480;
  const sourceAspect = sourceWidth / sourceHeight;
  const canvasAspect = rect.width / rect.height;

  let drawWidth = rect.width;
  let drawHeight = rect.height;
  let offsetX = 0;
  let offsetY = 0;

  if (canvasAspect > sourceAspect) {
    drawHeight = rect.height;
    drawWidth = drawHeight * sourceAspect;
    offsetX = (rect.width - drawWidth) / 2;
  } else {
    drawWidth = rect.width;
    drawHeight = drawWidth / sourceAspect;
    offsetY = (rect.height - drawHeight) / 2;
  }

  const mapPoint = (x: number, y: number) => ({
    x: offsetX + (x / sourceWidth) * drawWidth,
    y: offsetY + (y / sourceHeight) * drawHeight,
  });

  for (const person of payload.people) {
    const landmarksByIndex = new Map(person.landmarks.map((landmark) => [landmark.index, landmark]));

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.lineWidth = 4;
    for (const [from, to, group] of SKELETON_CONNECTIONS) {
      const a = landmarksByIndex.get(from);
      const b = landmarksByIndex.get(to);
      if (!a || !b || a.score < MIN_LANDMARK_SCORE || b.score < MIN_LANDMARK_SCORE) continue;
      const start = mapPoint(a.x, a.y);
      const end = mapPoint(b.x, b.y);
      ctx.strokeStyle = SKELETON_COLORS[group];
      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
      ctx.stroke();
    }

    const drawnLandmarks = new Set<number>();
    for (const [group, indices] of Object.entries(LANDMARK_GROUPS) as Array<[SkeletonGroup, number[]]>) {
      ctx.fillStyle = SKELETON_COLORS[group];
      for (const index of indices) {
        const landmark = landmarksByIndex.get(index);
        if (!landmark || landmark.score < MIN_LANDMARK_SCORE) continue;
        const point = mapPoint(landmark.x, landmark.y);
        ctx.beginPath();
        ctx.arc(point.x, point.y, 5, 0, Math.PI * 2);
        ctx.fill();
        drawnLandmarks.add(index);
      }
    }

    ctx.fillStyle = LANDMARK_FALLBACK_COLOR;
    for (const landmark of person.landmarks) {
      if (drawnLandmarks.has(landmark.index) || landmark.score < MIN_LANDMARK_SCORE) continue;
      const point = mapPoint(landmark.x, landmark.y);
      ctx.beginPath();
      ctx.arc(point.x, point.y, 5, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function renderFeedbackText(message: string) {
  const sections = message
    .split(/\n{2,}/)
    .map((section) => section.trim())
    .filter(Boolean);

  if (sections.length <= 1) {
    return <p className="feedback-message">{message}</p>;
  }

  return sections.map((section, index) => (
    <p className="feedback-message" key={`${index}-${section.slice(0, 20)}`}>
      {section}
    </p>
  ));
}

function FeedbackIcon({ severity }: { severity: string }) {
  const normalized = severity.toLowerCase();
  if (normalized === 'error' || normalized === 'warning') {
    return <AlertTriangle className="feedback-icon feedback-icon-alert" aria-hidden="true" size={16} />;
  }
  return <MessageCircle className="feedback-icon feedback-icon-info" aria-hidden="true" size={16} />;
}

export function PracticePage() {
  const [active, setActive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [statusMessage, setStatusMessage] = useState('Press “Start session” to use this device’s camera.');
  const [participantId, setParticipantId] = useState(() => localStorage.getItem(PARTICIPANT_STORAGE_KEY) || '');
  const [state, setState] = useState<StateMessage | null>(null);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);

  const stateSocketRef = useRef<WebSocket | null>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const lastFeedbackId = useRef<number>(-1);

  // Captures the laptop webcam and streams JPEG frames to the backend /ws/ingest.
  const webcam = useWebcamStream({ fps: 24 });

  // Close the live socket if the user navigates away mid-session.
  useEffect(() => {
    return () => {
      stateSocketRef.current?.close();
      stateSocketRef.current = null;
    };
  }, []);

  useEffect(() => {
    const canvas = overlayCanvasRef.current;
    if (!canvas) return;
    if (webcam.state.status !== 'streaming') {
      const ctx = canvas.getContext('2d');
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    drawBodyLandmarks(canvas, webcam.videoRef.current, state?.body_landmarks);
  }, [state?.body_landmarks, webcam.state.status, webcam.videoRef]);

  function openStateSocket() {
    stateSocketRef.current?.close();
    lastFeedbackId.current = -1;

    const socket = createStateSocket();
    stateSocketRef.current = socket;

    socket.onmessage = (event) => {
      let msg: StateMessage;
      try {
        msg = JSON.parse(event.data as string) as StateMessage;
      } catch {
        return;
      }
      if (msg.type === 'ping') return;
      setState(msg);

      if (
        typeof msg.feedback_id === 'number' &&
        msg.feedback_id !== lastFeedbackId.current &&
        msg.latest_feedback
      ) {
        lastFeedbackId.current = msg.feedback_id;
        setFeedback((prev) =>
          [{ id: msg.feedback_id as number, message: msg.latest_feedback as string, severity: msg.severity || 'info' }, ...prev].slice(0, 20),
        );
      }
    };

    socket.onclose = () => {
      if (stateSocketRef.current === socket) stateSocketRef.current = null;
    };
  }

  async function handleStart() {
    if (starting || active) return;
    setShowDisclaimer(true);
  }

  async function beginActiveLearningSession() {
    if (starting || active) return;
    const normalizedParticipantId = participantId.trim();
    if (!normalizedParticipantId) {
      setShowDisclaimer(false);
      setStatusMessage('Enter an approved participant ID before starting Active Learning Mode.');
      return;
    }
    setShowDisclaimer(false);
    setStarting(true);
    try {
      localStorage.setItem(PARTICIPANT_STORAGE_KEY, normalizedParticipantId);
      setStatusMessage('Requesting camera access…');
      await webcam.start();
      setStatusMessage('Starting session…');
      // No startCamera() — the server has no local camera; frames come from this
      // device over /ws/ingest. We still begin the research session for feedback.
      const session = await startSession(normalizedParticipantId);
      openStateSocket();
      setActive(true);
      setFeedback([]);
      setStatusMessage(`Session active${session.session_id ? ` (${session.session_id})` : ''}.`);
    } catch (error) {
      webcam.stop();
      setStatusMessage(error instanceof Error ? error.message : 'Unable to start the session.');
    } finally {
      setStarting(false);
    }
  }

  async function handleStop() {
    if (!active) return;
    setStatusMessage('Stopping session…');
    try {
      await stopSession();
      setStatusMessage('Session ended.');
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : 'Unable to stop the session.');
    } finally {
      stateSocketRef.current?.close();
      stateSocketRef.current = null;
      webcam.stop();
      setActive(false);
      setState(null);
    }
  }

  const ingestLabel = webcam.state.ingestConnected
    ? `sending ${webcam.state.sentFps} fps → server`
    : 'connecting to server…';

  return <div className="page-stack">
    {showDisclaimer ? (
      <div className="practice-modal-backdrop" role="presentation">
        <section
          className="practice-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="active-learning-disclaimer-title"
        >
          <div className="practice-modal-header">
            <AlertTriangle aria-hidden="true" size={20} />
            <h2 id="active-learning-disclaimer-title">Active Learning Mode Disclaimer</h2>
          </div>
          <p>
            You are about to enter Active Learning Mode, which is a supervised practice session. Please ensure that you use this feature only under appropriate supervision. Use this feature carefully and at your own risk. The University of Central Florida and the application developers are not responsible for any injuries, incidents, or outcomes that may occur while using this feature. By continuing, you acknowledge and accept these conditions.
          </p>
          <div className="practice-modal-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => setShowDisclaimer(false)}
            >
              Cancel
            </button>
            <button
              className="button button-primary"
              type="button"
              onClick={beginActiveLearningSession}
            >
              Continue
            </button>
          </div>
        </section>
      </div>
    ) : null}
    <div className="practice-flex">
      <section className="card camera-box" aria-label="Camera preview area">
        <div className="camera-frame">
          {/* Local webcam preview. Hidden (not unmounted) when idle so the ref stays stable. */}
          <video
            ref={webcam.videoRef}
            className="camera-video"
            autoPlay
            playsInline
            muted
            style={{
              display: webcam.state.status === 'streaming' ? 'block' : 'none',
            }}
          />
          <canvas
            ref={overlayCanvasRef}
            className="pose-overlay"
            aria-hidden="true"
          />
          {webcam.state.status !== 'streaming' ? (
            <span className="camera-placeholder">{webcam.state.error ?? 'Camera preview placeholder'}</span>
          ) : null}
        </div>
      </section>
      <SectionCard title="Live feedback">
        <div className="feedback-container">
          {active ? (
            <p className="helper-text" style={{ margin: 0 }}>
              {state?.duration_str ?? '00:00'} · Falls: {state?.fall_count ?? 0}
              {' · '}{ingestLabel}
            </p>
          ) : (
            <p className="helper-text" style={{ margin: 0 }}>{statusMessage}</p>
          )}
          <div className="feedback-box" aria-live="polite">
            {feedback.length > 0 ? (
              <>
                <article className={`feedback-card feedback-card-latest severity-${feedback[0].severity}`}>
                  <div className="feedback-card-header">
                    <span><FeedbackIcon severity={feedback[0].severity} /> Latest analysis</span>
                    <strong>{feedback[0].severity}</strong>
                  </div>
                  <div className="feedback-card-body">
                    {renderFeedbackText(feedback[0].message)}
                  </div>
                </article>
                {feedback.slice(1).map((item) => (
                  <article className={`feedback-card severity-${item.severity}`} key={item.id}>
                    <div className="feedback-card-header">
                      <span><FeedbackIcon severity={item.severity} /> Previous feedback</span>
                      <strong>{item.severity}</strong>
                    </div>
                    <div className="feedback-card-body">
                      {renderFeedbackText(item.message)}
                    </div>
                  </article>
                ))}
              </>
            ) : active ? (
              <article className="feedback-card feedback-card-latest">
                <div className="feedback-card-header">
                  <span><FeedbackIcon severity="info" /> Latest analysis</span>
                  <strong>waiting</strong>
                </div>
                <div className="feedback-card-body">
                  <p className="feedback-message">Waiting for feedback... move into frame and practice your technique.</p>
                </div>
              </article>
            ) : (
              <article className="feedback-card">
                <div className="feedback-card-header">
                  <span><FeedbackIcon severity="info" /> Ready check</span>
                  <strong>info</strong>
                </div>
                <div className="feedback-card-body">
                  <p className="feedback-message">Clear space around you, keep the camera pointed at your full body, and start slowly so the coach can analyze your movement.</p>
                </div>
              </article>
            )}
          </div>
          <div className="feedback-buttons">
            <input
              className="input participant-input"
              value={participantId}
              onChange={(event) => setParticipantId(event.target.value)}
              placeholder="Participant ID"
              disabled={active || starting}
            />
            <button
              className="button button-primary"
              type="button"
              onClick={handleStart}
              disabled={starting || active}
            >
              {starting ? 'Starting…' : 'Start session'}
            </button>
            <button
              className="button button-secondary"
              type="button"
              onClick={handleStop}
              disabled={!active}
            >
              Stop session
            </button>
          </div>
        </div>
      </SectionCard>
    </div>
  </div>;
}
