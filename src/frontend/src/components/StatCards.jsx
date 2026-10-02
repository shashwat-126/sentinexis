function StatCard({ label, value, tone }) {
  return (
    <div className={`stat-card stat-${tone}`}>
      <div className="stat-value">{value ?? '—'}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

export default function StatCards({ stats }) {
  return (
    <div className="stat-grid">
      <StatCard label="Open Incidents" value={stats?.open} tone="warning" />
      <StatCard label="Critical" value={stats?.critical} tone="danger" />
      <StatCard label="Recovered Today" value={stats?.recovered_today} tone="success" />
      <StatCard label="Resolved (All Time)" value={stats?.resolved} tone="accent" />
      <StatCard label="Total Incidents" value={stats?.total} tone="muted" />
    </div>
  )
}
