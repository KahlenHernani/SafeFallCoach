import '../styles/page-accessibility.css';
import { useAccessibility } from '../context/AccessibilityContext';
import { SectionCard } from '../components/SectionCard';

export function AccessibilityPage() {
  const { settings, setSettings } = useAccessibility();

  return <div className="page-stack"><section className="card"><p className="eyebrow">Accessibility</p><h1>Make the app easier to use</h1><p className="lead">These controls are meant to support comfort, clarity, and reduced overload.</p></section><SectionCard title="Text size"><input type="range" min="0.9" max="1.3" step="0.1" value={settings.fontScale} onChange={(e) => setSettings((prev) => ({ ...prev, fontScale: Number(e.target.value) }))} aria-label="Font size" /></SectionCard><SectionCard title="Display options"><label className="toggle-row"><input type="checkbox" checked={settings.highContrast} onChange={(e) => setSettings((prev) => ({ ...prev, highContrast: e.target.checked }))} /> High contrast mode</label><label className="toggle-row"><input type="checkbox" checked={settings.simplifiedNavigation} onChange={(e) => setSettings((prev) => ({ ...prev, simplifiedNavigation: e.target.checked }))} /> Simplified navigation</label><label className="toggle-row"><input type="checkbox" checked={settings.audioGuidance} onChange={(e) => setSettings((prev) => ({ ...prev, audioGuidance: e.target.checked }))} /> Audio guidance</label></SectionCard></div>;
}
