import '../styles/page-dashboard.css';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { SectionCard } from '../components/SectionCard';
import { progressStats } from '../data/mockData';
import { routes } from '../data/routes';
import { getHealth, startCamera, startSession } from '../lib/activeLearningApi';
import { useAuth } from '../context/AuthContext';
import { useActiveLearningAccess } from '../hooks/useActiveLearningAccess';

export function DashboardPage() {
  const { user } = useAuth();
  const { hasPracticeAccess } = useActiveLearningAccess();
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [backendMessage, setBackendMessage] = useState('Connecting to the Active Learning server...');
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
    return () => { cancelled = true; };
  }, []);

  async function handleStartSession() {
    if (!user) return;
    try {
      setSessionMessage('Starting session...');
      const session = await startSession(user.id);
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
        <Link className="button button-primary" to={routes.training}>Start a lesson</Link>
        {hasPracticeAccess ? (
          <Link className="button button-secondary" to={routes.practice}>Practice with camera</Link>
        ) : (
          <Link className="button button-secondary" to={routes.activeLearningAccess}>Request access</Link>
        )}
      </div>
    </section>

    {hasPracticeAccess ? (
      <SectionCard title="Active Learning connection">
        <p>Status: <strong>{backendStatus}</strong></p>
        <p>{backendMessage}</p>
        <div className="button-row">
          <button className="button button-primary" onClick={handleStartSession}>Start session</button>
        </div>
        {sessionMessage ? <p>{sessionMessage}</p> : null}
      </SectionCard>
    ) : null}

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