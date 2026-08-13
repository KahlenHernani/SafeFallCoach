import '../styles/page-dashboard.css';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { SectionCard } from '../components/SectionCard';
import { routes } from '../data/routes';
import { getHealth } from '../lib/activeLearningApi';
import { useAuth } from '../context/AuthContext';
import { useActiveLearningAccess } from '../hooks/useActiveLearningAccess';
import { getDashboardStats, type DashboardStats } from '../lib/dashboardStatsApi';

export function DashboardPage() {
  const { user } = useAuth();
  const { hasPracticeAccess, access } = useActiveLearningAccess();
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [backendMessage, setBackendMessage] = useState('Connecting to the Active Learning server...');
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsMessage, setStatsMessage] = useState('Loading your stats...');

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

  useEffect(() => {
    let cancelled = false;
    async function loadStats() {
      if (!user) return;
      try {
        const data = await getDashboardStats(user.id);
        if (!cancelled) {
          setStats(data);
          setStatsMessage('');
        }
      } catch (error) {
        if (!cancelled) {
          setStatsMessage(error instanceof Error ? error.message : 'Unable to load your stats.');
        }
      }
    }
    void loadStats();
    return () => { cancelled = true; };
  }, [user]);

  const statCards = [
    { label: 'Sessions this week', value: stats ? String(stats.sessionsThisWeek) : '—' },
    { label: 'Practice streak', value: stats ? `${stats.practiceStreakDays} day${stats.practiceStreakDays === 1 ? '' : 's'}` : '—' },
    { label: 'Completed lessons', value: stats ? String(stats.completedLessons) : '—' },
  ];

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
        <p>Server status: <strong>{backendStatus}</strong></p>
        <p>{backendMessage}</p>
        {access ? (
          <p>
            Today: {access.daily_sessions_used}/{access.daily_session_limit} sessions,{' '}
            {Math.floor(access.daily_seconds_used / 60)}m {access.daily_seconds_used % 60}s used
            (limit {Math.floor(access.daily_limit_seconds / 60)}m).
          </p>
        ) : null}
        <div className="button-row">
          <Link className="button button-primary" to={routes.practice}>Go to Practice</Link>
        </div>
      </SectionCard>
    ) : null}

    <div className="stats-grid">
      {statCards.map((item) => (
        <div className="stat-card card" key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
    {statsMessage ? <p className="helper-text">{statsMessage}</p> : null}
    <SectionCard title="Next step">
      <p>Try a short lesson, then open the practice room to see your movement feedback.</p>
    </SectionCard>
  </div>;
}