import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Sincronizaciones from './Sincronizaciones'
import Remediacion from './Remediacion'
import { api } from '../api/client'
import type { Remediation, Sync } from '../types'

vi.mock('../api/client', () => ({
  api: {
    syncs: vi.fn(),
    remediations: vi.fn(),
    remediate: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

const syncs: Sync[] = [
  {
    id: '10000000-0000-4000-8000-000000000001',
    correlation_id: 'corr-1',
    estado: 'failed',
    fecha_ejecucion: '2026-08-10',
    iniciado_at: '2026-08-10T09:00:00',
    finalizado_at: null,
    usuario_origen: 'n.romero',
    archivos_resumen: '2 total · 2 rechazados',
    archivos: [
      {
        nombre_archivo: 'clientes_20260810.csv',
        tipo_archivo: 'clientes',
        checksum: 'ij90kl12',
        estado: 'rejected',
        registros_totales: 15,
      },
    ],
  },
]

const remediations: Remediation[] = [
  {
    id: 1,
    sincronizacion_id: syncs[0].id,
    correlation_id: 'corr-1',
    accion_ejecutada: 'RETRY_JOB',
    ejecutado_por: 'n.romero',
    resultado: 'success',
    notas: 'Lote reprocesado',
    ejecutada_at: '2026-08-10T09:05:00',
  },
]

function renderWithClient(ui: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.syncs.mockResolvedValue(syncs)
  mockedApi.remediations.mockResolvedValue(remediations)
})

describe('Sincronizaciones page', () => {
  it('renders the sync table from GET /syncs', async () => {
    renderWithClient(<Sincronizaciones />)
    expect(await screen.findByText('corr-1')).toBeInTheDocument()
    expect(mockedApi.syncs).toHaveBeenCalledWith(true)
  })

  it('remediates a failed sync with a Toast confirmation and refetches', async () => {
    const user = userEvent.setup()
    mockedApi.remediate.mockResolvedValue({ ...syncs[0], estado: 'running' })
    renderWithClient(<Sincronizaciones />)
    await user.click(await screen.findByRole('button', { name: /Reintentar/ }))
    expect(mockedApi.remediate).toHaveBeenCalledWith(syncs[0].id, 'RETRY_JOB')
    expect(await screen.findByText(/Reintento programado/)).toBeInTheDocument()
  })

  it('shows a Toast on remediation failure', async () => {
    const user = userEvent.setup()
    mockedApi.remediate.mockRejectedValue(new Error('boom'))
    renderWithClient(<Sincronizaciones />)
    await user.click(await screen.findByRole('button', { name: /Reintentar/ }))
    expect(await screen.findByText(/No se pudo reintentar/)).toBeInTheDocument()
  })
})

describe('Remediacion page', () => {
  it('renders the remediation history from GET /remediations', async () => {
    renderWithClient(<Remediacion />)
    expect(await screen.findByText('corr-1')).toBeInTheDocument()
    expect(mockedApi.remediations).toHaveBeenCalledTimes(1)
    expect(screen.getByText('RETRY_JOB')).toBeInTheDocument()
  })

  it('shows error state with refetch button when remediations query fails', async () => {
    const user = userEvent.setup()
    mockedApi.remediations.mockRejectedValueOnce(new Error('boom'))
    mockedApi.remediations.mockResolvedValue(remediations)
    renderWithClient(<Remediacion />)
    const retryBtn = await screen.findByRole('button', { name: /Reintentar/ })
    expect(screen.getByText(/No se pudieron cargar las remediaciones/)).toBeInTheDocument()
    await user.click(retryBtn)
    expect(await screen.findByText('corr-1')).toBeInTheDocument()
  })
})

describe('Sincronizaciones error state', () => {
  it('shows error state with refetch button when syncs query fails', async () => {
    const user = userEvent.setup()
    mockedApi.syncs.mockRejectedValueOnce(new Error('boom'))
    mockedApi.syncs.mockResolvedValue(syncs)
    renderWithClient(<Sincronizaciones />)
    const retryBtn = await screen.findByRole('button', { name: /Reintentar/ })
    expect(screen.getByText(/No se pudieron cargar las sincronizaciones/)).toBeInTheDocument()
    await user.click(retryBtn)
    expect(await screen.findByText('corr-1')).toBeInTheDocument()
  })
})
