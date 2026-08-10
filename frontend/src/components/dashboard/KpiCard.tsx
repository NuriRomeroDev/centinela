type DeltaTone = 'up' | 'down' | 'accent'

interface KpiCardProps {
  label: string
  value: string
  delta: string
  tone: DeltaTone
  sub: string
}

export default function KpiCard({ label, value, delta, tone, sub }: KpiCardProps) {
  return (
    <article className="kpi-card">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      <div className={`kpi-delta kpi-delta--${tone}`}>{delta}</div>
      <div className="kpi-sub">{sub}</div>
    </article>
  )
}
