import '../styles/page-practice.css';
import { useEffect, useRef, useState } from 'react';
import { SectionCard } from '../components/SectionCard';
import {
  createStateSocket,
  startSession,
  stopSession,
  type StateMessage,
} from '../lib/activeLearningApi';
import { useWebcamStream } from '../lib/useWebcamStream';

interface FeedbackItem {
  id: number;
  message: string;
  severity: string;
}

export function PracticePage() {
  const [active, setActive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [statusMessage, setStatusMessage] = useState('Press “Start session” to use this device’s camera.');
  const [state, setState] = useState<StateMessage | null>(null);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);

  const stateSocketRef = useRef<WebSocket | null>(null);
  const lastFeedbackId = useRef<number>(-1);

  // Captures the laptop webcam and streams JPEG frames to the backend /ws/ingest.
  const webcam = useWebcamStream({ fps: 12 });

  // Close the live socket if the user navigates away mid-session.
  useEffect(() => {
    return () => {
      stateSocketRef.current?.close();
      stateSocketRef.current = null;
    };
  }, []);

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
    setStarting(true);
    try {
      setStatusMessage('Requesting camera access…');
      await webcam.start();
      setStatusMessage('Starting session…');
      // No startCamera() — the server has no local camera; frames come from this
      // device over /ws/ingest. We still begin the research session for feedback.
      const session = await startSession();
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
    <div className="practice-flex">
      <section className="card camera-box" aria-label="Camera preview area">
        <div className="camera-frame">
          {/* Local webcam preview. Hidden (not unmounted) when idle so the ref stays stable. */}
          <video
            ref={webcam.videoRef}
            autoPlay
            playsInline
            muted
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'contain',
              borderRadius: 24,
              display: webcam.state.status === 'streaming' ? 'block' : 'none',
            }}
          />
          {webcam.state.status !== 'streaming' ? (
            <span>{webcam.state.error ?? 'Camera preview placeholder'}</span>
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
          <div className="feedback-box">
            {feedback.length > 0 ? (
              feedback.map((item) => (
                <p key={item.id}><strong>{item.severity}</strong> — {item.message}</p>
              ))
            ) : active ? (
              <p>Waiting for feedback… move into frame and practice your technique.</p>
            ) : (
              <>
                <p><strong>Good posture</strong> — keep shoulders relaxed.</p>
                <p><strong>Slow down</strong> — move one step at a time.</p>
                <p><strong>Safe space</strong> — clear the area before starting.</p>
              </>
            )}
          </div>
          <div className="feedback-buttons">
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
