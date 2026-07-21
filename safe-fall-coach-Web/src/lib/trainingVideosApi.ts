import { supabase } from './supabaseClient';

export interface TrainingVideo {
  id: string;
  title: string;
  duration: string;
  level: string;
  category: string;
  summary: string;
  source: string;
  thumbnail?: string | null;
  databaseId?: string;
}

type TutorialVideoRow = {
  id: string;
  title: string;
  description: string | null;
  duration: string | null;
  category: string;
  video_url: string;
  thumbnail_url: string | null;
  video_order: number | null;
  is_active: boolean | null;
  coaching_notes: string | null;
};

function resolveMediaUrl(value: string | null | undefined) {
  if (!value) return null;
  if (/^(https?:)?\/\//.test(value) || value.startsWith('data:') || value.startsWith('blob:')) {
    return value;
  }

  const normalized = value.replace(/^\/+/, '');
  return supabase.storage.from('tutorial-videos').getPublicUrl(normalized).data.publicUrl;
}

function rowToTrainingVideo(row: TutorialVideoRow): TrainingVideo | null {
  const source = resolveMediaUrl(row.video_url);
  if (!source) return null;

  return {
    id: row.id,
    databaseId: row.id,
    title: row.title,
    duration: row.duration || 'Video',
    level: 'Lesson',
    category: row.category || 'Training',
    summary: row.description || row.coaching_notes || 'Watch the lesson and practice the movement at your own pace.',
    source,
    thumbnail: resolveMediaUrl(row.thumbnail_url),
  };
}

export async function listTrainingVideos(): Promise<TrainingVideo[]> {
  const { data, error } = await supabase
    .from('tutorial_videos')
    .select('id, title, description, duration, category, video_url, thumbnail_url, video_order, is_active, coaching_notes')
    .eq('is_active', true)
    .order('video_order', { ascending: true, nullsFirst: false })
    .order('title', { ascending: true });

  if (error) throw error;

  return ((data ?? []) as TutorialVideoRow[])
    .map(rowToTrainingVideo)
    .filter((video): video is TrainingVideo => video !== null);
}

export async function saveVideoProgress(
  userId: string,
  videoId: string,
  currentTime: number,
  duration: number,
  completed: boolean,
) {
  if (!userId || !videoId) return;

  const safeDuration = Number.isFinite(duration) && duration > 0 ? duration : null;
  const safePosition = Math.max(0, Number.isFinite(currentTime) ? currentTime : 0);
  const progress = safeDuration
    ? Math.min(100, Math.round((safePosition / safeDuration) * 1000) / 10)
    : completed ? 100 : null;
  const now = new Date().toISOString();

  const { data: existing, error: loadError } = await supabase
    .from('video_progress')
    .select('id')
    .eq('user_id', userId)
    .eq('video_id', videoId)
    .order('updated_at', { ascending: false })
    .limit(1)
    .maybeSingle();

  if (loadError) throw loadError;

  const values = {
      user_id: userId,
      video_id: videoId,
      last_position_seconds: safePosition,
      duration_seconds: safeDuration,
      progress_percentage: completed ? 100 : progress,
      is_completed: completed,
      last_watched_at: now,
      updated_at: now,
  };

  const { error } = existing
    ? await supabase
      .from('video_progress')
      .update(values)
      .eq('id', existing.id)
    : await supabase
      .from('video_progress')
      .insert({ id: crypto.randomUUID(), ...values });

  if (error) throw error;
}
