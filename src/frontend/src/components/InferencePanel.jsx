import { useEffect, useState } from 'react'
import { triggerInference, getResults } from '../api'

export default function InferencePanel() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchResults = () => {
    getResults().then(setResults).catch(() => {})
  }

  useEffect(() => {
    fetchResults()
    const interval = setInterval(fetchResults, 8000)
    return () => clearInterval(interval)
  }, [])

  const run = async () => {
    setLoading(true)
    setError(null)
    try {
      await triggerInference()
      setTimeout(fetchResults, 1500)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Inference failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel panel-wide">
      <div className="panel-header-row">
        <h2>Inference &amp; Anomaly Feed</h2>
        <button className="action-btn" onClick={run} disabled={loading}>
          {loading ? 'Processing…' : 'Send Test Inference'}
        </button>
      </div>
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {results.length > 0 ? (
        <table>
          <thead>
            <tr><th>Job ID</th><th>Status</th><th>Anomaly Score</th></tr>
          </thead>
          <tbody>
            {results.map((r, i) => (
              <tr key={i}>
                <td>{r.req_id}</td>
                <td>{r.status}</td>
                <td>
                  <span style={{ color: r.score > 80 ? 'var(--danger)' : r.score > 50 ? 'var(--warning)' : 'var(--success)' }}>
                    {r.score ? r.score.toFixed(2) : '-'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted">No recent results. Trigger an inference to see data.</p>
      )}
    </div>
  )
}
