import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { RequireAuth } from './components/RequireAuth';
import { RequireAdmin } from './components/RequireAdmin';
import { routes } from './data/routes';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { DashboardPage } from './pages/DashboardPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { ActiveLearningAccessPage } from './pages/ActiveLearningAccessPage';
import { TrainingPage } from './pages/TrainingPage';
import { PracticePage } from './pages/PracticePage';
import { AccessibilityPage } from './pages/AccessibilityPage';
import { AdminPage } from './pages/admin/AdminPage';
import { FeedbackHistoryPage } from './pages/FeedbackHistoryPage';
import { useAuth } from './context/AuthContext';

/**
 * '/' is the public landing page. Signed-out visitors see HomePage;
 * signed-in users are bounced straight to the Dashboard.
 */
function HomeRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="status-screen">
        <h1>Loading SafeFall Coach</h1>
        <p>Checking your sign-in status.</p>
      </div>
    );
  }

  if (user) {
    return <Navigate to={routes.dashboard} replace />;
  }

  return <HomePage />;
}

export default function App() {
  return (
    <Routes>
      {/* Public — no AppShell nav, no auth required */}
      <Route path={routes.login} element={<LoginPage />} />
      <Route path={routes.signup} element={<SignupPage />} />

      <Route element={<AppShell />}>
        {/* Public — HomeRoute decides landing page vs. redirect */}
        <Route path={routes.home} element={<HomeRoute />} />

        {/* Everything else requires sign-in */}
        <Route element={<RequireAuth />}>
          <Route path={routes.dashboard} element={<DashboardPage />} />
          <Route
            path={routes.activeLearningAccess}
            element={<ActiveLearningAccessPage />}
          />
          <Route path={routes.training} element={<TrainingPage />} />
          <Route path={routes.practice} element={<PracticePage />} />
          <Route
            path={routes.feedbackHistory}
            element={<FeedbackHistoryPage />}
          />
          <Route
            path={routes.accessibility}
            element={<AccessibilityPage />}
          />

          {/* Analytics — admins only */}
          <Route element={<RequireAdmin />}>
            <Route path={routes.analytics} element={<AnalyticsPage />} />
            <Route path={routes.admin} element={<AdminPage />} />
          </Route>
        </Route>

        {/* Unknown paths fall back to Home, which handles the redirect */}
        <Route path="*" element={<Navigate to={routes.home} replace />} />
      </Route>
    </Routes>
  );
}