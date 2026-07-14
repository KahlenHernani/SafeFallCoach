import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { routes } from '../data/routes';
import { useAuth } from '../context/AuthContext';

export function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return null;
  if (!user) {
    return <Navigate to={routes.login} replace state={{ from: location }} />;
  }
  return <Outlet />;
}