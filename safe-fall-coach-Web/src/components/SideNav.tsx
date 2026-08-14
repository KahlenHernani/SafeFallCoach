import { NavLink } from 'react-router-dom';
import { routes } from '../data/routes';
import {
  Home,
  PlayCircle,
  Camera,
  Settings2,
  ShieldCheck,
  BarChart3,
  LayoutDashboard,
  MessageCircle,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useActiveLearningAccess } from '../hooks/useActiveLearningAccess';

const itemClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? 'side-link active' : 'side-link';

export function SideNav() {
  const { role } = useAuth();
  const { hasPracticeAccess } = useActiveLearningAccess();
  const isAdmin = role === 'admin';

  return (
    <aside className="side-nav" aria-label="Secondary">
      <NavLink to={routes.dashboard} className={itemClass}>
        <Home size={18} /> Dashboard
      </NavLink>

      {isAdmin && (
        <NavLink to={routes.analytics} className={itemClass}>
          <BarChart3 size={18} /> Analytics
        </NavLink>
      )}

      {isAdmin && (
        <NavLink to={routes.admin} className={itemClass}>
          <LayoutDashboard size={18} /> Admin
        </NavLink>
      )}

      {!isAdmin &&
        (hasPracticeAccess ? (
          <NavLink to={routes.practice} className={itemClass}>
            <Camera size={18} /> Practice
          </NavLink>
        ) : (
          <NavLink to={routes.activeLearningAccess} className={itemClass}>
            <ShieldCheck size={18} /> Access
          </NavLink>
        ))}

      <NavLink to={routes.training} className={itemClass}>
        <PlayCircle size={18} /> Videos
      </NavLink>

      <NavLink to={routes.feedbackHistory} className={itemClass}>
        <MessageCircle size={18} /> Feedback
      </NavLink>

      {isAdmin && (
        <NavLink to={routes.practice} className={itemClass}>
          <Camera size={18} /> Practice
        </NavLink>
      )}

      <NavLink to={routes.accessibility} className={itemClass}>
        <Settings2 size={18} /> Accessibility
      </NavLink>
    </aside>
  );
}