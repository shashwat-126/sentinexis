import { useEffect, useState } from 'react'
import { getIncidentTimeline, getIncidentActions } from '../api'

const STAGE_ORDER = ['DETECTED', 'RCA', 'DECISION', 'REMEDIATION', 'VERIFICATION', 'RESOLVED', 'ESCALATED', 'FAILED']

export default function IncidentDrawer({ incident, onClose }) {
  const [timeline, setTimeline] = useState([])
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!incident) return
    let cancelled = false
    setLoading(true)
    Promise.all([getIncidentTimeline(incident.id), getIncidentActions(incident.id)])
      .then(([t, a]) => {
        if (cancelled) return
        setTimeline(t)
        setActions(a)
      })
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [incident])

  if (!incident) return null

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div>
            <h2>{incident.service_name}</h2>
            <span className="mono muted">{incident.incident_uid}</span>
          </div>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>

        <div className="drawer-badges">
          <span className={`badge badge-${incident.severity.toLowerCase()}`}>{incident.severity}</span>
          <span className={`badge badge-status-${incident.recovery_status.toLowerCase()}`}>{incident.recovery_status}</span>
          {incident.root_cause && <span className="badge badge-neutral">{incident.root_cause}</span>}
        </div>

        <p className="muted">{incident.details}</p>

        <h3>Incident Timeline</h3>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : timeline.length === 0 ? (
          <p className="muted">No timeline events yet.</p>
        ) : (
          <ol className="timeline">
            {timeline.map((ev) => (
              <li key={ev.id} className="timeline-item">
                <span className="timeline-stage">{ev.stage}</span>
                <span className="timeline-msg">{ev.message}</span>
                <span className="timeline-time muted">{new Date(ev.created_at).toLocaleTimeString()}</span>
              </li>
            ))}
          </ol>
        )}

        <h3>Remediation Actions</h3>
        {actions.length === 0 ? (
          <p className="muted">No remediation actions executed.</p>
        ) : (
          <table>
            <thead>
              <tr><th>Action</th><th>Backend</th><th>Mode</th><th>Result</th></tr>
            </thead>
            <tbody>
              {actions.map((a) => (
                <tr key={a.id}>
                  <td>{a.action_type}</td>
                  <td>{a.backend}</td>
                  <td>{a.mode || '-'}</td>
                  <td>{a.result || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export { STAGE_ORDER }
