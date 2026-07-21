import { useEffect, useState } from 'react';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { SectionCard } from '../../components/SectionCard';
import {
  createNotificationTemplate,
  deleteNotificationTemplate,
  listNotificationTemplates,
  setNotificationTemplateEnabled,
  updateNotificationTemplate,
  type NotificationFrequency,
  type NotificationTemplate,
} from '../../lib/adminApi';

type FormState = {
  id: string | null;
  title: string;
  message: string;
  frequency: NotificationFrequency;
  send_time: string;
  day_of_week: string;
  day_of_month: string;
  start_date: string;
  enabled: boolean;
};

const emptyForm: FormState = {
  id: null,
  title: '',
  message: '',
  frequency: 'daily',
  send_time: '09:00',
  day_of_week: '1',
  day_of_month: '1',
  start_date: '',
  enabled: true,
};

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function scheduleSummary(t: NotificationTemplate) {
  if (t.frequency === 'once') return t.start_date ? `Once on ${t.start_date} at ${t.send_time}` : `Once at ${t.send_time}`;
  if (t.frequency === 'daily') return `Daily at ${t.send_time}`;
  if (t.frequency === 'weekly') return `Weekly on ${WEEKDAYS[t.day_of_week ?? 0]} at ${t.send_time}`;
  return `Monthly on day ${t.day_of_month ?? 1} at ${t.send_time}`;
}

export function NotificationsPanel() {
  const [templates, setTemplates] = useState<NotificationTemplate[]>([]);
  const [message, setMessage] = useState('Loading reminders...');
  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      setMessage('Loading reminders...');
      setTemplates(await listNotificationTemplates());
      setMessage('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to load reminders.');
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function openEdit(t: NotificationTemplate) {
    setForm({
      id: t.id,
      title: t.title,
      message: t.message,
      frequency: t.frequency,
      send_time: t.send_time.slice(0, 5),
      day_of_week: String(t.day_of_week ?? 1),
      day_of_month: String(t.day_of_month ?? 1),
      start_date: t.start_date ?? '',
      enabled: t.enabled,
    });
  }

  async function handleToggle(t: NotificationTemplate) {
    try {
      await setNotificationTemplateEnabled(t.id, !t.enabled);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to update reminder.');
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteNotificationTemplate(id);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to delete reminder.');
    }
  }

  async function handleSave() {
    if (!form) return;
    setSaving(true);
    try {
      const payload = {
        title: form.title.trim(),
        message: form.message.trim(),
        frequency: form.frequency,
        send_time: form.send_time,
        day_of_week: form.frequency === 'weekly' ? Number(form.day_of_week) : null,
        day_of_month: form.frequency === 'monthly' ? Number(form.day_of_month) : null,
        start_date: form.frequency === 'once' ? (form.start_date || null) : null,
        enabled: form.enabled,
      };

      if (form.id) {
        await updateNotificationTemplate(form.id, payload);
      } else {
        await createNotificationTemplate(payload);
      }

      setForm(null);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to save reminder.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <SectionCard
      title="Reminder notifications"
      action={
        <button className="button button-primary" type="button" onClick={() => setForm({ ...emptyForm })}>
          <Plus size={16} /> New reminder
        </button>
      }
    >
      <p className="helper-text">
        This manages reminder schedules. Actual delivery still requires a scheduled job (e.g. a Supabase Edge
        Function on pg_cron) to read enabled templates and send them — ask if you'd like that wired up next.
      </p>
      {message ? <p className="helper-text">{message}</p> : null}
      <div className="access-table-wrap">
        <table className="access-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Schedule</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {templates.length > 0 ? templates.map((t) => (
              <tr key={t.id}>
                <td>{t.title}</td>
                <td>{scheduleSummary(t)}</td>
                <td>
                  <span className={t.enabled ? 'access-status status-approved' : 'access-status status-none'}>
                    {t.enabled ? 'enabled' : 'disabled'}
                  </span>
                </td>
                <td>
                  <div className="access-actions">
                    <button className="button button-secondary" type="button" onClick={() => openEdit(t)}>
                      <Pencil size={16} /> Edit
                    </button>
                    <button className="button button-secondary" type="button" onClick={() => void handleToggle(t)}>
                      {t.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button className="button button-secondary" type="button" onClick={() => void handleDelete(t.id)}>
                      <Trash2 size={16} /> Delete
                    </button>
                  </div>
                </td>
              </tr>
            )) : (
              <tr><td colSpan={4}>No reminders yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {form ? (
        <div className="admin-modal-backdrop" role="presentation">
          <section className="admin-modal" role="dialog" aria-modal="true">
            <h2>{form.id ? 'Edit reminder' : 'New reminder'}</h2>

            <label>Title
              <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </label>

            <label>Message
              <textarea rows={3} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} />
            </label>

            <label>Frequency
              <select
                value={form.frequency}
                onChange={(e) => setForm({ ...form, frequency: e.target.value as NotificationFrequency })}
              >
                <option value="once">Once</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </label>

            <div className="admin-form-row">
              <label>Send time
                <input type="time" value={form.send_time} onChange={(e) => setForm({ ...form, send_time: e.target.value })} />
              </label>

              {form.frequency === 'weekly' ? (
                <label>Day of week
                  <select value={form.day_of_week} onChange={(e) => setForm({ ...form, day_of_week: e.target.value })}>
                    {WEEKDAYS.map((day, index) => <option key={day} value={index}>{day}</option>)}
                  </select>
                </label>
              ) : null}

              {form.frequency === 'monthly' ? (
                <label>Day of month
                  <input
                    type="number" min={1} max={31}
                    value={form.day_of_month}
                    onChange={(e) => setForm({ ...form, day_of_month: e.target.value })}
                  />
                </label>
              ) : null}

              {form.frequency === 'once' ? (
                <label>Date
                  <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
                </label>
              ) : null}
            </div>

            <label className="toggle-row">
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              Enabled
            </label>

            <div className="practice-modal-actions">
              <button className="button button-secondary" type="button" onClick={() => setForm(null)} disabled={saving}>
                Cancel
              </button>
              <button className="button button-primary" type="button" onClick={() => void handleSave()} disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </SectionCard>
  );
}