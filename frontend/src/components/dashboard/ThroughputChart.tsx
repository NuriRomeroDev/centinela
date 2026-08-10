import { Chart } from 'primereact/chart'
import type { ThroughputPoint } from '../../types'

const WEEKDAYS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']

export default function ThroughputChart({ points }: { points: ThroughputPoint[] }) {
  const data = {
    labels: points.map((_, index) => WEEKDAYS[index % WEEKDAYS.length]),
    datasets: [
      {
        label: 'Aceptados',
        data: points.map((p) => p.aceptados),
        backgroundColor: 'var(--accent)',
      },
      {
        label: 'Rechazados',
        data: points.map((p) => p.rechazados),
        backgroundColor: 'var(--rejected-bar)',
      },
    ],
  }
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { stacked: true, grid: { display: false } },
      y: { stacked: true, display: false },
    },
  }
  return (
    <div className="throughput-card">
      <div className="throughput-chart">
        <Chart type="bar" data={data} options={options} />
      </div>
      <div className="chart-legend">
        <span className="chart-legend-item">
          <span className="chart-legend-swatch chart-legend-swatch--accent" />
          Aceptados
        </span>
        <span className="chart-legend-item">
          <span className="chart-legend-swatch chart-legend-swatch--rejected" />
          Rechazados
        </span>
      </div>
    </div>
  )
}
