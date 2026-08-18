import { supabase } from './supabaseClient';

export interface FeedbackHistoryItem {
  id: string;
  session_id: string | null;
  qr_session_link_id: string | null;
  user_id: string;
  message: string;
  severity: string | null;
  pose_score: number | null;
  created_at: string;
}

export async function recordSessionFeedback(input: {
  userId: string;
  sessionId: string | null;
  qrSessionLinkId?: string | null;
  message: string;
  severity: string;
  poseScore: number | null;
}): Promise<void> {
  const { error } = await supabase.from('session_feedback').insert({
    user_id: input.userId,
    session_id: input.sessionId,
    qr_session_link_id: input.qrSessionLinkId ?? null,
    message: input.message,
    severity: input.severity,
    pose_score: input.poseScore,
  });
  if (error) throw error;
}

export async function listFeedbackHistory(userId: string, limit = 100): Promise<FeedbackHistoryItem[]> {
  const { data, error } = await supabase
    .from('session_feedback')
    .select('id, session_id, user_id, message, severity, pose_score, created_at')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
    .limit(limit);
  if (error) throw error;
  return (data ?? []) as FeedbackHistoryItem[];
}

export function subscribeToFeedbackForLink(
  qrSessionLinkId: string,
  onInsert: (item: FeedbackHistoryItem) => void,
): () => void {
  const channel = supabase
    .channel(`feedback-link-${qrSessionLinkId}`)
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'session_feedback',
        filter: `qr_session_link_id=eq.${qrSessionLinkId}`,
      },
      (payload) => onInsert(payload.new as FeedbackHistoryItem),
    )
    .subscribe();

  return () => {
    void supabase.removeChannel(channel);
  };
}