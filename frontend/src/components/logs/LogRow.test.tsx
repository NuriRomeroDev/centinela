import { describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LogRow from './LogRow'
import type { LogEntry } from '../../types'

const globalCss = readFileSync('src/styles/global.css', 'utf-8')
const tokensCss = readFileSync('src/styles/tokens.css', 'utf-8')

const log: LogEntry = {
  id: 7,
  correlation_id: 'c-7',
  nivel_error: 'CRITICAL',
  codigo_error: 'ERR_DB_TIMEOUT',
  mensaje: 'Timeout al adquirir conexión de base de datos',
  servicio_responsable: 'ingesta',
  creado_at: '2026-08-10T10:00:00',
}

describe('LogRow', () => {
  it('positions the row at top=idx*56 with height 56px', () => {
    render(<LogRow log={log} index={3} onSelect={vi.fn()} />)
    const row = screen.getByText('ERR_DB_TIMEOUT').closest('.log-row') as HTMLElement
    expect(row).toHaveStyle({ top: '168px', height: '56px' })
  })

  it('applies zebra backgrounds by index (odd=subRowBg, even=cardBg)', () => {
    const { rerender } = render(<LogRow log={log} index={1} onSelect={vi.fn()} />)
    expect(screen.getByText('ERR_DB_TIMEOUT').closest('.log-row')).toHaveClass('log-row--odd')
    rerender(<LogRow log={log} index={2} onSelect={vi.fn()} />)
    expect(screen.getByText('ERR_DB_TIMEOUT').closest('.log-row')).toHaveClass('log-row--even')
  })

  it('renders the mock grid columns (90 130 1fr 120 110)', () => {
    render(<LogRow log={log} index={0} onSelect={vi.fn()} />)
    expect(globalCss).toMatch(/\.log-row\s*\{[^}]*grid-template-columns:\s*90px\s+130px\s+1fr\s+120px\s+110px/)
    expect(screen.getByText('ERR_DB_TIMEOUT')).toHaveClass('log-code')
    expect(globalCss).toMatch(/\.log-code\s*\{[^}]*font-family:\s*var\(--font-mono\)/)
    expect(screen.getByText(log.mensaje)).toHaveClass('log-message')
    expect(screen.getByText('ingesta')).toBeInTheDocument()
    expect(screen.getByText('2026-08-10 10:00')).toHaveClass('log-time')
  })

  it('renders the level badge with levelVisual tokens', () => {
    render(<LogRow log={log} index={0} onSelect={vi.fn()} />)
    const badge = screen.getByText('CRITICAL')
    expect(badge).toHaveClass('level-badge')
    expect(badge).toHaveClass('level-badge--CRITICAL')
    expect(globalCss).toMatch(/\.level-badge\s*\{[^}]*font-size:\s*10\.5px/)
    expect(tokensCss).toContain('--level-crt-bg:')
    expect(tokensCss).toContain('--level-crt-text:')
    expect(globalCss).toMatch(/\.level-badge--CRITICAL\s*\{[^}]*background:\s*var\(--level-crt-bg\)/)
    expect(globalCss).toMatch(/\.level-badge--CRITICAL\s*\{[^}]*color:\s*var\(--level-crt-text\)/)
  })

  it('calls onSelect with the log id on click', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<LogRow log={log} index={0} onSelect={onSelect} />)
    await user.click(screen.getByText('ERR_DB_TIMEOUT'))
    expect(onSelect).toHaveBeenCalledWith(7)
  })
})
