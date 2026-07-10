import '../styles/page-dashboard.css';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { SectionCard } from '../components/SectionCard';
import { progressStats } from '../data/mockData';
import { routes } from '../data/routes';
import { getHealth, startCamera, startSession } from '../lib/activeLearningApi';

const PARTICIPANT_STORAGE_KEY = 'safefall.participantId';

export function DashboardPage() {
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [backendMessage, setBackendMessage] = useState('Connecting to the Active Learning server...');
  const [participantId, setParticipantId] = useState(() => localStorage.getItem(PARTICIPANT_STORAGE_KEY) || '');
  const [sessionMessage, setSessionMessage] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      try {
        const health = await getHealth();
        if (cancelled) return;

        setBackendStatus(health.status === 'ok' ? 'online' : 'offline');
        setBackendMessage(health.status === 'ok' ? 'Server connected.' : 'Server is starting up.');
      } catch (error) {
        if (!cancelled) {
          setBackendStatus('offline');
          setBackendMessage(error instanceof Error ? error.message : 'Unable to reach the server.');
        }
      }
    }

    void loadHealth();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleStartSession() {
    try {
      setSessionMessage('Starting session...');
      const normalizedParticipantId = participantId.trim();
      localStorage.setItem(PARTICIPANT_STORAGE_KEY, normalizedParticipantId);
      const session = await startSession(normalizedParticipantId);
      await startCamera(0);
      setSessionMessage(`Session started: ${session.session_id || 'active'}`);
    } catch (error) {
      setSessionMessage(error instanceof Error ? error.message : 'Unable to start a session.');
    }
  }

  return <div className="page-stack">
    <section className="card">
      <p className="eyebrow">Today</p>
      <h1>Your SafeFall Coach dashboard</h1>
      <p className="lead">One place for lessons, practice, and feedback.</p>
      <div className="button-row">
        <Link className="button button-primary" to={routes.training}>
          Start a lesson
        </Link>
        <Link className="button button-secondary" to={routes.practice}>
          Practice with camera
        </Link>
        <Link className="button button-secondary" to={routes.activeLearningAccess}>
          Request access
        </Link>
      </div>
    </section>

    <SectionCard title="Active Learning connection">
      <p>Status: <strong>{backendStatus}</strong></p>
      <p>{backendMessage}</p>
      <div className="button-row">
        <input
          value={participantId}
          onChange={(event) => setParticipantId(event.target.value)}
          placeholder="Participant ID"
          className="input"
        />
        <button className="button button-primary" onClick={handleStartSession}>
          Start session
        </button>
      </div>
      {sessionMessage ? <p>{sessionMessage}</p> : null}
    </SectionCard>

    <div className="stats-grid">
      {progressStats.map((item) => (
        <div className="stat-card card" key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
    <SectionCard title="Next step">
      <p>Try a short lesson, then open the practice room to see your movement feedback.</p>
    </SectionCard>
  </div>;
}
