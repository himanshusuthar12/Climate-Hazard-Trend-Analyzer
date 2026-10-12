import { Chart as C, CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend } from 'chart.js'
import { Line, Bar } from 'react-chartjs-2'

C.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend)

const opts = { responsive: true, plugins: { legend: { labels: { color: '#e2e8f0' } } }, scales: { x: { ticks: { color: '#94a3b8', maxTicksLimit: 12 } }, y: { ticks: { color: '#94a3b8' } } } }

export function DaysChart({ yearly, trend }) {
  const labels = yearly.map((y) => y.year)
  const roll = trend?.rolling_5y?.map((r) => r.value) || []
  return (
    <Line options={opts} data={{ labels, datasets: [
      { label: 'Heatwave days / year', data: yearly.map((y) => y.heatwave_days), borderColor: '#f97316', tension: 0.25 },
      { label: '5-yr rolling mean', data: roll, borderColor: '#38bdf8', borderDash: [6, 4], tension: 0.25 },
    ]}} />
  )
}

export function EventsChart({ yearly }) {
  return (
    <Bar options={opts} data={{ labels: yearly.map((y) => y.year), datasets: [
      { label: 'Heatwave events / year', data: yearly.map((y) => y.heatwave_events), backgroundColor: '#fb923c' },
    ]}} />
  )
}

export function TmaxChart({ yearly }) {
  return (
    <Line options={opts} data={{ labels: yearly.map((y) => y.year), datasets: [
      { label: 'Mean annual Tmax (°C)', data: yearly.map((y) => y.mean_tmax), borderColor: '#facc15', tension: 0.25 },
    ]}} />
  )
}
