import { beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Dashboard from './Dashboard'
import { api } from '../api/client'
import type { DashboardMetrics, LogEntry, StatusDistributionItem, ThroughputPoint } from '../types'

const globalCss = readFileSync('src/styles/global.css', 'utf-8')

vi.mock('primereact/chart', () => ({
  Chart: ({ data, options }: { data: Record<string, unknown>; options: Record<string, unknown> }) => (
    <div
      data-testid="chart"
      data-data={JSON.stringify(data)}
      data-options={JSON.stringify(options)}
    />
  ),
}))

vi.mock('../api/client', () => ({
  api: {
    dashboardMetrics: vi.fn(),
    throughput: vi.fn(),
    statusDistribution: vi.fn(),
    recentLogs: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

const metrics: DashboardMetrics = {
  sincronizaciones_activas: 1,
  completadas_hoy: 3,
  archivos_rechazados: 2,
  tasa_errores_criticos: '8.2',
}

const throughput: ThroughputPoint[] = [
  { fecha: '2026-08-04', aceptados: 4, rechazados: 1 },
  { fecha: '2026-08-05', aceptados: 6, rechazados: 0 },
  { fecha: '2026-08-06', aceptados: 3, rechazados: 2 },
  { fecha: '2026-08-07', aceptados: 8, rechazados: 1 },
  { fecha: '2026-08-08', aceptados: 5, rechazados: 0 },
  { fecha: '2026-08-09', aceptados: 2, rechazados: 3 },
  { fecha: '2026-08-10', aceptados: 7, rechazados: 1 },
]

const distribution: StatusDistributionItem[] = [
  { estado: 'completed', count: 4, pct: '50.0' },
  { estado: 'running', count: 2, pct: '25.0' },
  { estado: 'failed', count: 1, pct: '12.5' },
  { estado: 'pending', count: 1, pct: '12.5' },
]

const recentLogs: LogEntry[] = [
  {
    id: 41,
    correlation_id: 'c-41',
    nivel_error: 'CRITICAL',
    codigo_error: 'ERR_DB_TIMEOUT',
    mensaje: 'Timeout al adquirir conexión de base de datos',
    servicio_responsable: 'ingesta',
    creado_at: '2026-08-10T10:00:00',
  },
  {
    id: 40,
    correlation_id: 'c-40',
    nivel_error: 'ERROR',
    codigo_error: 'ERR_CHECKSUM',
    mensaje: 'Checksum inválido para archivo ventas_20260810.csv',
    servicio_responsable: 'validacion',
    creado_at: '2026-08-10T09:58:00',
  },
  {
    id: 39,
    correlation_id: 'c-39',
    nivel_error: 'WARNING',
    codigo_error: 'ERR_DUPLICATE_BATCH',
    mensaje: 'Lote duplicado detectado',
    servicio_responsable: 'ingesta',
    creado_at: '2026-08-10T09:55:00',
  },
]

function StateProbe() {
  const location = useLocation()
  return <div data-testid="state-probe">{JSON.stringify(location.state)}</div>
}

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/logs" element={<StateProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
  mockedApi.dashboardMetrics.mockResolvedValue(metrics)
  mockedApi.throughput.mockResolvedValue(throughput)
  mockedApi.statusDistribution.mockResolvedValue(distribution)
  mockedApi.recentLogs.mockResolvedValue(recentLogs)
})

function kpiCard(label: string): HTMLElement {
  return screen.getByText(label).closest('.kpi-card') as HTMLElement
}

describe('Dashboard KPIs (R3)', () => {
  it('binds the 4 KPI cards to dashboard/metrics with mono values and delta tones', async () => {
    renderDashboard()
    expect(await screen.findByText('Sincronizaciones activas')).toBeInTheDocument()

    const activas = kpiCard('Sincronizaciones activas')
    expect(within(activas).getByText('1')).toHaveClass('kpi-value')
    const completadas = kpiCard('Completadas hoy')
    expect(within(completadas).getByText('3')).toHaveClass('kpi-value')
    const rechazados = kpiCard('Archivos rechazados')
    expect(within(rechazados).getByText('2')).toHaveClass('kpi-value')
    const tasa = kpiCard('Tasa de errores críticos')
    expect(within(tasa).getByText('8.2%')).toHaveClass('kpi-value')

    expect(globalCss).toMatch(/\.kpi-value\s*\{[^}]*font-family:\s*var\(--font-mono\)/)
    expect(globalCss).toMatch(/\.kpi-value\s*\{[^}]*font-size:\s*28px/)

    expect(within(activas).getByText('+1 vs ayer')).toHaveClass('kpi-delta--accent')
    expect(within(completadas).getByText('+3')).toHaveClass('kpi-delta--up')
    expect(within(rechazados).getByText('revisar')).toHaveClass('kpi-delta--down')
    expect(within(tasa).getByText('en monitoreo')).toHaveClass('kpi-delta--accent')
  })
})

describe('Throughput chart (R4)', () => {
  it('renders 7 stacked bars with weekday labels and 8x8 legend swatches', async () => {
    renderDashboard()
    const chart = await screen.findByTestId('chart')
    const data = JSON.parse(chart.dataset.data ?? '{}')
    expect(data.labels).toEqual(['L', 'M', 'X', 'J', 'V', 'S', 'D'])
    expect(data.datasets).toHaveLength(2)
    expect(data.datasets[0].label).toBe('Aceptados')
    expect(data.datasets[1].label).toBe('Rechazados')
    expect(typeof data.datasets[1].backgroundColor).toBe('string')
    expect(data.datasets[1].backgroundColor.length).toBeGreaterThan(0)
    const options = JSON.parse(chart.dataset.options ?? '{}')
    expect(options.scales.x.stacked).toBe(true)
    expect(options.scales.y.stacked).toBe(true)
    expect(screen.getAllByText('Aceptados').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Rechazados').length).toBeGreaterThan(0)
    const swatches = document.querySelectorAll('.chart-legend-swatch')
    expect(swatches).toHaveLength(2)
    expect(globalCss).toMatch(/\.chart-legend-swatch\s*\{[^}]*width:\s*8px/)
    expect(globalCss).toMatch(/\.chart-legend-swatch\s*\{[^}]*height:\s*8px/)
    expect(globalCss).toMatch(/\.throughput-chart\s*\{[^}]*height:\s*140px/)
  })
})

describe('Status distribution (R5)', () => {
  it('renders rows with mono counts and bars width proportional to pct', async () => {
    renderDashboard()
    expect(await screen.findByText('Distribución de estados')).toBeInTheDocument()
    await screen.findByText('completed')
    for (const item of distribution) {
      const row = screen.getByText(item.estado).closest('.status-row') as HTMLElement
      expect(row).not.toBeNull()
      expect(within(row).getByText(String(item.count))).toHaveClass('status-count')
      const fill = within(row).queryByRole('progressbar') as HTMLElement
      expect(fill).not.toBeNull()
      expect(fill).toHaveStyle({ width: `${item.pct}%` })
    }
  })
})

describe('Recent errors (R6)', () => {
  it('renders the 5 recent rows and navigates to /logs via Ver todos', async () => {
    const user = userEvent.setup()
    renderDashboard()
    expect(await screen.findByText('Actividad reciente de errores')).toBeInTheDocument()
    await screen.findByText('ERR_DB_TIMEOUT')
    for (const log of recentLogs) {
      expect(screen.getByText(log.codigo_error)).toBeInTheDocument()
      expect(screen.getByText(log.mensaje)).toBeInTheDocument()
    }
    await user.click(screen.getByRole('link', { name: /Ver todos/ }))
    expect(screen.getByTestId('state-probe')).toBeInTheDocument()
  })

  it('opens the log detail via row click navigating to /logs with the log id', async () => {
    const user = userEvent.setup()
    renderDashboard()
    const row = (await screen.findByText('ERR_DB_TIMEOUT')).closest('button') as HTMLElement
    await user.click(row)
    expect(screen.getByTestId('state-probe').textContent).toContain('41')
  })
})

describe('Dashboard metrics null data branch (line 72)', () => {
  it('renders nothing in KPI grid when metrics data is undefined', async () => {
    mockedApi.dashboardMetrics.mockResolvedValue(undefined as never)
    renderDashboard()
    await screen.findByText('Throughput de lotes · últimos 7 días')
    expect(document.querySelector('.kpi-card')).toBeNull()
  })
})

describe('RecentErrors empty state (line 17-18)', () => {
  it('renders Sin errores recientes when recent logs is empty', async () => {
    mockedApi.recentLogs.mockResolvedValue([])
    renderDashboard()
    expect(await screen.findByText('Sin errores recientes')).toBeInTheDocument()
  })
})

describe('Dashboard polling and error states (R7)', () => {
  it('polls the metrics query every 30 seconds', async () => {
    vi.useFakeTimers()
    renderDashboard()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(mockedApi.dashboardMetrics).toHaveBeenCalledTimes(1)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })
    expect(mockedApi.dashboardMetrics).toHaveBeenCalledTimes(2)
    vi.useRealTimers()
  })

  it('shows a retry affordance per widget on fetch failure and recovers', async () => {
    const user = userEvent.setup()
    mockedApi.dashboardMetrics.mockRejectedValueOnce(new Error('boom'))
    mockedApi.throughput.mockRejectedValueOnce(new Error('boom'))
    mockedApi.statusDistribution.mockRejectedValueOnce(new Error('boom'))
    mockedApi.recentLogs.mockRejectedValueOnce(new Error('boom'))
    renderDashboard()
    const retries = await screen.findAllByRole('button', { name: /Reintentar/ })
    expect(retries.length).toBeGreaterThanOrEqual(4)
    await user.click(retries[0])
    expect(await screen.findByText('Sincronizaciones activas')).toBeInTheDocument()
  })
})
