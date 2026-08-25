import '../../styles/page-admin.css';
import { useEffect, useState } from 'react';
import { Users, Video, Bell, QrCode } from 'lucide-react';
import { ParticipantsPanel } from './ParticipantsPanel';
import { ContentPanel } from './ContentPanel';
import { NotificationsPanel } from './NotificationsPanel';
import { ActiveLearningLivePanel } from './ActiveLearningLivePanel';

type Tab = 'participants' | 'content' | 'notifications' | 'liveSession';

const TABS: { id: Tab; label: string; icon: typeof Users }[] = [
  { id: 'participants', label: 'Participants', icon: Users },
  { id: 'content', label: 'Content', icon: Video },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'liveSession', label: 'Active Learning', icon: QrCode },
];

const ADMIN_TAB_STORAGE_KEY = 'safeFallCoach.admin.selectedTab';
const DEFAULT_TAB: Tab = 'participants';

function isTab(value: string | null): value is Tab {
  return TABS.some((tab) => tab.id === value);
}

function getStoredTab(): Tab {
  try {
    const storedTab = window.sessionStorage.getItem(ADMIN_TAB_STORAGE_KEY);
    return isTab(storedTab) ? storedTab : DEFAULT_TAB;
  } catch {
    return DEFAULT_TAB;
  }
}

export function AdminPage() {
  const [tab, setTab] = useState<Tab>(getStoredTab);

  useEffect(() => {
    try {
      window.sessionStorage.setItem(ADMIN_TAB_STORAGE_KEY, tab);
    } catch {
      // Ignore storage failures; tab state still works for the active mount.
    }
  }, [tab]);

  return (
    <div className="page-stack">
      <section className="card">
        <p className="eyebrow">Research Dashboard</p>
        <h1>Participant &amp; Content Management</h1>
        <p className="lead">Manage participants, tutorial content, and scheduled reminders.</p>
      </section>

      <div className="admin-tab-row" role="tablist">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            className={tab === id ? 'admin-tab active' : 'admin-tab'}
            type="button"
            onClick={() => setTab(id)}
          >
            <Icon size={16} /> {label}
          </button>
        ))}
      </div>

      {tab === 'participants' && <ParticipantsPanel />}
      {tab === 'content' && <ContentPanel />}
      {tab === 'notifications' && <NotificationsPanel />}
      {tab === 'liveSession' && <ActiveLearningLivePanel />}
    </div>
  );
}
