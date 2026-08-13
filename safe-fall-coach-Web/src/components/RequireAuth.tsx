import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { routes } from '../data/routes';
import { useAuth } from '../context/AuthContext';

function LoadingScreen() {
  return (
    <div className="status-screen">
      <h1>Loading SafeFall Coach</h1>
      <p>Checking your sign-in status.</p>
    </div>
  );
}

export function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <LoadingScreen />;
  if (!user) {
    return <Navigate to={routes.login} replace state={{ from: location }} />;
  }
  return <Outlet />;
}
