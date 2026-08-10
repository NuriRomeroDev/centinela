import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, renderHook, screen } from '@testing-library/react'
import { useEffect, useRef, useState } from 'react'
import fs from 'node:fs'
import { useDebounce } from './useDebounce'

const DEBOUNCE_MS = 300
const advance = (ms: number) => act(() => vi.advanceTimersByTime(ms))

function SearchProbe() {
  const [raw, setRaw] = useState('')
  const [, debounced] = useDebounce(raw, DEBOUNCE_MS)
  return (
    <>
      <input aria-label="buscar" value={raw} onChange={(event) => setRaw(event.target.value)} />
      <span>{raw !== debounced ? 'buscando…' : 'sin cambios'}</span>
    </>
  )
}

function RequestLogger({ value, onRequest }: { value: string; onRequest: (value: string) => void }) {
  const [, debounced] = useDebounce(value, DEBOUNCE_MS)
  const previous = useRef(debounced)
  useEffect(() => {
    if (previous.current !== debounced) onRequest(debounced)
    previous.current = debounced
  }, [debounced, onRequest])
  return null
}

describe('useDebounce', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts settled, mirrors raw immediately and settles 300ms after a change', () => {
    vi.useFakeTimers()
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, DEBOUNCE_MS), {
      initialProps: { value: 'ERR' },
    })
    expect(result.current[0]).toBe('ERR')
    expect(result.current[1]).toBe('ERR')
    rerender({ value: 'ERR_TIMEOUT' })
    expect(result.current[0]).toBe('ERR_TIMEOUT')
    expect(result.current[1]).toBe('ERR')
    advance(DEBOUNCE_MS)
    expect(result.current[1]).toBe('ERR_TIMEOUT')
  })

  it('fires exactly one request for a burst of five keystrokes 50ms apart', () => {
    vi.useFakeTimers()
    const onRequest = vi.fn()
    const { rerender } = render(<RequestLogger value="" onRequest={onRequest} />)
    const burst = ['E', 'ER', 'ERR', 'ERR_', 'ERR_T']
    burst.forEach((value) => {
      act(() => vi.advanceTimersByTime(50))
      rerender(<RequestLogger value={value} onRequest={onRequest} />)
    })
    act(() => vi.advanceTimersByTime(DEBOUNCE_MS))
    expect(onRequest).toHaveBeenCalledTimes(1)
    expect(onRequest).toHaveBeenCalledWith('ERR_T')
    act(() => vi.advanceTimersByTime(2000))
    expect(onRequest).toHaveBeenCalledTimes(1)
  })

  it('fires one request per distinct burst after each settle', () => {
    vi.useFakeTimers()
    const onRequest = vi.fn()
    const { rerender } = render(<RequestLogger value="" onRequest={onRequest} />)
    rerender(<RequestLogger value="DB" onRequest={onRequest} />)
    act(() => vi.advanceTimersByTime(DEBOUNCE_MS))
    expect(onRequest).toHaveBeenCalledTimes(1)
    expect(onRequest).toHaveBeenLastCalledWith('DB')
    rerender(<RequestLogger value="NET" onRequest={onRequest} />)
    act(() => vi.advanceTimersByTime(DEBOUNCE_MS))
    expect(onRequest).toHaveBeenCalledTimes(2)
    expect(onRequest).toHaveBeenLastCalledWith('NET')
  })

  it('shows the pending indicator while raw differs from debounced', () => {
    vi.useFakeTimers()
    render(<SearchProbe />)
    const input = screen.getByLabelText('buscar')
    fireEvent.change(input, { target: { value: 'ERR' } })
    expect(screen.getByText('buscando…')).toBeInTheDocument()
    advance(100)
    expect(screen.getByText('buscando…')).toBeInTheDocument()
    advance(DEBOUNCE_MS)
    expect(screen.getByText('sin cambios')).toBeInTheDocument()
  })

  it('clears the pending timer on unmount so no request fires after unmount', () => {
    vi.useFakeTimers()
    const onRequest = vi.fn()
    const { unmount } = render(<RequestLogger value="PENDIENTE" onRequest={onRequest} />)
    unmount()
    act(() => vi.advanceTimersByTime(DEBOUNCE_MS * 3))
    expect(onRequest).not.toHaveBeenCalled()
  })

  it('declares no external debounce library', () => {
    const pkg = JSON.parse(fs.readFileSync('package.json', 'utf-8')) as Record<string, Record<string, string>>
    const dependencies = { ...pkg.dependencies, ...pkg.devDependencies }
    expect(dependencies.lodash).toBeUndefined()
    expect(dependencies.underscore).toBeUndefined()
  })
})
