import { describe, expect, it } from 'vitest'
import { getWindow, ROW_H, VIEWPORT_H, OVERSCAN, spacerHeight, visibleCount } from './virtualWindow'

describe('virtualWindow math', () => {
  it('exports the mock geometry constants', () => {
    expect(ROW_H).toBe(56)
    expect(VIEWPORT_H).toBe(480)
    expect(OVERSCAN).toBe(4)
    expect(visibleCount()).toBe(Math.ceil(480 / 56))
  })

  it('starts at offset 0 with the first window', () => {
    expect(getWindow(0, 38)).toEqual({ start: 0, end: 9 })
  })

  it('keeps only viewport + overscan rows in the DOM at offset 1000', () => {
    const windowed = getWindow(1000, 38)
    expect(windowed.start).toBe(Math.floor(1000 / 56) - 4)
    expect(windowed.start).toBe(13)
    expect(windowed.end).toBe(Math.floor(1000 / 56) + visibleCount())
    expect(windowed.end).toBe(26)
    expect(windowed.end - windowed.start + 1).toBeLessThanOrEqual(38)
  })

  it('clamps to the last window at deep offsets', () => {
    expect(getWindow(10000, 38)).toEqual({ start: 25, end: 37 })
  })

  it('handles empty lists', () => {
    expect(getWindow(0, 0)).toEqual({ start: 0, end: -1 })
  })
})

describe('spacerHeight', () => {
  it('returns total * ROW_H', () => {
    expect(spacerHeight(38)).toBe(38 * 56)
    expect(spacerHeight(0)).toBe(0)
  })
})
