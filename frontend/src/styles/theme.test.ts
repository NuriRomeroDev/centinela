import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'

const tokens = readFileSync('src/styles/tokens.css', 'utf-8')
const root = tokens.slice(0, tokens.indexOf(":root[data-theme='b']"))
const dark = tokens.slice(tokens.indexOf(":root[data-theme='b']"))

const BADGE_TOKENS = [
  '--level-warn-bg',
  '--level-warn-text',
  '--level-err-bg',
  '--level-err-text',
  '--level-crt-bg',
  '--level-crt-text',
  '--status-pending-bg',
  '--status-pending-text',
  '--status-running-bg',
  '--status-running-text',
  '--status-completed-bg',
  '--status-completed-text',
  '--status-failed-bg',
  '--status-failed-text',
  '--status-rejected-bg',
  '--status-rejected-text',
]

describe('D-4 badge tokens', () => {
  it('defines every statusVisual/levelVisual token in palette A and palette B', () => {
    for (const token of BADGE_TOKENS) {
      expect(root, `${token} missing in palette A`).toContain(`${token}:`)
      expect(dark, `${token} missing in palette B`).toContain(`${token}:`)
    }
  })

  it('uses light-on-dark chips (near-white text, darker saturated bg) in palette B', () => {
    for (const token of ['--level-warn-text', '--level-crt-text']) {
      const match = dark.match(new RegExp(`${token}:\\s*oklch\\(([\\d.]+)%`))
      expect(match, `${token} parse`).not.toBeNull()
      expect(Number(match?.[1])).toBeGreaterThanOrEqual(90)
    }
    for (const token of ['--level-warn-bg', '--level-crt-bg']) {
      const match = dark.match(new RegExp(`${token}:\\s*oklch\\(([\\d.]+)%`))
      expect(Number(match?.[1])).toBeLessThanOrEqual(45)
    }
  })
})
