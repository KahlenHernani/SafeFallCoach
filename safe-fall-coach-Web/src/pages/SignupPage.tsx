import '../styles/page-auth.css';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { routes } from '../data/routes';
import { useAuth } from '../context/AuthContext';

export function SignupPage() {
  const { signUp } = useAuth();
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmMessage, setConfirmMessage] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const { error } = await signUp(email, password, firstName, lastName);
    setSubmitting(false);
    if (error) {
      setError(error);
      return;
    }
    // If email confirmation is required, there's no session yet.
    setConfirmMessage('Check your email to confirm your account, then sign in.');
    setTimeout(() => navigate(routes.login), 1500);
  }

  return <div className="auth-shell">
    <form className="card auth-card" onSubmit={handleSubmit}>
      <p className="eyebrow">Create account</p>
      <h1>Sign up</h1>
      <p className="lead">A simple account helps save your progress and training history.</p>
      <label>First name
        <input type="text" placeholder="Your first name" value={firstName}
          onChange={(e) => setFirstName(e.target.value)} required />
      </label>
      <label>Last name
        <input type="text" placeholder="Your last name" value={lastName}
          onChange={(e) => setLastName(e.target.value)} required />
      </label>
      <label>Email
        <input type="email" placeholder="name@example.com" value={email}
          onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label>Password
        <input type="password" placeholder="Choose a password" value={password}
          onChange={(e) => setPassword(e.target.value)} required minLength={6} />
      </label>
      {error ? <p className="helper-text" style={{ color: '#dc2626' }}>{error}</p> : null}
      {confirmMessage ? <p className="helper-text">{confirmMessage}</p> : null}
      <button className="button button-primary" type="submit" disabled={submitting}>
        {submitting ? 'Creating account…' : 'Create account'}
      </button>
      <p className="helper-text">Already have an account? <Link to={routes.login}>Sign in</Link></p>
    </form>
  </div>;
}