import '../styles/page-auth.css';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { routes } from '../data/routes';
import { useAuth } from '../context/AuthContext';

export function LoginPage() {
  const { signIn, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Already signed in (e.g. navigated back to /login manually) — bounce to
  // the dashboard instead of showing the sign-in form again.
  useEffect(() => {
    if (user) navigate(routes.dashboard, { replace: true });
  }, [user, navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const { error } = await signIn(email, password);
    setSubmitting(false);
    if (error) {
      setError(error);
      return;
    }
    navigate(routes.dashboard, { replace: true });
  }

  if (user) return null;

  return <div className="auth-shell">
    <form className="card auth-card" onSubmit={handleSubmit}>
      <p className="eyebrow">Welcome back</p>
      <h1>Sign in</h1>
      <p className="lead">Use your account to continue training and view feedback.</p>
      <label>Email
        <input
          type="email"
          placeholder="name@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </label>
      <label>Password
        <input
          type="password"
          placeholder="Enter your password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      {error ? <p className="helper-text" style={{ color: '#dc2626' }}>{error}</p> : null}
      <button className="button button-primary" type="submit" disabled={submitting}>
        {submitting ? 'Signing in…' : 'Sign in'}
      </button>
      <p className="helper-text">New here? <Link to={routes.signup}>Create an account</Link></p>
    </form>
  </div>;
}