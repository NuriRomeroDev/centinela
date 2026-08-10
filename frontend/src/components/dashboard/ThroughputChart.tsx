import { Chart } from 'primereact/chart'
import type { ThroughputPoint } from '../../types'

const WEEKDAYS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']

const PALETTE = {
  light: {
    accent: '#3d5bd9',
    rejected: '#d4521a',
    tick: '#64748b',
  },
  dark: {
    accent: '#7b97f5',
    rejected: '#e07a50',
    tick: '#8b9cba',
  },
}

export default function ThroughputChart({ points }: { points: ThroughputPoint[] }) {
  const isDark = document.documentElement.getAttribute('data-theme') === 'b'
  const p = isDark ? PALETTE.dark : PALETTE.light

  const data = {
    labels: points.map((_, index) => WEEKDAYS[index % WEEKDAYS.length]),
    datasets: [
      {
        label: 'Aceptados',
        data: points.map((pt) => pt.aceptados),
        backgroundColor: p.accent,
        borderRadius: 3,
      },
      {
        label: 'Rechazados',
        data: points.map((pt) => pt.rechazados),
        backgroundColor: p.rejected,
        borderRadius: 3,
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        stacked: true,
        grid: { display: false },
        ticks: { color: p.tick, font: { size: 11 } },
      },
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
