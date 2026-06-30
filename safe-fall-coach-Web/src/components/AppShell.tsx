import { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { routes } from '../data/routes';
import { TopNav } from './TopNav';
import { SideNav } from './SideNav';
import { useAccessibility } from '../context/AccessibilityContext';

const pageLabels: Record<string, string> = {
  [routes.home]: 'Home',
  [routes.login]: 'Sign in',
  [routes.signup]: 'Sign up',
  [routes.dashboard]: 'Dashboard',
  [routes.training]: 'Training',
  [routes.practice]: 'Practice',
  [routes.accessibility]: 'Accessibility',
};

export function AppShell() {
  const location = useLocation();
  const { settings } = useAccessibility();
  const hideNav = location.pathname === routes.login || location.pathname === routes.signup;

  // Audio guidance: announce each page when enabled.
  useEffect(() => {
    if (!settings.audioGuidance) return;
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    const label = pageLabels[location.pathname];
    if (!label) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(`${label} page`));
  }, [location.pathname, settings.audioGuidance]);

  return (
    <div className={`app-root ${settings.highContrast ? 'high-contrast' : ''}`}>
      {!hideNav && <TopNav />}
      <div className="app-layout">
        {!hideNav && !settings.simplifiedNavigation && <SideNav />}
        <main className="app-main" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
