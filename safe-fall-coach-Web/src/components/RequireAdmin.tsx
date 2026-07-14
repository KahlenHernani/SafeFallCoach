import { Navigate, Outlet } from 'react-router-dom';
import { routes } from '../data/routes';
import { useAuth } from '../context/AuthContext';

const ADMIN_ROLES = ['admin'];

export function RequireAdmin() {
  const { role, loading } = useAuth();

  if (loading) return null;
  if (!role || !ADMIN_ROLES.includes(role)) {
    return <Navigate to={routes.dashboard} replace />;
  }
  return <Outlet />;
}