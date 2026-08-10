import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import RemediationTable from './RemediationTable'
import type { Remediation } from '../../types'

const remediations: Remediation[] = [
  {
    id: 1,
    sincronizacion_id: '10000000-0000-4000-8000-000000000001',
    correlation_id: 'corr-1',
    accion_ejecutada: 'RETRY_JOB',
    ejecutado_por: 'j.medina',
    resultado: 'success',
    notas: 'Lote reprocesado sin errores',
    ejecutada_at: '2026-08-10T09:05:00',
  },
  {
    id: 2,
    sincronizacion_id: '20000000-0000-4000-8000-000000000002',
    correlation_id: 'corr-2',
    accion_ejecutada: 'FORCE_SKIP_VALIDATION',
    ejecutado_por: 'svc.autoheal',
    resultado: 'failed',
    notas: null,
    ejecutada_at: '2026-08-10T08:31:00',
  },
]

describe('RemediationTable', () => {
  it('renders the mock columns with action pill and resultado badge', () => {
    render(<RemediationTable remediations={remediations} />)
    expect(screen.getByText('Fecha')).toBeInTheDocument()
    expect(screen.getByText('Sincronización')).toBeInTheDocument()
    expect(screen.getByText('Acción')).toBeInTheDocument()
    expect(screen.getByText('Ejecutado por')).toBeInTheDocument()
    expect(screen.getByText('Resultado')).toBeInTheDocument()
    expect(screen.getByText('Notas')).toBeInTheDocument()

    expect(screen.getByText('corr-1')).toBeInTheDocument()
    expect(screen.getByText('RETRY_JOB')).toHaveClass('action-pill')
    expect(screen.getByText('success')).toHaveClass('status-badge--success')
    expect(screen.getByText('failed')).toHaveClass('status-badge--failed')
    expect(screen.getByText('Lote reprocesado sin errores')).toBeInTheDocument()
    expect(screen.getByText('svc.autoheal')).toBeInTheDocument()
    expect(screen.getByText('2026-08-10 09:05')).toBeInTheDocument()
  })

  it('renders an empty state when there is no history', () => {
    render(<RemediationTable remediations={[]} />)
    expect(screen.getByText('Sin acciones de remediación')).toBeInTheDocument()
  })
})
