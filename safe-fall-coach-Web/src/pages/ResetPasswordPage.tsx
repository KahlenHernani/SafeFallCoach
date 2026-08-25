import '../styles/page-auth.css';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { routes } from '../data/routes';
import { useAuth } from '../context/AuthContext';
import { supabase } from '../lib/supabaseClient';

export function ResetPasswordPage() {
  const { updatePassword } = useAuth();
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  // Supabase parses the recovery token from the URL and fires this event
  // once a temporary session is established, which is required before
  // updateUser({ password }) will succeed.
  useEffect(() => {
    const { data: listener } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY') setReady(true);
    });
    // In case the event already fired before this component mounted.
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) setReady(true);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    const { error } = await updatePassword(password);
    setSubmitting(false);
    if (error) {
      setError(error);
      return;
    }
    setDone(true);
    setTimeout(() => navigate(routes.dashboard, { replace: true }), 1500);
  }

  return <div className="auth-shell">
    <form className="card auth-card" onSubmit={handleSubmit}>
      <p className="eyebrow">Reset password</p>
      <h1>Choose a new password</h1>

      {!ready && !done ? (
        <p className="helper-text">
          Verifying your reset link… If this doesn't update in a few seconds, the link may be expired —
          request a new one from the sign-in page.
        </p>
      ) : done ? (
        <p className="helper-text">Password updated! Redirecting you to your dashboard…</p>
      ) : (
        <>
          <label>New password
            <input
              type="password"
              placeholder="Enter a new password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </label>
          <label>Confirm new password
            <input
              type="password"
              placeholder="Re-enter the new password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={6}
            />
          </label>
          {error ? <p className="helper-text" style={{ color: '#dc2626' }}>{error}</p> : null}
          <button className="button button-primary" type="submit" disabled={submitting}>
            {submitting ? 'Updating…' : 'Update password'}
          </button>
        </>
      )}
    </form>
  </div>;
}