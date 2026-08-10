import { afterEach, describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { THEME_STORAGE_KEY } from '../app/theme'
import { useTheme } from './useTheme'

describe('useTheme', () => {
  afterEach(() => {
    window.localStorage.clear()
    delete document.documentElement.dataset.theme
  })

  it('applies the default palette A to the document root', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current[0]).toBe('a')
    expect(document.documentElement.dataset.theme).toBe('a')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('a')
  })

  it('switches to palette B and persists it', () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current[1]('b'))
    expect(result.current[0]).toBe('b')
    expect(document.documentElement.dataset.theme).toBe('b')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('b')
  })

  it('reads the persisted theme on mount', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'b')
    const { result } = renderHook(() => useTheme())
    expect(result.current[0]).toBe('b')
    expect(document.documentElement.dataset.theme).toBe('b')
  })

  it('rejects persisted values outside the palette', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'z')
    const { result } = renderHook(() => useTheme())
    expect(result.current[0]).toBe('a')
  })
})
