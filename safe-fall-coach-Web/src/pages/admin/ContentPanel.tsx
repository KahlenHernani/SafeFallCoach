import { useEffect, useState } from 'react';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { SectionCard } from '../../components/SectionCard';
import {
  createTutorialVideo,
  deleteTutorialVideo,
  listAllTutorialVideos,
  updateTutorialVideo,
  uploadTutorialMedia,
  TUTORIAL_CATEGORIES,
  type TutorialCategory,
  type TutorialVideoRecord,
} from '../../lib/adminApi';

type FormState = {
  id: string | null;
  title: string;
  description: string;
  duration: string;
  category: TutorialCategory | '';
  video_order: string;
  coaching_notes: string;
  is_active: boolean;
  video_url: string;
  thumbnail_url: string;
};

const emptyForm: FormState = {
  id: null,
  title: '',
  description: '',
  duration: '',
  category: '',
  video_order: '0',
  coaching_notes: '',
  is_active: true,
  video_url: '',
  thumbnail_url: '',
};

export function ContentPanel() {
  const [videos, setVideos] = useState<TutorialVideoRecord[]>([]);
  const [message, setMessage] = useState('Loading tutorials...');
  const [form, setForm] = useState<FormState | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [thumbFile, setThumbFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      setMessage('Loading tutorials...');
      setVideos(await listAllTutorialVideos());
      setMessage('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to load tutorials.');
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function openCreate() {
    setForm({ ...emptyForm });
    setVideoFile(null);
    setThumbFile(null);
  }

  function openEdit(video: TutorialVideoRecord) {
    setForm({
      id: video.id,
      title: video.title,
      description: video.description ?? '',
      duration: video.duration ?? '',
      category: (video.category as TutorialCategory) ?? '',
      video_order: String(video.video_order ?? 0),
      coaching_notes: video.coaching_notes ?? '',
      is_active: video.is_active,
      video_url: video.video_url,
      thumbnail_url: video.thumbnail_url ?? '',
    });
    setVideoFile(null);
    setThumbFile(null);
  }

  async function handleDelete(id: string) {
    try {
      await deleteTutorialVideo(id);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to delete tutorial.');
    }
  }

  async function handleSave() {
    if (!form) return;
    setSaving(true);
    try {
      let videoUrl = form.video_url;
      let thumbUrl = form.thumbnail_url || null;

      if (videoFile) videoUrl = await uploadTutorialMedia(videoFile, 'video');
      if (thumbFile) thumbUrl = await uploadTutorialMedia(thumbFile, 'thumbnail');

      if (!videoUrl) throw new Error('A video file or URL is required.');

      const payload = {
        title: form.title.trim(),
        description: form.description.trim() || null,
        duration: form.duration.trim() || null,
        category: form.category || null,
        video_order: Number(form.video_order) || 0,
        coaching_notes: form.coaching_notes.trim() || null,
        is_active: form.is_active,
        video_url: videoUrl,
        thumbnail_url: thumbUrl,
      };

      if (form.id) {
        await updateTutorialVideo(form.id, payload);
      } else {
        await createTutorialVideo(payload);
      }

      setForm(null);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to save tutorial.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <SectionCard
      title="Tutorials & videos"
      action={
        <button className="button button-primary" type="button" onClick={openCreate}>
          <Plus size={16} /> Add tutorial
        </button>
      }
    >
      {message ? <p className="helper-text">{message}</p> : null}
      <div className="access-table-wrap">
        <table className="access-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Category</th>
              <th>Order</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {videos.length > 0 ? videos.map((v) => (
              <tr key={v.id}>
                <td>{v.title}</td>
                <td>{v.category ?? '—'}</td>
                <td>{v.video_order ?? 0}</td>
                <td>
                  <span className={v.is_active ? 'access-status status-approved' : 'access-status status-none'}>
                    {v.is_active ? 'active' : 'hidden'}
                  </span>
                </td>
                <td>
                  <div className="access-actions">
                    <button className="button button-secondary" type="button" onClick={() => openEdit(v)}>
                      <Pencil size={16} /> Edit
                    </button>
                    <button className="button button-secondary" type="button" onClick={() => void handleDelete(v.id)}>
                      <Trash2 size={16} /> Delete
                    </button>
                  </div>
                </td>
              </tr>
            )) : (
              <tr><td colSpan={5}>No tutorials yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {form ? (
        <div className="admin-modal-backdrop" role="presentation">
          <section className="admin-modal" role="dialog" aria-modal="true">
            <h2>{form.id ? 'Edit tutorial' : 'Add tutorial'}</h2>

            <label>Title
              <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </label>

            <label>Category
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as TutorialCategory })}>
                <option value="">Uncategorized</option>
                {TUTORIAL_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>

            <label>Description
              <textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </label>

            <label>Coaching notes
              <textarea rows={2} value={form.coaching_notes} onChange={(e) => setForm({ ...form, coaching_notes: e.target.value })} />
            </label>

            <div className="admin-form-row">
              <label>Duration label
                <input type="text" placeholder="e.g. 4 min" value={form.duration} onChange={(e) => setForm({ ...form, duration: e.target.value })} />
              </label>
              <label>Sort order
                <input type="number" value={form.video_order} onChange={(e) => setForm({ ...form, video_order: e.target.value })} />
              </label>
            </div>

            <label>Video file {form.video_url && !videoFile ? '(existing file kept unless replaced)' : ''}
              <input type="file" accept="video/*" onChange={(e) => setVideoFile(e.target.files?.[0] ?? null)} />
            </label>

            <label>Thumbnail {form.thumbnail_url && !thumbFile ? '(existing kept unless replaced)' : ''}
              <input type="file" accept="image/*" onChange={(e) => setThumbFile(e.target.files?.[0] ?? null)} />
            </label>

            <label className="toggle-row">
              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              Visible to participants
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