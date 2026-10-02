const GRAFANA_URL = import.meta.env.VITE_GRAFANA_URL || 'http://localhost:3001'
const PROMETHEUS_URL = import.meta.env.VITE_PROMETHEUS_URL || 'http://localhost:9090'

export default function ObservabilityLinks() {
  return (
    <div className="panel">
      <h2>Observability</h2>
      <div className="link-list">
        <a href={GRAFANA_URL} target="_blank" rel="noreferrer" className="action-btn action-btn-secondary">
          Open Grafana ↗
        </a>
        <a href={PROMETHEUS_URL} target="_blank" rel="noreferrer" className="action-btn action-btn-secondary">
          Open Prometheus ↗
        </a>
      </div>
    </div>
  )
}
