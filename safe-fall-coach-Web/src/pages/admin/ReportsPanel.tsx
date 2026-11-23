import '../../styles/page-admin-reports.css';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Download, Eye, RefreshCw, Search } from 'lucide-react';
import { SectionCard } from '../../components/SectionCard';
import type { Participant } from '../../lib/adminApi';
import {
  buildEnrollmentRows,
  detailsCsv,
  downloadCsv,
  enrollmentCsv,
  formatMonth,
  formatValue,
  loadReportingData,
  monthlyStatusCsv,
  participantName,
  type CompletionStatus,
  type MonthlyReport,
} from '../../lib/reportsApi';

type View = 'completion' | 'details';

const STATUS_LABEL: Record<CompletionStatus, string> = {
  overdue: 'Overdue',
  up_to_date: 'Up to date',
  none_due: 'None due yet',
};
const STATUS_CLASS: Record<CompletionStatus, string> = {
  overdue: 'access-status status-rejected',
  up_to_date: 'access-status status-approved',
  none_due: 'access-status status-none',
};

function formatDate(value: string | Date | null) {
  if (!value) return '—';
  return new Date(value).toLocaleDateString();
}

function stamp() {
  return new Date().toISOString().slice(0, 10);
}

export function ReportsPanel() {
  const [view, setView] = useState<View>('completion');
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [reports, setReports] = useState<MonthlyReport[]>([]);
  const [message, setMessage] = useState('Loading reports...');
  const [query, setQuery] = useState('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [monthFilter, setMonthFilter] = useState('');
  const [selected, setSelected] = useState<MonthlyReport | null>(null);

  const load = useCallback(async () => {
    try {
      setMessage('Loading reports...');
      const data = await loadReportingData();
      setParticipants(data.participants);
      setReports(data.reports);
      setMessage('');
    } catch (error) {
      setMessage(
        error instanceof Error
          ? `${error.message} (has migration 013_monthly_reports.sql been run?)`
          : 'Unable to load reports.',
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const participantsById = useMemo(() => new Map(participants.map((p) => [p.user_id, p])), [participants]);
  const rows = useMemo(() => buildEnrollmentRows(participants, reports), [participants, reports]);

  const matchesQuery = useCallback(
    (p: Participant | undefined) => {
      const q = query.trim().toLowerCase();
      if (!q) return true;
      if (!p) return false;
      return [p.first_name, p.last_name, p.email, p.user_id]
        .filter(Boolean)
        .some((f) => String(f).toLowerCase().includes(q));
    },
    [query],
  );

  const filteredRows = useMemo(
    () => rows.filter((r) => matchesQuery(r.participant) && (!overdueOnly || r.status === 'overdue')),
    [rows, matchesQuery, overdueOnly],
  );

  const filteredReports = useMemo(
    () =>
      reports.filter(
        (r) =>
          matchesQuery(participantsById.get(r.user_id)) &&
          (!monthFilter || r.report_month.slice(0, 7) === monthFilter),
      ),
    [reports, participantsById, matchesQuery, monthFilter],
  );

  const monthOptions = useMemo(
    () => [...new Set(reports.map((r) => r.report_month.slice(0, 7)))].sort().reverse(),
    [reports],
  );

  const totals = useMemo(
    () => ({
      enrolled: rows.length,
      active: rows.filter((r) => r.participant.is_active).length,
      upToDate: rows.filter((r) => r.status === 'up_to_date').length,
      overdueParticipants: rows.filter((r) => r.status === 'overdue').length,
      overdueReports: rows.reduce((sum, r) => sum + r.overdue, 0),
    }),
    [rows],
  );

  return (
    <SectionCard
      title="Reports"
      action={
        <button className="button button-secondary" type="button" onClick={() => void load()}>
          <RefreshCw size={16} /> Refresh
        </button>
      }
    >
      <div className="report-subtabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={view === 'completion'}
          className={view === 'completion' ? 'admin-tab active' : 'admin-tab'}
          onClick={() => setView('completion')}
        >
          Enrollment &amp; completion
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'details'}
          className={view === 'details' ? 'admin-tab active' : 'admin-tab'}
          onClick={() => setView('details')}
        >
          Submitted details
        </button>
      </div>

      {message ? <p className="helper-text">{message}</p> : null}

      <div className="report-toolbar">
        <div className="admin-search">
          <Search size={16} />
          <input
            type="text"
            placeholder="Search by name, email, or participant ID"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {view === 'completion' ? (
          <>
            <label className="report-check">
              <input type="checkbox" checked={overdueOnly} onChange={(e) => setOverdueOnly(e.target.checked)} />
              Overdue only
            </label>
            <button
              className="button button-primary"
              type="button"
              onClick={() => downloadCsv(`enrollment-report-${stamp()}.csv`, enrollmentCsv(filteredRows))}
            >
              <Download size={16} /> Download summary
            </button>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => downloadCsv(`monthly-status-${stamp()}.csv`, monthlyStatusCsv(filteredRows))}
            >
              <Download size={16} /> Download monthly status
            </button>
          </>
        ) : (
          <>
            <select value={monthFilter} onChange={(e) => setMonthFilter(e.target.value)} aria-label="Report month">
              <option value="">All months</option>
              {monthOptions.map((m) => (
                <option key={m} value={m}>{formatMonth(m)}</option>
              ))}
            </select>
            <button
              className="button button-primary"
              type="button"
              onClick={() => downloadCsv(`submitted-reports-${stamp()}.csv`, detailsCsv(filteredReports, participantsById))}
            >
              <Download size={16} /> Download details
            </button>
          </>
        )}
      </div>

      {view === 'completion' ? (
        <>
          <div className="report-summary">
            <div><span>Enrolled</span><strong>{totals.enrolled}</strong></div>
            <div><span>Active accounts</span><strong>{totals.active}</strong></div>
            <div><span>Up to date</span><strong>{totals.upToDate}</strong></div>
            <div><span>Participants overdue</span><strong>{totals.overdueParticipants}</strong></div>
            <div><span>Overdue reports</span><strong>{totals.overdueReports}</strong></div>
          </div>

          <div className="access-table-wrap">
            <table className="access-table">
              <thead>
                <tr>
                  <th>Participant</th>
                  <th>Email</th>
                  <th>Enrolled</th>
                  <th>Account</th>
                  <th>Submitted / due</th>
                  <th>Overdue</th>
                  <th>Last report</th>
                  <th>Recent months</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.length > 0 ? (
                  filteredRows.map((r) => (
                    <tr key={r.participant.user_id}>
                      <td>{participantName(r.participant)}</td>
                      <td>{r.participant.email}</td>
                      <td>{formatDate(r.enrolledAt)}</td>
                      <td>
                        <span className={r.participant.is_active ? 'access-status status-approved' : 'access-status status-rejected'}>
                          {r.participant.is_active ? 'active' : 'disabled'}
                        </span>
                      </td>
                      <td>{r.submitted} / {r.reportsDue}</td>
                      <td>{r.overdue}</td>
                      <td>{formatDate(r.lastSubmittedAt)}</td>
                      <td>
                        <div className="month-chips">
                          {r.months.length === 0 ? '—' : r.months.slice(-6).map((m) => (
                            <span key={m.month} className={`month-chip ${m.status}`} title={`${formatMonth(m.month)}: ${m.status}`}>
                              {formatMonth(m.month)}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td><span className={STATUS_CLASS[r.status]}>{STATUS_LABEL[r.status]}</span></td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan={9}>No participants match.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="access-table-wrap">
          <table className="access-table">
            <thead>
              <tr>
                <th>Participant</th>
                <th>Email</th>
                <th>Report month</th>
                <th>Submitted</th>
                <th>Summary</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredReports.length > 0 ? (
                filteredReports.map((r) => {
                  const p = participantsById.get(r.user_id);
                  const count = Object.keys(r.responses ?? {}).length;
                  return (
                    <tr key={r.id}>
                      <td>{p ? participantName(p) : r.user_id.slice(0, 8) + '…'}</td>
                      <td>{p?.email ?? '—'}</td>
                      <td>{formatMonth(r.report_month)}</td>
                      <td>{new Date(r.submitted_at).toLocaleString()}</td>
                      <td>{count} answer{count === 1 ? '' : 's'}{r.notes ? ' + notes' : ''}</td>
                      <td>
                        <button className="button button-secondary" type="button" onClick={() => setSelected(r)}>
                          <Eye size={16} /> View
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr><td colSpan={6}>No submitted reports match.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {selected ? (
        <div className="admin-modal-backdrop" role="presentation">
          <section className="admin-modal" role="dialog" aria-modal="true">
            <h2>
              {participantsById.get(selected.user_id)
                ? participantName(participantsById.get(selected.user_id)!)
                : 'Participant'}{' '}
              — {formatMonth(selected.report_month)}
            </h2>
            <p className="helper-text">Submitted {new Date(selected.submitted_at).toLocaleString()}</p>
            <dl className="report-detail-list">
              {Object.entries(selected.responses ?? {}).map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{formatValue(value) || '—'}</dd>
                </div>
              ))}
              {selected.notes ? (
                <div><dt>Notes</dt><dd>{selected.notes}</dd></div>
              ) : null}
              {Object.keys(selected.responses ?? {}).length === 0 && !selected.notes ? (
                <div><dd>No details were submitted with this report.</dd></div>
              ) : null}
            </dl>
            <div className="report-modal-actions">
              <button
                className="button button-secondary"
                type="button"
                onClick={() =>
                  downloadCsv(
                    `report-${selected.report_month.slice(0, 7)}-${selected.user_id.slice(0, 8)}.csv`,
                    detailsCsv([selected], participantsById),
                  )
                }
              >
                <Download size={16} /> Download
              </button>
              <button className="button button-primary" type="button" onClick={() => setSelected(null)}>
                Close
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </SectionCard>
  );
}
