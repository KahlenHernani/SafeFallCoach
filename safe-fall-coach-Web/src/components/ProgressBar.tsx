type Props = { label: string; value: number; };
export function ProgressBar({ label, value }: Props) {
  return <div className="progress-block"><div className="progress-row"><span>{label}</span><strong>{value}%</strong></div><div className="progress-track" aria-hidden="true"><div className="progress-fill" style={{ width: `${value}%` }} /></div></div>;
}
