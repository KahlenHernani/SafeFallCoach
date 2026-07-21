import '../styles/page-training.css';
import { useEffect, useState } from 'react';
import { trainingVideos } from '../data/mockData';
import { SectionCard } from '../components/SectionCard';
import { useAuth } from '../context/AuthContext';
import { listTrainingVideos, saveVideoProgress, type TrainingVideo } from '../lib/trainingVideosApi';

export function TrainingPage() {
  const { user } = useAuth();
  const [videos, setVideos] = useState<TrainingVideo[]>(trainingVideos);
  const [message, setMessage] = useState('Loading videos...');

  useEffect(() => {
    let cancelled = false;

    async function loadVideos() {
      try {
        const rows = await listTrainingVideos();
        if (cancelled) return;
        if (rows.length > 0) {
          setVideos(rows);
          setMessage('Showing videos from Supabase.');
        } else {
          setVideos(trainingVideos);
          setMessage('No active Supabase videos found. Showing local demo videos.');
        }
      } catch (error) {
        if (cancelled) return;
        setVideos(trainingVideos);
        setMessage(error instanceof Error ? error.message : 'Unable to load Supabase videos. Showing local demo videos.');
      }
    }

    void loadVideos();
    return () => { cancelled = true; };
  }, []);

  async function recordProgress(video: TrainingVideo, element: HTMLVideoElement, completed: boolean) {
    if (!user || !video.databaseId) return;

    try {
      await saveVideoProgress(
        user.id,
        video.databaseId,
        element.currentTime,
        element.duration,
        completed,
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to save video progress.');
    }
  }

  return <div className="page-stack">
    <section className="card">
      <p className="eyebrow">Training videos</p>
      <h1>Watch simple lessons</h1>
      <p className="lead">Choose a short video and learn at your own pace.</p>
    </section>
    <p className="helper-text">{message}</p>
    <div className="video-grid">
      {videos.map((video) => (
        <article className="card video-card" key={video.id}>
          <video
            className="video-preview"
            src={video.source}
            poster={video.thumbnail || undefined}
            controls
            preload="auto"
            playsInline
            onPlay={(event) => void recordProgress(video, event.currentTarget, false)}
            onPause={(event) => void recordProgress(video, event.currentTarget, false)}
            onEnded={(event) => void recordProgress(video, event.currentTarget, true)}
          />
          <h2>{video.title}</h2>
          <p>{video.summary}</p>
          <div className="tag-row">
            <span className="tag">{video.duration}</span>
            <span className="tag">{video.level}</span>
            <span className="tag">{video.category}</span>
          </div>
        </article>
      ))}
    </div>
    <SectionCard title="Tip">
      <p>Progress is saved for Supabase videos when you start, pause, or complete a lesson.</p>
    </SectionCard>
  </div>;
}
