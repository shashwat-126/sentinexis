import { useEffect, useState } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js'
import { getMetricsHistory } from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend)

const MONITORED = ['inference-service', 'result-service', 'api-gateway', 'auth-service', 'incident-service']

// Pulled from the same design tokens index.css defines (Chart.js renders to
// canvas, so it needs literal values, not CSS custom properties -- these
// are kept in sync with :root in index.css by hand since there are only
// four of them).
const COLOR_CPU = '#6b93c9'      // --status-info
const COLOR_MEMORY = '#5fb488'   // --status-ok
const COLOR_LATENCY = '#e2a33d'  // --signal
const COLOR_ERROR = '#d3685f'    // --status-critical
const COLOR_AXIS = '#8b93a3'     // --ink-500
const COLOR_GRID = '#262b34'     // --hairline

export default function MetricsChart() {
  const [service, setService] = useState(MONITORED[0])
  const [rows, setRows] = useState([])

  useEffect(() => {
    let cancelled = false
    const load = () => {
      getMetricsHistory(service)
        .then((data) => !cancelled && setRows(data))
        .catch(() => {})
    }
    load()
    const interval = setInterval(load, 15000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [service])

  const labels = rows.map((r) => new Date(r.created_at).toLocaleTimeString())

  const data = {
    labels,
    datasets: [
      {
        label: 'CPU %',
        data: rows.map((r) => r.cpu_percent),
        borderColor: COLOR_CPU,
        backgroundColor: COLOR_CPU,
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.25,
      },
      {
        label: 'Memory %',
        data: rows.map((r) => r.memory_percent),
        borderColor: COLOR_MEMORY,
        backgroundColor: COLOR_MEMORY,
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.25,
      },
      {
        label: 'Latency (ms)',
        data: rows.map((r) => r.latency_ms),
        borderColor: COLOR_LATENCY,
        backgroundColor: COLOR_LATENCY,
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.25,
      },
      {
        label: 'Error Rate %',
        data: rows.map((r) => r.error_rate_percent),
        borderColor: COLOR_ERROR,
        backgroundColor: COLOR_ERROR,
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.25,
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        labels: { color: COLOR_AXIS, font: { family: "'IBM Plex Sans', sans-serif", size: 12 }, boxWidth: 12, boxHeight: 2 },
      },
    },
    scales: {
      x: { ticks: { color: COLOR_AXIS, font: { family: "'IBM Plex Mono', monospace", size: 10 } }, grid: { color: COLOR_GRID } },
      y: { ticks: { color: COLOR_AXIS, font: { family: "'IBM Plex Mono', monospace", size: 10 } }, grid: { color: COLOR_GRID } },
    },
  }

  return (
    <div className="panel panel-wide">
      <div className="panel-header-row">
        <h2>Metrics History</h2>
        <select className="service-select" value={service} onChange={(e) => setService(e.target.value)}>
          {MONITORED.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>
      {rows.length === 0 ? (
        <p className="muted">No metric snapshots yet for {service}. The RCA engine reports one every ~15s.</p>
      ) : (
        <div className="chart-frame">
          <Line data={data} options={options} />
        </div>
      )}
    </div>
  )
}
