import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { CheckCircle2, AlertTriangle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { routes } from '../data/routes';
import { claimQrSessionLink } from '../lib/qrSessionApi';

export function ConnectPage() {
  const { code } = useParams<{ code: string }>();
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'connecting' | 'connected' | 'error'>('connecting');
  const [message, setMessage] = useState("Connecting to your admin's session...");

  useEffect(() => {
    if (loading || !code || !user) return;

    let cancelled = false;
    async function connect() {
      try {
        const link = await claimQrSessionLink(code!, user!.id);
        if (cancelled) return;
        sessionStorage.setItem('safefall.qrSessionLinkId', link.id);
        setStatus('connected');
        setMessage('Connected! Starting your practice session...');
        setTimeout(() => navigate(routes.practice, { replace: true }), 900);
      } catch (error) {
        if (cancelled) return;
        setStatus('error');
        setMessage(error instanceof Error ? error.message : 'Unable to connect.');
      }
    }
    void connect();
    return () => { cancelled = true; };
  }, [code, user, loading, navigate]);

  return (
    <div className="status-screen">
      {status === 'connected' ? <CheckCircle2 size={40} color="#16a34a" /> : status === 'error' ? <AlertTriangle size={40} color="#dc2626" /> : null}
      <h1>{status === 'error' ? 'Connection failed' : 'Connecting to Active Learning'}</h1>
      <p>{message}</p>
    </div>
  );
}