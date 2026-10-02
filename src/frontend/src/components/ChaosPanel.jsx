import { useState } from 'react'
import { triggerChaos } from '../api'

// Database chaos is deliberately not offered here -- Postgres is a shared
// dependency of nearly every service, so stopping it makes the whole
// control plane look broken rather than demonstrating one service's
// self-healing. It's still reachable directly against remediation-service
// for an isolated staging experiment, gated behind ENABLE_DB_CHAOS=true.
const SCENARIOS = [
  { key: 'cpu-spike', label: 'CPU / Latency Degradation', needsConfirm: false, target: 'inference-service' },
  { key: 'memory-leak', label: 'Error-Rate Degradation', needsConfirm: false, target: 'inference-service' },
  { key: 'high-latency', label: 'Latency Fault Injection', needsConfirm: false, target: 'inference-service' },
  { key: 'container-failure', label: 'Container Failure (real)', needsConfirm: true, target: 'inference-service' },
]

export default function ChaosPanel() {
  const [status, setStatus] = useState({})
  const [busy, setBusy] = useState(null)

  const run = async (scenario) => {
    setBusy(scenario.key)
    try {
      const payload = scenario.needsConfirm
        ? { container_name: scenario.target, confirm: true }
        : {}
      await triggerChaos(scenario.key, payload)
      setStatus((s) => ({ ...s, [scenario.key]: 'triggered' }))
    } catch {
      setStatus((s) => ({ ...s, [scenario.key]: 'failed' }))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="panel">
      <h2>Chaos Engineering</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        Inject a fault and watch the self-healing loop detect, decide, remediate, and verify recovery.
        The first three scenarios are controlled, application-level fault injection (they shape
        inference-service's own latency/error behavior); Container Failure actually stops a real
        container via the Docker SDK.
      </p>
      <div className="chaos-grid">
        {SCENARIOS.map((s) => (
          <button
            key={s.key}
            className={`action-btn chaos-btn ${s.needsConfirm ? 'chaos-btn-danger' : ''}`}
            disabled={busy === s.key}
            onClick={() => run(s)}
          >
            {busy === s.key ? 'Injecting…' : s.label}
            {status[s.key] && <span className="chaos-status">{status[s.key]}</span>}
          </button>
        ))}
      </div>
    </div>
  )
}
