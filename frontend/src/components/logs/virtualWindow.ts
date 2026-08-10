export const ROW_H = 56
export const VIEWPORT_H = 480
export const OVERSCAN = 4

export function visibleCount(): number {
  return Math.ceil(VIEWPORT_H / ROW_H)
}

export function getWindow(
  scrollTop: number,
  total: number,
): { start: number; end: number } {
  if (total === 0) return { start: 0, end: -1 }
  const first = Math.floor(scrollTop / ROW_H)
  if (first >= total) {
    return {
      start: Math.max(0, total - visibleCount() - OVERSCAN),
      end: total - 1,
    }
  }
  const start = Math.max(0, first - OVERSCAN)
  const end = Math.min(total - 1, first + visibleCount())
  return { start, end }
}

export function spacerHeight(total: number): number {
  return total * ROW_H
}
