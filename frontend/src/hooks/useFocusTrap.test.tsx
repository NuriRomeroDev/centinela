import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, renderHook } from '@testing-library/react'
import { createRef, type RefObject } from 'react'
import { useFocusTrap } from './useFocusTrap'

describe('useFocusTrap', () => {
  it('adds the keydown listener on open and removes it on close', () => {
    const onEscape = vi.fn()
    const ref = createRef<HTMLElement>()
    const { rerender, unmount } = renderHook(
      ({ open }) => useFocusTrap(open, ref as RefObject<HTMLElement | null>, onEscape),
      { initialProps: { open: false } },
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onEscape).not.toHaveBeenCalled()
    rerender({ open: true })
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onEscape).toHaveBeenCalledTimes(1)
    rerender({ open: false })
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onEscape).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('focuses the first focusable element and restores the saved element on close', () => {
    const saved = document.createElement('button')
    document.body.appendChild(saved)
    saved.focus()

    const dialog = document.createElement('div')
    const first = document.createElement('button')
    const last = document.createElement('button')
    dialog.appendChild(first)
    dialog.appendChild(last)
    document.body.appendChild(dialog)

    const ref = createRef<HTMLElement>()
    ;(ref as { current: HTMLElement | null }).current = dialog
    const onEscape = vi.fn()

    const { rerender } = renderHook(
      ({ open }) => useFocusTrap(open, ref as RefObject<HTMLElement | null>, onEscape),
      { initialProps: { open: false } },
    )
    rerender({ open: true })
    expect(document.activeElement).toBe(first)

    rerender({ open: false })
    expect(document.activeElement).toBe(saved)
    document.body.removeChild(dialog)
    document.body.removeChild(saved)
  })

  it('does not steal focus when the dialog has no focusable elements', () => {
    const dialog = document.createElement('div')
    document.body.appendChild(dialog)
    const ref = createRef<HTMLElement>()
    ;(ref as { current: HTMLElement | null }).current = dialog
    const onEscape = vi.fn()
    const { rerender } = renderHook(
      ({ open }) => useFocusTrap(open, ref as RefObject<HTMLElement | null>, onEscape),
      { initialProps: { open: false } },
    )
    expect(() => rerender({ open: true })).not.toThrow()
    document.body.removeChild(dialog)
  })

  it('is usable under act() with async transitions', async () => {
    const onEscape = vi.fn()
    const ref = createRef<HTMLElement>()
    const dialog = document.createElement('div')
    dialog.appendChild(document.createElement('button'))
    document.body.appendChild(dialog)
    ;(ref as { current: HTMLElement | null }).current = dialog
    const { rerender } = renderHook(
      ({ open }) => useFocusTrap(open, ref as RefObject<HTMLElement | null>, onEscape),
      { initialProps: { open: false } },
    )
    await act(async () => {
      rerender({ open: true })
    })
    expect(onEscape).not.toHaveBeenCalled()
    document.body.removeChild(dialog)
  })
})
