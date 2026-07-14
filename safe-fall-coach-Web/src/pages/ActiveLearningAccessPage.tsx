import '../styles/page-active-learning-access.css';
import { ShieldCheck } from 'lucide-react';
import { SectionCard } from '../components/SectionCard';
import { useActiveLearningAccess } from '../hooks/useActiveLearningAccess';

function formatMinutes(seconds: number) {
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function statusClass(status: string) {
  return `access-status status-${status.toLowerCase()}`;
}

export function ActiveLearningAccessPage() {
  const { access, loading, requestAccess } = useActiveLearningAccess();

  return <div className="page-stack">
    <section className="card access-hero">
      <p className="eyebrow">Active Learning Mode</p>
      <h1>Request practice access</h1>
      <p className="lead">Request access to the camera-based practice room. An administrator reviews each request.</p>
    </section>

    <SectionCard title="Your request">
      <div className="access-panel">
        {loading ? (
          <p className="helper-text">Loading your status...</p>
        ) : access ? (
          <div className="access-summary">
            <span className={statusClass(access.request_status)}>{access.request_status}</span>
            <p>Practice mode is <strong>{access.enabled ? 'enabled' : 'disabled'}</strong> for your account.</p>
            <p>Today: {access.daily_sessions_used}/{access.daily_session_limit} sessions, {formatMinutes(access.daily_seconds_used)}/{formatMinutes(access.daily_limit_seconds)} used.</p>
          </div>
        ) : null}
        {(!access || access.request_status === 'none' || access.request_status === 'rejected') ? (
          <button className="button button-primary" type="button" onClick={() => void requestAccess()}>
            <ShieldCheck size={16} /> Request Active Learning
          </button>
        ) : null}
      </div>
    </SectionCard>
  </div>;
}