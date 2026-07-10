import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
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

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path={routes.home} element={<HomePage />} />
        <Route path={routes.login} element={<LoginPage />} />
        <Route path={routes.signup} element={<SignupPage />} />
        <Route path={routes.dashboard} element={<DashboardPage />} />
        <Route path={routes.analytics} element={<AnalyticsPage />} />
        <Route path={routes.activeLearningAccess} element={<ActiveLearningAccessPage />} />
        <Route path={routes.training} element={<TrainingPage />} />
        <Route path={routes.practice} element={<PracticePage />} />
        <Route path={routes.accessibility} element={<AccessibilityPage />} />
        <Route path="*" element={<Navigate to={routes.home} replace />} />
      </Route>
    </Routes>
  );
}
