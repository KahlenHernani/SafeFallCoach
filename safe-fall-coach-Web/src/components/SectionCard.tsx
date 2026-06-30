type Props = { title: string; children: React.ReactNode; action?: React.ReactNode; };
export function SectionCard({ title, children, action }: Props) {
  return <section className="card"><div className="card-header"><h2>{title}</h2>{action}</div>{children}</section>;
}
