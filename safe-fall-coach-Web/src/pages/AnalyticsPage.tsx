import '../styles/page-analytics.css';
import { useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Activity, BarChart3, Clock3, RefreshCw, Route, TrendingUp } from 'lucide-react';
import { SectionCard } from '../components/SectionCard';
import { getAnalyticsDashboard, type AnalyticsDashboard } from '../lib/activeLearningApi';

const journeyLabels: Record<keyof AnalyticsDashboard['journey'], string> = {
  registration_to_onboarding: 'Registration to onboarding',
  onboarding_to_first_training: 'Onboarding to first training',
  first_training_to_week_one: 'First training to week 1',
  week_one_to_month_one: 'Week 1 to month 1',
};

const heatColors = ['#dbeafe', '#bfdbfe', '#93c5fd', '#60a5fa', '#2563eb'];

function percent(value: number) {
  return `${value.toFixed(1)}%`;
}

export function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsDashboard | null>(null);
  const [message, setMessage] = useState('Loading analytics...');

  async function loadAnalytics() {
    try {
      setMessage('Loading analytics...');
      const data = await getAnalyticsDashboard();
      setAnalytics(data);
      setMessage('Analytics loaded.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to load analytics.');
    }
  }

  useEffect(() => {
    void loadAnalytics();
  }, []);

  const journeyData = useMemo(() => {
    if (!analytics) return [];
    return Object.entries(analytics.journey).map(([key, value]) => ({
      step: journeyLabels[key as keyof AnalyticsDashboard['journey']],
      rate: value,
    }));
  }, [analytics]);

  const trainingData = analytics ? [
    { label: 'Started', value: analytics.training.sessions_started },
    { label: 'Completed', value: analytics.training.sessions_completed },
  ] : [];

  const maxHeat = analytics
    ? Math.max(1, ...analytics.engagement.most_active_days.map((item) => item.activity))
    : 1;

  return <div className="page-stack analytics-page">
    <section className="card analytics-hero">
      <div>
        <p className="eyebrow">Admin analytics</p>
        <h1>Dashboard and usage analytics</h1>
        <p className="lead">Database-backed engagement, journey, heatmap, and training completion metrics.</p>
      </div>
      <button className="button button-secondary" type="button" onClick={() => void loadAnalytics()}>
        <RefreshCw size={16} /> Refresh
      </button>
    </section>

    {analytics ? (
      <>
        <div className="analytics-kpi-grid">
          <article className="card analytics-kpi">
            <Activity size={18} />
            <span>Daily active users</span>
            <strong>{analytics.activity.dau}</strong>
          </article>
          <article className="card analytics-kpi">
            <TrendingUp size={18} />
            <span>Weekly active users</span>
            <strong>{analytics.activity.wau}</strong>
          </article>
          <article className="card analytics-kpi">
            <BarChart3 size={18} />
            <span>Monthly active users</span>
            <strong>{analytics.activity.mau}</strong>
          </article>
          <article className="card analytics-kpi">
            <Clock3 size={18} />
            <span>Completion rate</span>
            <strong>{percent(analytics.training.average_completion_rate)}</strong>
          </article>
        </div>

        <div className="analytics-grid">
          <SectionCard title="Active user growth trend">
            <div className="chart-frame">
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={analytics.activity.growth_trend}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={24} />
                  <YAxis allowDecimals={false} width={32} />
                  <Tooltip />
                  <Area type="monotone" dataKey="active_users" stroke="#2563eb" fill="#bfdbfe" name="Active users" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>
          <SectionCard title="Monthly progress">
            <div className="chart-frame">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={analytics.monthlyProgress}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} width={32} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="completedLessons" name="Lessons completed" fill="#2563eb" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="practiceSessions" name="Practice sessions" fill="#16a34a" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>
          <SectionCard title="User journey analytics">
            <div className="journey-list">
              {journeyData.map((item) => (
                <div className="journey-row" key={item.step}>
                  <div>
                    <Route size={16} />
                    <span>{item.step}</span>
                  </div>
                  <strong>{percent(item.rate)}</strong>
                  <div className="journey-bar" aria-hidden="true">
                    <span style={{ width: `${item.rate}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Engagement heatmap">
            <div className="heatmap-row">
              {analytics.engagement.most_active_days.map((item) => {
                const index = Math.min(heatColors.length - 1, Math.floor((item.activity / maxHeat) * (heatColors.length - 1)));
                return (
                  <div className="heat-cell" style={{ background: heatColors[index] }} key={item.day}>
                    <strong>{item.day}</strong>
                    <span>{item.activity}</span>
                  </div>
                );
              })}
            </div>
            <div className="chart-frame chart-frame-compact">
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={analytics.engagement.most_active_times}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} width={32} />
                  <Tooltip />
                  <Bar dataKey="activity" name="Activity" fill="#16a34a" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>

          <SectionCard title="Session frequency patterns">
            <div className="chart-frame chart-frame-compact">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={analytics.engagement.session_frequency_patterns}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} width={32} />
                  <Tooltip />
                  <Bar dataKey="users" name="Users" radius={[4, 4, 0, 0]}>
                    {analytics.engagement.session_frequency_patterns.map((entry, index) => (
                      <Cell key={entry.bucket} fill={['#f97316', '#2563eb', '#16a34a'][index]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>

          <SectionCard title="Training completion metrics">
            <div className="training-metrics">
              <div>
                <span>Sessions started</span>
                <strong>{analytics.training.sessions_started}</strong>
              </div>
              <div>
                <span>Sessions completed</span>
                <strong>{analytics.training.sessions_completed}</strong>
              </div>
              <div>
                <span>Drop-off rate</span>
                <strong>{percent(analytics.training.drop_off_rate)}</strong>
              </div>
            </div>
            <div className="chart-frame chart-frame-compact">
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={trainingData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" />
                  <YAxis allowDecimals={false} width={36} />
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="#dc2626" strokeWidth={3} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>

        </div>
      </>
    ) : (
      <SectionCard title="Analytics status">
        <p>{message}</p>
      </SectionCard>
    )}
    {analytics ? <p className="helper-text">{message}</p> : null}
  </div>;
}