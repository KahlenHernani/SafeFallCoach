import { supabase } from './supabaseClient';

export interface DashboardStats {
  sessionsThisWeek: number;
  practiceStreakDays: number;
  completedLessons: number;
}

function dayKeyOf(date: Date) {
  return date.toISOString().slice(0, 10);
}

/**
 * - completedLessons: video_progress rows the user has finished
 * - sessionsThisWeek: Active Learning practice sessions started in the
 *   trailing 7 days (active_learning_sessions)
 * - practiceStreakDays: consecutive days with a practice session, counting
 *   back from today (today may have no session yet without breaking a
 *   streak that started yesterday)
 */
export async function getDashboardStats(userId: string): Promise<DashboardStats> {
  const lookbackStart = new Date();
  lookbackStart.setDate(lookbackStart.getDate() - 90);
  lookbackStart.setHours(0, 0, 0, 0);

  const [{ data: sessionRows, error: sessionError }, { data: progressRows, error: progressError }] = await Promise.all([
    supabase
      .from('active_learning_sessions')
      .select('started_at')
      .eq('user_id', userId)
      .gte('started_at', lookbackStart.toISOString()),
    supabase
      .from('video_progress')
      .select('is_completed')
      .eq('user_id', userId),
  ]);

  if (sessionError) throw sessionError;
  if (progressError) throw progressError;

  const today = new Date();
  const dayKeyForOffset = (offsetDays: number) => {
    const d = new Date(today);
    d.setDate(today.getDate() - offsetDays);
    return dayKeyOf(d);
  };

  const activityDates = new Set<string>();
  const trailingSevenDayKeys = new Set(Array.from({ length: 7 }, (_, i) => dayKeyForOffset(i)));
  let sessionsThisWeek = 0;

  for (const row of sessionRows ?? []) {
    if (!row.started_at) continue;
    const key = dayKeyOf(new Date(row.started_at));
    activityDates.add(key);
    if (trailingSevenDayKeys.has(key)) sessionsThisWeek += 1;
  }

  const completedLessons = (progressRows ?? []).filter((row) => row.is_completed).length;

  let practiceStreakDays = 0;
  for (let i = 0; i < 90; i++) {
    const key = dayKeyForOffset(i);
    if (activityDates.has(key)) {
      practiceStreakDays += 1;
      continue;
    }
    if (i === 0) continue;
    break;
  }

  return { sessionsThisWeek, practiceStreakDays, completedLessons };
}