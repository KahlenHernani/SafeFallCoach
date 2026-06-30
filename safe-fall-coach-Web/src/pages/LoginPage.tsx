import '../styles/page-auth.css';
import { Link } from 'react-router-dom';
import { routes } from '../data/routes';

export function LoginPage() {
  return <div className="auth-shell">
    <form className="card auth-card">
      <p className="eyebrow">Welcome back</p>
      <h1>Sign in</h1>
      <p className="lead">Use your account to continue training and view feedback.</p>
      <label>Email
        <input type="email" placeholder="name@example.com" />
      </label>
      <label>Password
        <input type="password" placeholder="Enter your password" />
      </label>
      <button className="button button-primary" type="button">Sign in</button>
      <p className="helper-text">New here? <Link to={routes.signup}>Create an account</Link></p>
    </form>
  </div>;
}
