export default function IncidentsTable({ incidents, onSelect }) {
  return (
    <div className="panel panel-wide">
      <h2>Incidents</h2>
      {incidents.length === 0 ? (
        <p className="muted">No incidents recorded. The platform is healthy.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Service</th>
              <th>Severity</th>
              <th>Root Cause</th>
              <th>Action</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map((inc) => (
              <tr key={inc.id} className="clickable-row" onClick={() => onSelect(inc)}>
                <td className="muted">{new Date(inc.timestamp).toLocaleTimeString()}</td>
                <td>{inc.service_name}</td>
                <td><span className={`badge badge-${inc.severity.toLowerCase()}`}>{inc.severity}</span></td>
                <td>{inc.root_cause || '—'}</td>
                <td>{inc.executed_action || inc.recommended_action || '—'}</td>
                <td><span className={`badge badge-status-${inc.recovery_status.toLowerCase()}`}>{inc.recovery_status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
