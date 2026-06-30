import { NavLink } from 'react-router-dom';
import { routes } from '../data/routes';
import { Home, PlayCircle, Camera, Settings2 } from 'lucide-react';

const itemClass = ({ isActive }: { isActive: boolean }) => isActive ? 'side-link active' : 'side-link';

export function SideNav() {
  return (
    <aside className="side-nav" aria-label="Secondary">
      <NavLink to={routes.dashboard} className={itemClass}><Home size={18} /> Dashboard</NavLink>
      <NavLink to={routes.training} className={itemClass}><PlayCircle size={18} /> Videos</NavLink>
      <NavLink to={routes.practice} className={itemClass}><Camera size={18} /> Practice</NavLink>
      <NavLink to={routes.accessibility} className={itemClass}><Settings2 size={18} /> Accessibility</NavLink>
    </aside>
  );
}
