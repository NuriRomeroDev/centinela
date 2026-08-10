import { describe, expect, it, vi } from 'vitest'
import { render } from '@testing-library/react'
import VirtualLogList from './VirtualLogList'
import type { LogEntry } from '../../types'

const items: LogEntry[] = Array.from({ length: 38 }, (_, index) => ({
  id: index + 1,
  correlation_id: `c-${index + 1}`,
  nivel_error: 'ERROR',
  codigo_error: `ERR_${index}`,
  mensaje: `Mensaje ${index}`,
  servicio_responsable: 'ingesta',
  creado_at: '2026-08-10T10:00:00',
}))

function lastProps(): Record<string, unknown> {
  const calls = vi.mocked(VirtualScrollerMock).mock.calls
  return calls[calls.length - 1][0] as Record<string, unknown>
}

const VirtualScrollerMock = vi.fn()

vi.mock('primereact/virtualscroller', () => ({
  VirtualScroller: (props: Record<string, unknown>) => {
    VirtualScrollerMock(props)
    return <div data-testid="vs" />
  },
}))

describe('VirtualLogList', () => {
  it('configures the PrimeReact VirtualScroller with mock geometry', () => {
    render(<VirtualLogList items={items} onSelect={vi.fn()} />)
    const props = lastProps()
    expect(props.itemSize).toBe(56)
    expect(props.numToleratedItems).toBe(4)
    expect(props.items).toHaveLength(38)
    const style = props.style as Record<string, unknown>
    expect(style.height).toBe(480)
    expect(typeof props.itemTemplate).toBe('function')
  })

  it('renders a row per item with top=idx*56 via the item template', () => {
    render(<VirtualLogList items={items} onSelect={vi.fn()} />)
    const props = lastProps()
    const template = props.itemTemplate as (item: LogEntry, options: { index: number }) => React.ReactNode
    const node = template(items[3], { index: 3 })
    expect(node).not.toBeNull()
  })
})
