import '../styles/page-active-learning-access.css';
import { useEffect, useState } from 'react';
import { CheckCircle2, RefreshCw, ShieldCheck, XCircle } from 'lucide-react';
import { SectionCard } from '../components/SectionCard';
import {
  decideActiveLearningRequest,
  getActiveLearningAccess,
  listActiveLearningRequests,
  requestActiveLearningAccess,
  setActiveLearningEnabled,
  type ActiveLearningAccess,
} from '../lib/activeLearningApi';

const PARTICIPANT_STORAGE_KEY = 'safefall.participantId';

function formatMinutes(seconds: number) {
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function statusClass(status: string) {
  return `access-status status-${status.toLowerCase()}`;
}

export function ActiveLearningAccessPage() {
  const [participantId, setParticipantId] = useState(() => localStorage.getItem(PARTICIPANT_STORAGE_KEY) || '');
  const [participantStatus, setParticipantStatus] = useState<ActiveLearningAccess | null>(null);
  const [participantMessage, setParticipantMessage] = useState('');
  const [adminUsers, setAdminUsers] = useState<ActiveLearningAccess[]>([]);
  const [adminMessage, setAdminMessage] = useState('');

  async function loadParticipantStatus(id = participantId.trim()) {
    if (!id) {
      setParticipantMessage('Enter a participant ID to check request status.');
      return;
    }
    try {
      localStorage.setItem(PARTICIPANT_STORAGE_KEY, id);
      const status = await getActiveLearningAccess(id);
      setParticipantStatus(status);
      setParticipantMessage('');
    } catch (error) {
      setParticipantMessage(error instanceof Error ? error.message : 'Unable to load request status.');
    }
  }

  async function submitRequest() {
    const id = participantId.trim();
    if (!id) {
      setParticipantMessage('Enter a participant ID before requesting access.');
      return;
    }
    try {
      localStorage.setItem(PARTICIPANT_STORAGE_KEY, id);
      const status = await requestActiveLearningAccess(id);
      setParticipantStatus(status);
      setParticipantMessage('Request submitted.');
      await loadAdminUsers();
    } catch (error) {
      setParticipantMessage(error instanceof Error ? error.message : 'Unable to submit request.');
    }
  }

  async function loadAdminUsers() {
    try {
      const response = await listActiveLearningRequests();
      setAdminUsers(response.users);
      setAdminMessage('');
    } catch (error) {
      setAdminMessage(error instanceof Error ? error.message : 'Unable to load admin requests.');
    }
  }

  async function updateRequest(participant: string, status: 'approved' | 'rejected') {
    try {
      await decideActiveLearningRequest(participant, status);
      await loadAdminUsers();
      if (participant === participantId.trim()) await loadParticipantStatus(participant);
    } catch (error) {
      setAdminMessage(error instanceof Error ? error.message : 'Unable to update request.');
    }
  }

  async function updateEnabled(participant: string, enabled: boolean) {
    try {
      await setActiveLearningEnabled(participant, enabled);
      await loadAdminUsers();
      if (participant === participantId.trim()) await loadParticipantStatus(participant);
    } catch (error) {
      setAdminMessage(error instanceof Error ? error.message : 'Unable to update Active Learning status.');
    }
  }

  useEffect(() => {
    void loadAdminUsers();
    if (participantId.trim()) void loadParticipantStatus(participantId.trim());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div className="page-stack">
    <section className="card access-hero">
      <p className="eyebrow">Active Learning Mode</p>
      <h1>Access approval and daily limits</h1>
      <p className="lead">Request access, review approval status, and manage participant eligibility.</p>
    </section>

    <div className="access-grid">
      <SectionCard title="Participant request">
        <div className="access-panel">
          <label className="field-label" htmlFor="participant-id">Participant ID</label>
          <div className="access-row">
            <input
              id="participant-id"
              className="input"
              value={participantId}
              onChange={(event) => setParticipantId(event.target.value)}
              placeholder="Participant ID"
            />
            <button className="button button-secondary" type="button" onClick={() => void loadParticipantStatus()}>
              <RefreshCw size={16} /> Check
            </button>
          </div>
          <button className="button button-primary" type="button" onClick={() => void submitRequest()}>
            <ShieldCheck size={16} /> Request Active Learning
          </button>
          {participantStatus ? (
            <div className="access-summary">
              <span className={statusClass(participantStatus.request_status)}>{participantStatus.request_status}</span>
              <p>Mode is <strong>{participantStatus.enabled ? 'enabled' : 'disabled'}</strong> for this participant.</p>
              <p>Today: {participantStatus.daily_sessions_used}/{participantStatus.daily_session_limit} sessions, {formatMinutes(participantStatus.daily_seconds_used)}/{formatMinutes(participantStatus.daily_limit_seconds)} used.</p>
            </div>
          ) : null}
          {participantMessage ? <p className="helper-text">{participantMessage}</p> : null}
        </div>
      </SectionCard>

      <SectionCard title="Administrator controls">
        <div className="access-panel">
          <div className="access-row access-row-between">
            <p className="helper-text">Review requests and change Active Learning status for each participant.</p>
            <button className="button button-secondary" type="button" onClick={() => void loadAdminUsers()}>
              <RefreshCw size={16} /> Refresh
            </button>
          </div>
          <div className="access-table-wrap">
            <table className="access-table">
              <thead>
                <tr>
                  <th>Participant</th>
                  <th>Request</th>
                  <th>Status</th>
                  <th>Today</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {adminUsers.length > 0 ? adminUsers.map((user) => (
                  <tr key={user.participant_id}>
                    <td>{user.participant_id}</td>
                    <td><span className={statusClass(user.request_status)}>{user.request_status}</span></td>
                    <td>{user.enabled ? 'Enabled' : 'Disabled'}</td>
                    <td>{user.daily_sessions_used}/{user.daily_session_limit} sessions<br />{formatMinutes(user.daily_seconds_used)}</td>
                    <td>
                      <div className="access-actions">
                        <button className="button button-secondary" type="button" onClick={() => void updateRequest(user.participant_id, 'approved')}>
                          <CheckCircle2 size={16} /> Approve
                        </button>
                        <button className="button button-secondary" type="button" onClick={() => void updateRequest(user.participant_id, 'rejected')}>
                          <XCircle size={16} /> Reject
                        </button>
                        <button className="button button-primary" type="button" onClick={() => void updateEnabled(user.participant_id, !user.enabled)}>
                          {user.enabled ? 'Disable' : 'Enable'}
                        </button>
                      </div>
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={5}>No Active Learning requests yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {adminMessage ? <p className="helper-text">{adminMessage}</p> : null}
        </div>
      </SectionCard>
    </div>
  </div>;
}
