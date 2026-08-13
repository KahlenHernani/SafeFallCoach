import { supabase } from './supabaseClient';

/**
 * Records the start of an Active Learning practice session in
 * active_learning_sessions. Returns the new row's id so the caller can
 * close it out later with recordSessionEnd().
 */
export async function recordSessionStart(userId: string): Promise<string> {
  const { data, error } = await supabase
    .from('active_learning_sessions')
    .insert({ user_id: userId })
    .select('id')
    .single();
  if (error) throw error;
  return data.id as string;
}

/** Closes out a previously started session with its final duration. */
export async function recordSessionEnd(sessionId: string, durationSeconds: number): Promise<void> {
  const { error } = await supabase
    .from('active_learning_sessions')
    .update({
      ended_at: new Date().toISOString(),
      duration_seconds: Math.max(0, Math.round(durationSeconds)),
    })
    .eq('id', sessionId);
  if (error) throw error;
}

export interface DailyActiveLearningUsage {
  sessionsUsed: number;
  secondsUsed: number;
}

/**
 * Computes today's Active Learning usage (session count + seconds) directly
 * from active_learning_sessions — real usage, not a placeholder. Sessions
 * still in progress (no ended_at yet) count elapsed time so far, so an
 * open session correctly eats into the daily budget in real time.
 */
export async function getDailyActiveLearningUsage(userId: string): Promise<DailyActiveLearningUsage> {
  const startOfDay = new Date();
  startOfDay.setHours(0, 0, 0, 0);

  const { data, error } = await supabase
    .from('active_learning_sessions')
    .select('duration_seconds, started_at, ended_at')
    .eq('user_id', userId)
    .gte('started_at', startOfDay.toISOString());

  if (error) throw error;

  const rows = data ?? [];
  const now = Date.now();
  let secondsUsed = 0;

  for (const row of rows) {
    if (row.ended_at) {
      secondsUsed += row.duration_seconds ?? 0;
    } else if (row.started_at) {
      secondsUsed += Math.max(0, Math.floor((now - new Date(row.started_at).getTime()) / 1000));
    }
  }

  return { sessionsUsed: rows.length, secondsUsed };
}