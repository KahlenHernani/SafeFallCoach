import { supabase } from './supabaseClient';

// ── Participants ──

export interface Participant {
  user_id: string;
  first_name: string | null;
  last_name: string | null;
  email: string;
  role: string | null;
  is_active: boolean;
  created_at: string | null;
  last_sign_in_at: string | null;
}

export async function listParticipants(): Promise<Participant[]> {
  const { data, error } = await supabase.rpc('admin_list_participants');
  if (error) throw error;
  return (data ?? []) as Participant[];
}

export async function setParticipantActive(userId: string, active: boolean): Promise<void> {
  const { error } = await supabase.rpc('admin_set_user_active', {
    target_user_id: userId,
    new_active: active,
  });
  if (error) throw error;
}

// ── Content / tutorials ──

export const TUTORIAL_CATEGORIES = [
  'Forward Fall',
  'Backward Fall',
  'Side Fall',
  'Recovery/Getting Up',
] as const;
export type TutorialCategory = (typeof TUTORIAL_CATEGORIES)[number];

export interface TutorialVideoRecord {
  id: string;
  title: string;
  description: string | null;
  duration: string | null;
  category: TutorialCategory | null;
  video_url: string;
  thumbnail_url: string | null;
  video_order: number | null;
  is_active: boolean;
  coaching_notes: string | null;
  created_at: string;
  updated_at: string;
}

export type TutorialVideoInput = {
  title: string;
  description?: string | null;
  duration?: string | null;
  category?: TutorialCategory | '' | null;
  video_order?: number;
  is_active?: boolean;
  coaching_notes?: string | null;
  video_url: string;
  thumbnail_url?: string | null;
};

export async function listAllTutorialVideos(): Promise<TutorialVideoRecord[]> {
  const { data, error } = await supabase
    .from('tutorial_videos')
    .select('*')
    .order('video_order', { ascending: true, nullsFirst: false })
    .order('title', { ascending: true });
  if (error) throw error;
  return (data ?? []) as TutorialVideoRecord[];
}

export async function createTutorialVideo(input: TutorialVideoInput) {
  const { error } = await supabase.from('tutorial_videos').insert({
    ...input,
    category: input.category || null,
  });
  if (error) throw error;
}

export async function updateTutorialVideo(id: string, input: Partial<TutorialVideoInput>) {
  const { error } = await supabase
    .from('tutorial_videos')
    .update({ ...input, category: input.category || null })
    .eq('id', id);
  if (error) throw error;
}

export async function deleteTutorialVideo(id: string) {
  const { error } = await supabase.from('tutorial_videos').delete().eq('id', id);
  if (error) throw error;
}

export async function uploadTutorialMedia(file: File, kind: 'video' | 'thumbnail'): Promise<string> {
  const ext = file.name.split('.').pop() || (kind === 'video' ? 'mp4' : 'jpg');
  const path = `${kind}s/${crypto.randomUUID()}.${ext}`;
  const { error } = await supabase.storage.from('tutorial-videos').upload(path, file, {
    upsert: true,
    contentType: file.type || undefined,
  });
  if (error) throw error;
  return path;
}

// ── Notification templates ──

export type NotificationFrequency = 'once' | 'daily' | 'weekly' | 'monthly';

export interface NotificationTemplate {
  id: string;
  title: string;
  message: string;
  frequency: NotificationFrequency;
  send_time: string;
  day_of_week: number | null;
  day_of_month: number | null;
  start_date: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export type NotificationTemplateInput = {
  title: string;
  message: string;
  frequency: NotificationFrequency;
  send_time: string;
  day_of_week?: number | null;
  day_of_month?: number | null;
  start_date?: string | null;
  enabled?: boolean;
};

export async function listNotificationTemplates(): Promise<NotificationTemplate[]> {
  const { data, error } = await supabase
    .from('notification_templates')
    .select('*')
    .order('created_at', { ascending: false });
  if (error) throw error;
  return (data ?? []) as NotificationTemplate[];
}

export async function createNotificationTemplate(input: NotificationTemplateInput) {
  const { error } = await supabase.from('notification_templates').insert(input);
  if (error) throw error;
}

export async function updateNotificationTemplate(id: string, input: Partial<NotificationTemplateInput>) {
  const { error } = await supabase.from('notification_templates').update(input).eq('id', id);
  if (error) throw error;
}

export async function deleteNotificationTemplate(id: string) {
  const { error } = await supabase.from('notification_templates').delete().eq('id', id);
  if (error) throw error;
}

export async function setNotificationTemplateEnabled(id: string, enabled: boolean) {
  const { error } = await supabase.from('notification_templates').update({ enabled }).eq('id', id);
  if (error) throw error;
}