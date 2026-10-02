export default function ServiceHealthGrid({ services }) {
  return (
    <div className="panel">
      <h2>Cluster Health</h2>
      <div className="health-grid">
        {services.map((s) => (
          <div key={s.key} className={`health-chip ${s.healthy ? 'health-up' : 'health-down'}`}>
            <span className="dot">●</span>
            {s.label}
          </div>
        ))}
      </div>
    </div>
  )
}
