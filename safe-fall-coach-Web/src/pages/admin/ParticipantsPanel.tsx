import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, UserCheck, UserX, CheckCircle2, XCircle } from 'lucide-react';
import { SectionCard } from '../../components/SectionCard';
import { listParticipants, setParticipantActive, type Participant } from '../../lib/adminApi';
import {
  decideActiveLearningRequest,
  listActiveLearningRequests,
  setActiveLearningEnabled,
  type ActiveLearningAccess,
} from '../../lib/activeLearningApi';
import { sendAccessGrantedEmail } from '../../lib/accessEmailApi';

type MergedParticipant = Participant & { access: ActiveLearningAccess | null };

function formatDate(value: string | null) {
  if (!value) return 'Never';
  return new Date(value).toLocaleString();
}

export function ParticipantsPanel() {
  const [participants, setParticipants] = useState<MergedParticipant[]>([]);
  const [query, setQuery] = useState('');
  const [message, setMessage] = useState('Loading participants...');

  const load = useCallback(async () => {
    try {
      setMessage('Loading participants...');
      const [rows, requests] = await Promise.all([
        listParticipants(),
        listActiveLearningRequests(),
      ]);
      const accessByParticipant = new Map(requests.users.map((a) => [a.participant_id, a]));
      const merged: MergedParticipant[] = rows.map((p) => ({
        ...p,
        access: accessByParticipant.get(p.user_id) ?? null,
      }));
      setParticipants(merged);
      setMessage('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to load participants.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return participants;
    return participants.filter((p) =>
      [p.first_name, p.last_name, p.email, p.user_id]
        .filter(Boolean)
        .some((field) => String(field).toLowerCase().includes(q)),
    );
  }, [participants, query]);

  async function handleToggleActive(p: MergedParticipant) {
    try {
      await setParticipantActive(p.user_id, !p.is_active);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to update participant.');
    }
  }

  async function handleDecision(p: MergedParticipant, status: 'approved' | 'rejected') {
    try {
      await decideActiveLearningRequest(p.user_id, status);
      let emailMessage = '';
      if (status === 'approved') {
        const emailResult = await sendAccessGrantedEmail({
          userId: p.user_id,
          email: p.email,
          firstName: p.first_name,
          lastName: p.last_name,
        });
        emailMessage = emailResult.message;
      }
      await load();
      if (emailMessage) setMessage(emailMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to update access request.');
    }
  }

  async function handleToggleEnabled(p: MergedParticipant, enabled: boolean) {
    try {
      await setActiveLearningEnabled(p.user_id, enabled);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to update access.');
    }
  }

  return (
    <SectionCard title="Registered participants">
      <div className="admin-toolbar">
        <div className="admin-search">
          <Search size={16} />
          <input
            type="text"
            placeholder="Search by name, email, or participant ID"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>
      {message ? <p className="helper-text">{message}</p> : null}
      <div className="access-table-wrap">
        <table className="access-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Participant ID</th>
              <th>Email</th>
              <th>Role</th>
              <th>Account</th>
              <th>AL request</th>
              <th>AL access</th>
              <th>Last login</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length > 0 ? filtered.map((p) => {
              const isAdmin = p.role === 'admin';
              const status = p.access?.request_status ?? 'none';
              const enabled = p.access?.enabled ?? false;
              const isApproved = status === 'approved';
              return (
                <tr key={p.user_id}>
                  <td>{p.first_name} {p.last_name}</td>
                  <td><code title={p.user_id}>{p.user_id.slice(0, 8)}…</code></td>
                  <td>{p.email}</td>
                  <td>{p.role ?? 'user'}</td>
                  <td>
                    <span className={p.is_active ? 'access-status status-approved' : 'access-status status-rejected'}>
                      {p.is_active ? 'active' : 'disabled'}
                    </span>
                  </td>
                  <td><span className={`access-status status-${status}`}>{status}</span></td>
                  <td>{enabled ? 'Enabled' : 'Disabled'}</td>
                  <td>{formatDate(p.last_sign_in_at)}</td>
                  <td>
                    {isAdmin ? (
                      <span className="helper-text">Admin account</span>
                    ) : (
                      <div className="access-actions">
                        <button className="button button-secondary" type="button" onClick={() => void handleToggleActive(p)}>
                          {p.is_active ? <><UserX size={16} /> Deactivate</> : <><UserCheck size={16} /> Activate</>}
                        </button>
                        {!isApproved ? (
                          <>
                            <button className="button button-secondary" type="button" onClick={() => void handleDecision(p, 'approved')}>
                              <CheckCircle2 size={16} /> Approve AL
                            </button>
                            <button className="button button-secondary" type="button" onClick={() => void handleDecision(p, 'rejected')}>
                              <XCircle size={16} /> Reject AL
                            </button>
                            <button className="button button-primary" type="button" onClick={() => void handleToggleEnabled(p, !enabled)}>
                              {enabled ? 'Disable AL' : 'Enable AL'}
                            </button>
                          </>
                        ) : (
                          <button className="button button-secondary" type="button" onClick={() => void handleDecision(p, 'rejected')}>
                            <XCircle size={16} /> Revoke AL access
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              );
            }) : (
              <tr><td colSpan={9}>No participants match your search.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}