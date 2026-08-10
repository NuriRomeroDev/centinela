import { describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SyncTable from './SyncTable'
import type { Sync } from '../../types'

const globalCss = readFileSync('src/styles/global.css', 'utf-8')
const tokensCss = readFileSync('src/styles/tokens.css', 'utf-8')

const syncs: Sync[] = [
  {
    id: '10000000-0000-4000-8000-000000000001',
    correlation_id: 'corr-1',
    estado: 'completed',
    fecha_ejecucion: '2026-08-10',
    iniciado_at: '2026-08-10T09:00:00',
    finalizado_at: '2026-08-10T09:01:00',
    usuario_origen: 'j.medina',
    archivos_resumen: '3 total · 0 rechazados',
    archivos: [
      {
        nombre_archivo: 'ventas_20260810.csv',
        tipo_archivo: 'ventas',
        checksum: 'ab12cd34',
        estado: 'accepted',
        registros_totales: 1240,
      },
      {
        nombre_archivo: 'inventario_20260810.csv',
        tipo_archivo: 'inventario',
        checksum: 'ef56gh78',
        estado: 'accepted',
        registros_totales: 320,
      },
    ],
  },
  {
    id: '20000000-0000-4000-8000-000000000002',
    correlation_id: 'corr-2',
    estado: 'failed',
    fecha_ejecucion: '2026-08-10',
    iniciado_at: '2026-08-10T08:30:00',
    finalizado_at: null,
    usuario_origen: 'm.ruiz',
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

describe('SyncTable', () => {
  it('renders the mock columns with badges and server-side archivos_resumen', () => {
    render(<SyncTable syncs={syncs} onRemediate={vi.fn()} />)
    expect(screen.getByText('Correlation ID')).toBeInTheDocument()
    expect(screen.getByText('Estado')).toBeInTheDocument()
    expect(screen.getByText('Fecha')).toBeInTheDocument()
    expect(screen.getByText('Iniciado')).toBeInTheDocument()
    expect(screen.getByText('Finalizado')).toBeInTheDocument()
    expect(screen.getByText('Usuario')).toBeInTheDocument()
    expect(screen.getByText('Archivos')).toBeInTheDocument()
    expect(screen.getByText('corr-1')).toBeInTheDocument()
    expect(screen.getByText('3 total · 0 rechazados')).toBeInTheDocument()
    const completedBadge = screen.getByText('completed')
    expect(completedBadge).toHaveClass('status-badge--completed')
    expect(tokensCss).toContain('--status-completed-bg:')
  })

  it('expands a row revealing the archivos grid (tipo, checksum, estado, registros)', async () => {
    const user = userEvent.setup()
    render(<SyncTable syncs={syncs} onRemediate={vi.fn()} />)
    const togglers = screen.getAllByRole('button')
    await user.click(togglers[0])
    expect(screen.getByText('Archivos procesados')).toBeInTheDocument()
    expect(screen.getByText('ventas_20260810.csv')).toBeInTheDocument()
    expect(screen.getByText('ventas')).toHaveClass('tipo-badge')
    expect(screen.getByText('ab12cd34')).toBeInTheDocument()
    const accepted = screen.getAllByText('accepted')
    expect(accepted.length).toBeGreaterThanOrEqual(2)
    expect(accepted[0]).toHaveClass('status-badge--accepted')
    expect(screen.getByText(/1[.,]?240/)).toBeInTheDocument()
    expect(globalCss).toMatch(/\.sync-chevron\s*\{[^}]*transition:\s*transform\s+0\.15s/)
  })

  it('offers a Reintentar action only on failed/rejected rows', async () => {
    const user = userEvent.setup()
    const onRemediate = vi.fn()
    render(<SyncTable syncs={syncs} onRemediate={onRemediate} />)
    const retries = screen.getAllByRole('button', { name: /Reintentar/ })
    expect(retries).toHaveLength(1)
    const failedRow = screen.getByText('corr-2').closest('tr') as HTMLElement
    expect(within(failedRow).getByRole('button', { name: /Reintentar/ })).toBeInTheDocument()
    await user.click(retries[0])
    expect(onRemediate).toHaveBeenCalledWith(syncs[1].id, 'RETRY_JOB')
  })
})
