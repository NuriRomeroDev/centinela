import { test, expect } from '@playwright/test'

const API_BASE = process.env.API_BASE ?? 'http://localhost:8000'

test.describe('Virtual List DOM efficiency', () => {
  test.beforeEach(async ({ page }) => {
    await page.route(`${API_BASE}/api/v1/logs**`, (route) => {
      const items = Array.from({ length: 38 }, (_, i) => ({
        id: i + 1,
        correlation_id: `c-${i + 1}`,
        nivel_error: 'ERROR',
        codigo_error: `ERR_${i}`,
        mensaje: `Mensaje ${i}`,
        servicio_responsable: 'ingesta',
        creado_at: '2026-08-10T10:00:00',
      }))
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items,
          total: 38,
          next_cursor: null,
          page_size: 25,
          page: 1,
        }),
      })
    })
  })

  test('renders only visible rows — not all 38 at once (DOM virtualization)', async ({ page }) => {
    await page.goto('http://localhost:5173/logs')

    await page.waitForSelector('.log-row')

    const domRowCount = await page.locator('.log-row').count()

    // VirtualScroller with viewport 480px / itemSize 56px ≈ 9 visible + 4 overscan each side ≈ 17 max
    // Allows up to 20 to account for PrimeReact internal buffers, never all 38
    expect(domRowCount).toBeGreaterThan(0)
    expect(domRowCount).toBeLessThan(25)
  })

  test('DOM row count stays bounded after scrolling halfway down', async ({ page }) => {
    await page.goto('http://localhost:5173/logs')

    await page.waitForSelector('.log-row')

    const virtualList = page.locator('.p-virtualscroller')
    await virtualList.evaluate((el) => {
      el.scrollTop = 1000
    })

    await page.waitForTimeout(150)

    const domRowCount = await page.locator('.log-row').count()
    expect(domRowCount).toBeLessThan(25)
  })
})
