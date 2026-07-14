import { useState } from 'react';
import { NavLink, Link, useNavigate } from 'react-router-dom';
import { routes } from '../data/routes';
import { Menu, X, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useActiveLearningAccess } from '../hooks/useActiveLearningAccess';

const navLinkClass = ({ isActive }: { isActive: boolean }) => isActive ? 'nav-link active' : 'nav-link';

export function TopNav() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, role, signOut } = useAuth();
  const { hasPracticeAccess } = useActiveLearningAccess();
  const navigate = useNavigate();
  const isAdmin = role === 'admin';

  const closeMenu = () => setMenuOpen(false);

  async function handleSignOut() {
    await signOut();
    closeMenu();
    navigate(routes.login);
  }

  return (
    <>
      <header className="top-nav">
        <Link to={routes.home} className="brand"><ShieldCheck size={26} /><span>SafeFall Coach</span></Link>
        <nav className="desktop-nav" aria-label="Primary">
          <NavLink to={routes.home} className={navLinkClass}>Home</NavLink>
          {isAdmin && <NavLink to={routes.analytics} className={navLinkClass}>Analytics</NavLink>}
          {!isAdmin && (
            hasPracticeAccess
              ? <NavLink to={routes.practice} className={navLinkClass}>Practice</NavLink>
              : <NavLink to={routes.activeLearningAccess} className={navLinkClass}>Access</NavLink>
          )}
          <NavLink to={routes.training} className={navLinkClass}>Training</NavLink>
          {isAdmin && <NavLink to={routes.practice} className={navLinkClass}>Practice</NavLink>}
          <NavLink to={routes.accessibility} className={navLinkClass}>Accessibility</NavLink>
        </nav>
        <div className="top-nav-actions">
          {user ? (
            <button className="button button-secondary" type="button" onClick={handleSignOut}>
              Sign out
            </button>
          ) : (
            <Link to={routes.login} className="button button-secondary">Sign in</Link>
          )}
          <button
            className="icon-button"
            type="button"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <X /> : <Menu />}
          </button>
        </div>
      </header>
      <nav className={menuOpen ? 'mobile-nav open' : 'mobile-nav'} aria-label="Mobile primary">
        <NavLink to={routes.home} className={navLinkClass} onClick={closeMenu}>Home</NavLink>
        {isAdmin && <NavLink to={routes.analytics} className={navLinkClass} onClick={closeMenu}>Analytics</NavLink>}
        {!isAdmin && (
          hasPracticeAccess
            ? <NavLink to={routes.practice} className={navLinkClass} onClick={closeMenu}>Practice</NavLink>
            : <NavLink to={routes.activeLearningAccess} className={navLinkClass} onClick={closeMenu}>Access</NavLink>
        )}
        <NavLink to={routes.training} className={navLinkClass} onClick={closeMenu}>Training</NavLink>
        {isAdmin && <NavLink to={routes.practice} className={navLinkClass} onClick={closeMenu}>Practice</NavLink>}
        <NavLink to={routes.accessibility} className={navLinkClass} onClick={closeMenu}>Accessibility</NavLink>
      </nav>
    </>
  );
}