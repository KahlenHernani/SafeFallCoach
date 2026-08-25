import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { RequireAuth } from './components/RequireAuth';
import { RequireAdmin } from './components/RequireAdmin';
import { routes } from './data/routes';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';
import { DashboardPage } from './pages/DashboardPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { ActiveLearningAccessPage } from './pages/ActiveLearningAccessPage';
import { TrainingPage } from './pages/TrainingPage';
import { PracticePage } from './pages/PracticePage';
import { AccessibilityPage } from './pages/AccessibilityPage';
import { AdminPage } from './pages/admin/AdminPage';
import { FeedbackHistoryPage } from './pages/FeedbackHistoryPage';
import { ConnectPage } from './pages/ConnectPage';
import { useAuth } from './context/AuthContext';

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
      <Route path={routes.forgotPassword} element={<ForgotPasswordPage />} />
      <Route path={routes.resetPassword} element={<ResetPasswordPage />} />

      <Route element={<AppShell />}>
        <Route path={routes.home} element={<HomeRoute />} />

        <Route element={<RequireAuth />}>
          <Route path={routes.dashboard} element={<DashboardPage />} />
          <Route path={routes.connect} element={<ConnectPage />} />
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

          <Route element={<RequireAdmin />}>
            <Route path={routes.analytics} element={<AnalyticsPage />} />
            <Route path={routes.admin} element={<AdminPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to={routes.home} replace />} />
      </Route>
    </Routes>
  );
}