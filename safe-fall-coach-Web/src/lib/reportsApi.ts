import { supabase } from './supabaseClient';
import { listParticipants, type Participant } from './adminApi';

/** A report for month M is due at the start of month M+1, plus this many days. */
export const OVERDUE_GRACE_DAYS = 0;
/** Participants first owe a report for the month AFTER the month they enrolled. */
const FIRST_REPORT_MONTH_OFFSET = 1;

export interface MonthlyReport {
  id: string;
  user_id: string;
  report_month: string; // YYYY-MM-DD (1st of month)
  submitted_at: string;
  responses: Record<string, unknown> | null;
  notes: string | null;
}

export type MonthStatus = 'submitted' | 'overdue' | 'upcoming';
export type CompletionStatus = 'overdue' | 'up_to_date' | 'none_due';

export interface MonthEntry {
  month: string; // YYYY-MM
  status: MonthStatus;
  report: MonthlyReport | null;
  dueDate: Date;
}

export interface EnrollmentRow {
  participant: Participant;
  enrolledAt: Date | null;
  months: MonthEntry[];
  reportsDue: number;
  submitted: number;
  overdue: number;
  lastSubmittedAt: string | null;
  status: CompletionStatus;
}

export function participantName(p: Participant): string {
  return [p.first_name, p.last_name].filter(Boolean).join(' ').trim() || p.email;
}

function monthKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export function formatMonth(key: string): string {
  const [y, m] = key.slice(0, 7).split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
}

function buildMonths(enrolledAt: Date, byMonth: Map<string, MonthlyReport>, now: Date): MonthEntry[] {
  const entries: MonthEntry[] = [];
  const cursor = new Date(enrolledAt.getFullYear(), enrolledAt.getMonth() + FIRST_REPORT_MONTH_OFFSET, 1);
  const last = new Date(now.getFullYear(), now.getMonth(), 1);

  while (cursor <= last) {
    const key = monthKey(cursor);
    const report = byMonth.get(key) ?? null;
    const dueDate = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1 + OVERDUE_GRACE_DAYS);
    const status: MonthStatus = report ? 'submitted' : now >= dueDate ? 'overdue' : 'upcoming';
    entries.push({ month: key, status, report, dueDate });
    cursor.setMonth(cursor.getMonth() + 1);
  }
  return entries;
}

export function buildEnrollmentRows(
  participants: Participant[],
  reports: MonthlyReport[],
  now = new Date(),
): EnrollmentRow[] {
  const reportsByUser = new Map<string, MonthlyReport[]>();
  for (const r of reports) {
    const list = reportsByUser.get(r.user_id) ?? [];
    list.push(r);
    reportsByUser.set(r.user_id, list);
  }

  const rows = participants
    .filter((p) => p.role !== 'admin')
    .map<EnrollmentRow>((p) => {
      const userReports = reportsByUser.get(p.user_id) ?? [];
      const byMonth = new Map(userReports.map((r) => [r.report_month.slice(0, 7), r]));
      const enrolledAt = p.created_at ? new Date(p.created_at) : null;
      const months = enrolledAt ? buildMonths(enrolledAt, byMonth, now) : [];

      const reportsDue = months.filter((m) => m.status !== 'upcoming').length;
      const overdue = months.filter((m) => m.status === 'overdue').length;
      const lastSubmittedAt = userReports.reduce<string | null>(
        (latest, r) => (!latest || r.submitted_at > latest ? r.submitted_at : latest),
        null,
      );
      const status: CompletionStatus = overdue > 0 ? 'overdue' : reportsDue === 0 ? 'none_due' : 'up_to_date';

      return {
        participant: p,
        enrolledAt,
        months,
        reportsDue,
        submitted: userReports.length,
        overdue,
        lastSubmittedAt,
        status,
      };
    });

  const rank: Record<CompletionStatus, number> = { overdue: 0, up_to_date: 1, none_due: 2 };
  return rows.sort(
    (a, b) => rank[a.status] - rank[b.status] || participantName(a.participant).localeCompare(participantName(b.participant)),
  );
}

export async function loadReportingData(): Promise<{ participants: Participant[]; reports: MonthlyReport[] }> {
  const [participants, reportsResult] = await Promise.all([
    listParticipants(),
    supabase
      .from('monthly_reports')
      .select('id, user_id, report_month, submitted_at, responses, notes')
      .order('report_month', { ascending: false })
      .limit(5000),
  ]);
  if (reportsResult.error) throw reportsResult.error;
  return { participants, reports: (reportsResult.data ?? []) as MonthlyReport[] };
}

// ── CSV export ──

type Cell = string | number | boolean | null | undefined;

function csvEscape(value: Cell): string {
  if (value === null || value === undefined) return '';
  const s = String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function downloadCsv(filename: string, rows: Cell[][]): void {
  const csv = rows.map((r) => r.map(csvEscape).join(',')).join('\r\n');
  // BOM so Excel opens UTF-8 correctly.
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function enrollmentCsv(rows: EnrollmentRow[]): Cell[][] {
  return [
    [
      'Participant ID', 'First name', 'Last name', 'Email', 'Account active', 'Enrolled on',
      'Last sign-in', 'Reports due', 'Reports submitted', 'Reports overdue', 'Overdue months',
      'Last report submitted', 'Status',
    ],
    ...rows.map((r) => [
      r.participant.user_id,
      r.participant.first_name,
      r.participant.last_name,
      r.participant.email,
      r.participant.is_active ? 'Yes' : 'No',
      r.enrolledAt ? r.enrolledAt.toISOString().slice(0, 10) : '',
      r.participant.last_sign_in_at,
      r.reportsDue,
      r.submitted,
      r.overdue,
      r.months.filter((m) => m.status === 'overdue').map((m) => m.month).join('; '),
      r.lastSubmittedAt,
      r.status === 'overdue' ? 'Overdue' : r.status === 'up_to_date' ? 'Up to date' : 'No report due yet',
    ]),
  ];
}

export function monthlyStatusCsv(rows: EnrollmentRow[]): Cell[][] {
  const out: Cell[][] = [['Participant ID', 'Name', 'Email', 'Month', 'Status', 'Due date', 'Submitted at']];
  for (const r of rows) {
    for (const m of r.months) {
      out.push([
        r.participant.user_id,
        participantName(r.participant),
        r.participant.email,
        m.month,
        m.status,
        m.dueDate.toISOString().slice(0, 10),
        m.report?.submitted_at ?? '',
      ]);
    }
  }
  return out;
}

export function detailsCsv(reports: MonthlyReport[], participantsById: Map<string, Participant>): Cell[][] {
  const keys = new Set<string>();
  for (const r of reports) Object.keys(r.responses ?? {}).forEach((k) => keys.add(k));
  const responseKeys = [...keys].sort();

  return [
    ['Participant ID', 'Name', 'Email', 'Report month', 'Submitted at', 'Notes', ...responseKeys],
    ...reports.map((r) => {
      const p = participantsById.get(r.user_id);
      return [
        r.user_id,
        p ? participantName(p) : '',
        p?.email ?? '',
        r.report_month.slice(0, 7),
        r.submitted_at,
        r.notes,
        ...responseKeys.map((k) => formatValue(r.responses?.[k])),
      ];
    }),
  ];
}