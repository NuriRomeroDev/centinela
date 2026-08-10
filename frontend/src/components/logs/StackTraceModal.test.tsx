import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import StackTraceModal from './StackTraceModal'
import type { LogDetail } from '../../types'

const detail: LogDetail = {
  id: 41,
  correlation_id: 'c-41',
  nivel_error: 'CRITICAL',
  codigo_error: 'ERR_DB_TIMEOUT',
  mensaje: 'Timeout al adquirir conexión de base de datos',
  servicio_responsable: 'ingesta',
  creado_at: '2026-08-10T10:00:00',
  stack_trace: 'Traceback (most recent call last):\n  File "app/db/retry.py", line 42\npool.acquire(timeout=5.0)',
}

function Harness() {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        abrir
      </button>
      {open && <StackTraceModal log={detail} onClose={() => setOpen(false)} />}
    </div>
  )
}

describe('StackTraceModal', () => {
  it('renders role=dialog aria-modal with badge, code, meta and stack trace', () => {
    render(<StackTraceModal log={detail} onClose={vi.fn()} />)
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByText('CRITICAL')).toHaveClass('level-badge--CRITICAL')
    expect(screen.getByText('ERR_DB_TIMEOUT')).toBeInTheDocument()
    expect(screen.getByText(detail.mensaje)).toBeInTheDocument()
    expect(screen.getByText('c-41')).toBeInTheDocument()
    expect(screen.getByText('ingesta')).toBeInTheDocument()
    expect(screen.getByText('2026-08-10T10:00:00')).toBeInTheDocument()
    expect(screen.getByText(/pool\.acquire\(timeout=5\.0\)/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cerrar (Esc)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reintentar job' })).toBeInTheDocument()
  })

  it('moves focus to the first focusable on open and restores it on close', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const trigger = screen.getByRole('button', { name: 'abrir' })
    await user.click(trigger)
    const dialog = screen.getByRole('dialog')
    const firstFocusable = dialog.querySelectorAll<HTMLElement>('button')[0]
    expect(document.activeElement).toBe(firstFocusable)
    await user.click(screen.getByRole('button', { name: 'Reintentar job' }))
    expect(document.activeElement).toBe(trigger)
  })

  it('closes on Escape and restores focus to the trigger', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const trigger = screen.getByRole('button', { name: 'abrir' })
    await user.click(trigger)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(trigger)
  })

  it('closes via the Cerrar and Reintentar job buttons', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<StackTraceModal log={detail} onClose={onClose} />)
    await user.click(screen.getByRole('button', { name: 'Reintentar job' }))
    expect(onClose).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: 'Cerrar (Esc)' }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('closes on overlay mousedown but not on dialog mousedown', () => {
    const onClose = vi.fn()
    render(<StackTraceModal log={detail} onClose={onClose} />)
    const dialog = screen.getByRole('dialog')
    fireEvent.mouseDown(dialog)
    expect(onClose).not.toHaveBeenCalled()
    fireEvent.mouseDown(document.querySelector('.stack-modal-mask') as HTMLElement)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('wraps Tab from the last focusable to the first', async () => {
    const user = userEvent.setup()
    render(<StackTraceModal log={detail} onClose={vi.fn()} />)
    const dialog = screen.getByRole('dialog')
    const focusables = dialog.querySelectorAll<HTMLElement>('button')
    expect(focusables.length).toBeGreaterThanOrEqual(3)
    focusables[focusables.length - 1].focus()
    await user.tab()
    expect(document.activeElement).toBe(focusables[0])
  })

  it('wraps Shift+Tab from the first focusable to the last', async () => {
    const user = userEvent.setup()
    render(<StackTraceModal log={detail} onClose={vi.fn()} />)
    const dialog = screen.getByRole('dialog')
    const focusables = dialog.querySelectorAll<HTMLElement>('button')
    focusables[0].focus()
    await user.tab({ shift: true })
    expect(document.activeElement).toBe(focusables[focusables.length - 1])
  })
})
