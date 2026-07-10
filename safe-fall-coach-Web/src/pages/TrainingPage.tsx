import '../styles/page-training.css';
import { trainingVideos } from '../data/mockData';
import { SectionCard } from '../components/SectionCard';

export function TrainingPage() {
  return <div className="page-stack">
    <section className="card">
      <p className="eyebrow">Training videos</p>
      <h1>Watch simple lessons</h1>
      <p className="lead">Choose a short video and learn at your own pace.</p>
    </section>
    <div className="video-grid">
      {trainingVideos.map((video) => (
        <article className="card video-card" key={video.id}>
          <video
            className="video-preview"
            src={video.source}
            controls
            preload="auto"
            playsInline
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
      <p>Keep the lesson list short and use one clear action per card.</p>
    </SectionCard>
  </div>;
}
