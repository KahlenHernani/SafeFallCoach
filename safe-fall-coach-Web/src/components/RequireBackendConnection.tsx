import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw, Wifi } from 'lucide-react';
import { getHealth } from '../lib/activeLearningApi';

type GateStatus = 'checking' | 'online' | 'offline';

const RECHECK_INTERVAL_MS = 15000;

export function RequireBackendConnection({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<GateStatus>('checking');
  const [detail, setDetail] = useState<string | null>(null);

  const check = useCallback(async () => {
    try {
      const health = await getHealth();
      if (health.status === 'ok' || health.status === 'starting') {
        setStatus('online');
        setDetail(null);
      } else {
        setStatus('offline');
        setDetail('The workstation responded but reported it is not ready.');
      }
    } catch (error) {
      setStatus('offline');
      setDetail(error instanceof Error ? error.message : 'Unable to reach the workstation.');
    }
  }, []);

  useEffect(() => {
    void check();
    const interval = setInterval(() => void check(), RECHECK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [check]);

  if (status === 'online') return <>{children}</>;

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: '2rem',
        textAlign: 'center',
        background: '#f5f8fb',
      }}
    >
      <div style={{ maxWidth: 460 }}>
        {status === 'checking' ? <Wifi size={40} /> : <AlertTriangle size={40} color="#dc2626" />}
        <h1 style={{ marginTop: '1rem' }}>
          {status === 'checking' ? 'Connecting…' : 'Workstation unreachable'}
        </h1>
        <p style={{ color: '#54657a' }}>
          {status === 'checking'
            ? 'Checking your connection to the SafeFall Active Learning workstation.'
            : `SafeFall Coach requires an active connection to the Active Learning workstation to load (campus network or VPN). ${detail ?? ''}`}
        </p>
        {status === 'offline' && (
          <button
            className="button button-primary"
            type="button"
            onClick={() => {
              setStatus('checking');
              void check();
            }}
            style={{ marginTop: '1rem', display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <RefreshCw size={16} /> Retry
          </button>
        )}
      </div>
    </div>
  );
}