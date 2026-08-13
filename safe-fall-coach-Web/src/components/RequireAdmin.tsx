import { Navigate, Outlet } from 'react-router-dom';
import { routes } from '../data/routes';
import { useAuth } from '../context/AuthContext';

const ADMIN_ROLES = ['admin'];

function LoadingScreen() {
  return (
    <div className="status-screen">
      <h1>Loading SafeFall Coach</h1>
      <p>Checking your account permissions.</p>
    </div>
  );
}

export function RequireAdmin() {
  const { role, loading, roleLoading } = useAuth();

  if (loading || roleLoading) return <LoadingScreen />;
  if (!role || !ADMIN_ROLES.includes(role)) {
    return <Navigate to={routes.dashboard} replace />;
  }
  return <Outlet />;
}
