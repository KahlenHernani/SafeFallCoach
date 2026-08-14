import '../styles/page-feedback-history.css';
import { useEffect, useState } from 'react';
import { MessageCircle, AlertTriangle } from 'lucide-react';
import { SectionCard } from '../components/SectionCard';
import { useAuth } from '../context/AuthContext';
import { listFeedbackHistory, type FeedbackHistoryItem } from '../lib/feedbackApi';

function severityClass(severity: string | null) {
  return `severity-${(severity || 'info').toLowerCase()}`;
}

function FeedbackIcon({ severity }: { severity: string | null }) {
  const s = (severity || '').toLowerCase();
  return s === 'error' || s === 'warning'
    ? <AlertTriangle size={16} />
    : <MessageCircle size={16} />;
}

export function FeedbackHistoryPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<FeedbackHistoryItem[]>([]);
  const [message, setMessage] = useState('Loading feedback history...');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!user) return;
      try {
        const rows = await listFeedbackHistory(user.id);
        if (cancelled) return;
        setItems(rows);
        setMessage(rows.length ? '' : 'No feedback recorded yet. Start an Active Learning session to build your history.');
      } catch (error) {
        if (!cancelled) setMessage(error instanceof Error ? error.message : 'Unable to load feedback history.');
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [user]);

  return (
    <div className="page-stack">
      <section className="card">
        <p className="eyebrow">Active Learning</p>
        <h1>Feedback history</h1>
        <p className="lead">Every coaching message generated during your practice sessions, saved to your account.</p>
      </section>
      {message ? <p className="helper-text">{message}</p> : null}
      <SectionCard title="Recent feedback">
        <div className="feedback-history-list">
          {items.map((item) => (
            <article className={`feedback-card ${severityClass(item.severity)}`} key={item.id}>
              <div className="feedback-card-header">
                <span><FeedbackIcon severity={item.severity} /> {new Date(item.created_at).toLocaleString()}</span>
                {item.pose_score !== null ? <strong>{item.pose_score}/100</strong> : null}
              </div>
              <p className="feedback-message">{item.message}</p>
            </article>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}