import '../styles/page-home.css';
import { SectionCard } from '../components/SectionCard';
import { Brain, Camera, CircleCheckBig, ShieldCheck, Users } from 'lucide-react';

export function HomePage() {
  return (
    <div className="page-stack">
      <section className="hero card">
        <div className="hero-copy">
          <p className="eyebrow">Research-friendly fall prevention</p>
          <h1>Simple, accessible training for safer movement.</h1>
          <p className="lead">SafeFall Coach helps older adults watch short lessons, practice with a camera, and review gentle AI feedback without payments or clutter.</p>
        </div>
        <div className="hero-panel" aria-label="Key benefits">
          <div className="mini-stat"><ShieldCheck /><span>High contrast and large text</span></div>
          <div className="mini-stat"><Camera /><span>Practice with camera preview</span></div>
          <div className="mini-stat"><Brain /><span>Gentle feedback after each session</span></div>
        </div>
      </section>
      <div className="grid-2">
        <SectionCard title="How it works"><div className="feature-list"><div><CircleCheckBig size={18} /> Watch a short training video.</div><div><CircleCheckBig size={18} /> Practice the movement using your camera.</div><div><CircleCheckBig size={18} /> Read simple feedback and next steps.</div></div></SectionCard>
        <SectionCard title="Why this is easy to use"><div className="feature-list"><div><Users size={18} /> Big buttons and plain language.</div><div><Users size={18} /> Minimal navigation and no payment screens.</div><div><Users size={18} /> Built for caregivers and older adults.</div></div></SectionCard>
      </div>
    </div>
  );
}
