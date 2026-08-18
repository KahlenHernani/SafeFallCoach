import { useCallback, useEffect, useRef, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { RefreshCw, UserX, MessageCircle, AlertTriangle } from 'lucide-react';
import { SectionCard } from '../../components/SectionCard';
import { useAuth } from '../../context/AuthContext';
import {
  createQrSessionLink,
  endQrSessionLink,
  getAdminParticipantInfo,
  subscribeToQrSessionLink,
  type QrSessionLink,
} from '../../lib/qrSessionApi';
import { subscribeToFeedbackForLink, type FeedbackHistoryItem } from '../../lib/feedbackApi';

interface ParticipantInfo {
  first_name: string | null;
  last_name: string | null;
  email: string;
}

export function ActiveLearningLivePanel() {
  const { user } = useAuth();
  const [link, setLink] = useState<QrSessionLink | null>(null);
  const [participant, setParticipant] = useState<ParticipantInfo | null>(null);
  const [feedback, setFeedback] = useState<FeedbackHistoryItem[]>([]);
  const [message, setMessage] = useState('');

  const linkUnsubRef = useRef<() => void>(() => {});
  const feedbackUnsubRef = useRef<() => void>(() => {});

  const cleanupSubscriptions = useCallback(() => {
    linkUnsubRef.current();
    feedbackUnsubRef.current();
    linkUnsubRef.current = () => {};
    feedbackUnsubRef.current = () => {};
  }, []);

  const startNewLink = useCallback(async () => {
    if (!user) return;
    cleanupSubscriptions();
    setParticipant(null);
    setFeedback([]);
    setMessage('Generating a new QR code...');
    try {
      const newLink = await createQrSessionLink(user.id);
      setLink(newLink);
      setMessage('Waiting for a participant to scan the QR code.');

      linkUnsubRef.current = subscribeToQrSessionLink(newLink.id, async (updated) => {
        setLink(updated);
        if (updated.status === 'connected' && updated.participant_id) {
          setMessage('Participant connected. Feedback will appear below in real time.');
          try {
            setParticipant(await getAdminParticipantInfo(updated.participant_id));
          } catch {
            setParticipant(null);
          }
          feedbackUnsubRef.current = subscribeToFeedbackForLink(updated.id, (item) => {
            setFeedback((prev) => [item, ...prev].slice(0, 50));
          });
        }
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to generate a QR code.');
    }
  }, [user, cleanupSubscriptions]);

  useEffect(() => {
    void startNewLink();
    return cleanupSubscriptions;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function handleEndSession() {
    if (!link) return;
    try {
      await endQrSessionLink(link.id);
      await startNewLink();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to end the session.');
    }
  }

  const connectUrl = link ? `${window.location.origin}/connect/${link.code}` : '';
  const isConnected = link?.status === 'connected';

  return (
    <SectionCard
      title="Active Learning — live session"
      action={
        <button className="button button-secondary" type="button" onClick={() => void startNewLink()}>
          <RefreshCw size={16} /> New QR code
        </button>
      }
    >
      <div className="access-grid">
        <div className="access-panel">
          <p className="field-label">Scan to connect</p>
          {link && !isConnected ? (
            <div style={{ background: 'white', padding: '1rem', borderRadius: 16, display: 'inline-block' }}>
              <QRCodeSVG value={connectUrl} size={220} includeMargin />
            </div>
          ) : null}
          {link ? <p className="helper-text">Code: <strong>{link.code}</strong></p> : null}
          <p className="helper-text">{message}</p>

          {isConnected ? (
            <div className="access-summary">
              <span className="access-status status-approved">connected</span>
              <p>
                {participant
                  ? `${participant.first_name ?? ''} ${participant.last_name ?? ''}`.trim() || participant.email
                  : 'Participant'}
              </p>
              <button className="button button-secondary" type="button" onClick={() => void handleEndSession()}>
                <UserX size={16} /> End session / Disconnect user
              </button>
            </div>
          ) : null}
        </div>

        <div className="access-panel">
          <p className="field-label">Live feedback</p>
          <div className="feedback-history-list">
            {feedback.length > 0 ? feedback.map((item) => {
              const sev = (item.severity || 'info').toLowerCase();
              return (
                <article className={`feedback-card severity-${sev}`} key={item.id}>
                  <div className="feedback-card-header">
                    <span>
                      {sev === 'error' || sev === 'warning' ? <AlertTriangle size={16} /> : <MessageCircle size={16} />}
                      {' '}{new Date(item.created_at).toLocaleTimeString()}
                    </span>
                    {item.pose_score !== null ? <strong>{item.pose_score}/100</strong> : null}
                  </div>
                  <p className="feedback-message">{item.message}</p>
                </article>
              );
            }) : (
              <p className="helper-text">No feedback yet.</p>
            )}
          </div>
        </div>
      </div>
    </SectionCard>
  );
}