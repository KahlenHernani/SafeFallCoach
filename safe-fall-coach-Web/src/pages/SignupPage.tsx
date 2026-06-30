import '../styles/page-auth.css';
import { Link } from 'react-router-dom';
import { routes } from '../data/routes';

export function SignupPage() {
  return <div className="auth-shell">
    <form className="card auth-card">
      <p className="eyebrow">Create account</p>
      <h1>Sign up</h1>
      <p className="lead">A simple account helps save your progress and training history.</p>
      <label>Full name
        <input type="text" placeholder="Your name" />
      </label>
      <label>Email
        <input type="email" placeholder="name@example.com" />
      </label>
      <label>Password
        <input type="password" placeholder="Choose a password" />
      </label>
      <button className="button button-primary" type="button">Create account</button>
      <p className="helper-text">Already have an account? <Link to={routes.login}>Sign in</Link></p>
    </form>
  </div>;
}
