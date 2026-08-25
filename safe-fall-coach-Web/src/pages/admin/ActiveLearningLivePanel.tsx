import { useCallback, useEffect, useRef, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { RefreshCw, UserX, MessageCircle, AlertTriangle } from 'lucide-react';
import { SectionCard } from '../../components/SectionCard';
import { useAuth } from '../../context/AuthContext';
import {
  createQrSessionLink,
  endQrSessionLink,
  getQrSessionLink,
  getAdminParticipantInfo,
  subscribeToQrSessionLink,
  type QrSessionLink,
} from '../../lib/qrSessionApi';
import { listFeedbackForLink, subscribeToFeedbackForLink, type FeedbackHistoryItem } from '../../lib/feedbackApi';

interface ParticipantInfo {
  first_name: string | null;
  last_name: string | null;
  email: string;
}

const LIVE_SESSION_STORAGE_PREFIX = 'safeFallCoach.admin.liveSessionLink.';
const FEEDBACK_POLL_INTERVAL_MS = 3000;
const createLinkRequests = new Map<string, Promise<QrSessionLink>>();

function getStoredLiveSessionLinkId(adminId: string): string | null {
  try {
    return window.sessionStorage.getItem(`${LIVE_SESSION_STORAGE_PREFIX}${adminId}`);
  } catch {
    return null;
  }
}

function setStoredLiveSessionLinkId(adminId: string, linkId: string): void {
  try {
    window.sessionStorage.setItem(`${LIVE_SESSION_STORAGE_PREFIX}${adminId}`, linkId);
  } catch {
    // The active component state still keeps the session usable for this mount.
  }
}

function clearStoredLiveSessionLinkId(adminId: string): void {
  try {
    window.sessionStorage.removeItem(`${LIVE_SESSION_STORAGE_PREFIX}${adminId}`);
  } catch {
    // Ignore storage failures.
  }
}

async function createLiveSessionLink(adminId: string): Promise<QrSessionLink> {
  const existingRequest = createLinkRequests.get(adminId);
  if (existingRequest) return existingRequest;

  const request = createQrSessionLink(adminId).finally(() => {
    createLinkRequests.delete(adminId);
  });
  createLinkRequests.set(adminId, request);
  return request;
}

export function ActiveLearningLivePanel() {
  const { user } = useAuth();
  const [link, setLink] = useState<QrSessionLink | null>(null);
  const [participant, setParticipant] = useState<ParticipantInfo | null>(null);
  const [feedback, setFeedback] = useState<FeedbackHistoryItem[]>([]);
  const [message, setMessage] = useState('');

  const linkUnsubRef = useRef<() => void>(() => {});
  const feedbackUnsubRef = useRef<() => void>(() => {});
  const feedbackPollRef = useRef<number | null>(null);
  const feedbackLinkIdRef = useRef<string | null>(null);

  const mergeFeedback = useCallback((items: FeedbackHistoryItem[]) => {
    setFeedback((prev) => {
      const byId = new Map<string, FeedbackHistoryItem>();
      for (const item of [...items, ...prev]) {
        byId.set(item.id, item);
      }
      return Array.from(byId.values())
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 50);
    });
  }, []);

  const cleanupSubscriptions = useCallback(() => {
    linkUnsubRef.current();
    feedbackUnsubRef.current();
    if (feedbackPollRef.current !== null) {
      window.clearInterval(feedbackPollRef.current);
      feedbackPollRef.current = null;
    }
    linkUnsubRef.current = () => {};
    feedbackUnsubRef.current = () => {};
    feedbackLinkIdRef.current = null;
  }, []);

  const subscribeToFeedback = useCallback((linkId: string) => {
    if (feedbackLinkIdRef.current === linkId) return;
    feedbackUnsubRef.current();
    if (feedbackPollRef.current !== null) {
      window.clearInterval(feedbackPollRef.current);
      feedbackPollRef.current = null;
    }

    const refreshFeedback = async () => {
      try {
        mergeFeedback(await listFeedbackForLink(linkId));
      } catch {
        // Keep the live subscription active; permission/schema problems surface as an empty admin view.
      }
    };

    void refreshFeedback();
    feedbackPollRef.current = window.setInterval(() => {
      void refreshFeedback();
    }, FEEDBACK_POLL_INTERVAL_MS);

    feedbackUnsubRef.current = subscribeToFeedbackForLink(linkId, (item) => {
      mergeFeedback([item]);
    });
    feedbackLinkIdRef.current = linkId;
  }, [mergeFeedback]);

  const activateLink = useCallback((activeLink: QrSessionLink, wasRestored = false) => {
    setLink(activeLink);

    if (activeLink.status === 'ended') {
      if (user) clearStoredLiveSessionLinkId(user.id);
      setParticipant(null);
      setFeedback([]);
      setMessage('This QR session has ended. Generate a new QR code to continue.');
      return;
    }

    setStoredLiveSessionLinkId(activeLink.admin_id, activeLink.id);

    linkUnsubRef.current = subscribeToQrSessionLink(activeLink.id, async (updated) => {
      setLink(updated);
      if (updated.status === 'ended') {
        clearStoredLiveSessionLinkId(updated.admin_id);
        feedbackUnsubRef.current();
        feedbackUnsubRef.current = () => {};
        if (feedbackPollRef.current !== null) {
          window.clearInterval(feedbackPollRef.current);
          feedbackPollRef.current = null;
        }
        feedbackLinkIdRef.current = null;
        setMessage('This QR session has ended. Generate a new QR code to continue.');
        return;
      }

      setStoredLiveSessionLinkId(updated.admin_id, updated.id);
      if (updated.status === 'connected' && updated.participant_id) {
        setMessage('Participant connected. Feedback will appear below in real time.');
        try {
          setParticipant(await getAdminParticipantInfo(updated.participant_id));
        } catch {
          setParticipant(null);
        }
        subscribeToFeedback(updated.id);
      }
    });

    if (activeLink.status === 'connected' && activeLink.participant_id) {
      setMessage('Participant connected. Feedback will appear below in real time.');
      void getAdminParticipantInfo(activeLink.participant_id)
        .then(setParticipant)
        .catch(() => setParticipant(null));
      subscribeToFeedback(activeLink.id);
      return;
    }

    setMessage(wasRestored ? 'Waiting for a participant to scan the existing QR code.' : 'Waiting for a participant to scan the QR code.');
  }, [subscribeToFeedback, user]);

  const startNewLink = useCallback(async () => {
    if (!user) return;
    cleanupSubscriptions();
    setParticipant(null);
    setFeedback([]);
    setMessage('Generating a new QR code...');
    try {
      const newLink = await createLiveSessionLink(user.id);
      activateLink(newLink);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to generate a QR code.');
    }
  }, [activateLink, user, cleanupSubscriptions]);

  useEffect(() => {
    let isCurrent = true;

    async function initializeLink() {
      if (!user) return;

      cleanupSubscriptions();
      setMessage('Loading QR session...');

      const storedLinkId = getStoredLiveSessionLinkId(user.id);
      if (storedLinkId) {
        try {
          const storedLink = await getQrSessionLink(storedLinkId);
          if (!isCurrent) return;
          if (storedLink && storedLink.admin_id === user.id && storedLink.status !== 'ended') {
            activateLink(storedLink, true);
            return;
          }
        } catch {
          if (!isCurrent) return;
          // Fall through and create a fresh link if the stored one cannot be loaded.
        }
        clearStoredLiveSessionLinkId(user.id);
      }

      setParticipant(null);
      setFeedback([]);
      setMessage('Generating a new QR code...');
      try {
        const newLink = await createLiveSessionLink(user.id);
        if (!isCurrent) return;
        activateLink(newLink);
      } catch (error) {
        if (!isCurrent) return;
        setMessage(error instanceof Error ? error.message : 'Unable to generate a QR code.');
      }
    }

    void initializeLink();
    return () => {
      isCurrent = false;
      cleanupSubscriptions();
    };
  }, [activateLink, cleanupSubscriptions, user]);

  async function handleEndSession() {
    if (!link) return;
    try {
      await endQrSessionLink(link.id);
      if (user) clearStoredLiveSessionLinkId(user.id);
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
