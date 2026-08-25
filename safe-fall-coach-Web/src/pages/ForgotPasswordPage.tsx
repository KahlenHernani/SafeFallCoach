import '../styles/page-auth.css';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { routes } from '../data/routes';
import { useAuth } from '../context/AuthContext';

export function ForgotPasswordPage() {
  const { resetPasswordForEmail } = useAuth();
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const { error } = await resetPasswordForEmail(email);
    setSubmitting(false);
    if (error) {
      setError(error);
      return;
    }
    setSent(true);
  }

  return <div className="auth-shell">
    <form className="card auth-card" onSubmit={handleSubmit}>
      <p className="eyebrow">Reset password</p>
      <h1>Forgot your password?</h1>
      <p className="lead">Enter your account email and we'll send you a link to reset your password.</p>

      {sent ? (
        <p className="helper-text">
          If an account exists for <strong>{email}</strong>, a reset link has been sent. Check your inbox
          (and spam folder), then follow the link to choose a new password.
        </p>
      ) : (
        <>
          <label>Email
            <input
              type="email"
              placeholder="name@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          {error ? <p className="helper-text" style={{ color: '#dc2626' }}>{error}</p> : null}
          <button className="button button-primary" type="submit" disabled={submitting}>
            {submitting ? 'Sending…' : 'Send reset link'}
          </button>
        </>
      )}

            <p className="helper-text">
        <Link className="auth-link" to={routes.login}>Back to sign in</Link>
      </p>
    </form>
  </div>;
}