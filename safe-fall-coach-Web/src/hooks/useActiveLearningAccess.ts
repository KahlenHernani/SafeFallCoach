import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { getActiveLearningAccess, requestActiveLearningAccess, type ActiveLearningAccess } from '../lib/activeLearningApi';

export function useActiveLearningAccess() {
  const { user } = useAuth();
  const [access, setAccess] = useState<ActiveLearningAccess | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const participantId = user?.id ?? null;

  const refresh = useCallback(async () => {
    if (!participantId) {
      setAccess(null);
      setLoading(false);
      return;
    }
    try {
      const result = await getActiveLearningAccess(participantId);
      setAccess(result);
      setError(null);
    } catch (err) {
      setAccess(null);
      setError(err instanceof Error ? err.message : 'Unable to load access status.');
    } finally {
      setLoading(false);
    }
  }, [participantId]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function requestAccess() {
    if (!participantId) return;
    try {
      const result = await requestActiveLearningAccess(participantId);
      setAccess(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to submit request.');
    }
  }

  const hasPracticeAccess = !!access && access.request_status === 'approved' && access.enabled;

  return { participantId, access, loading, error, hasPracticeAccess, refresh, requestAccess };
}