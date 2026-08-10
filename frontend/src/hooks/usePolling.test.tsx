import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { POLLING_INTERVAL_MS, usePolling } from './usePolling'

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return Wrapper
}

describe('usePolling', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('fetches immediately and refetches every 30 seconds', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn().mockResolvedValue({ ok: true })
    const { result } = renderHook(() => usePolling(['metrics'], fetcher), { wrapper: createWrapper() })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(result.current.data).toEqual({ ok: true })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLLING_INTERVAL_MS)
    })
    expect(fetcher).toHaveBeenCalledTimes(2)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLLING_INTERVAL_MS)
    })
    expect(fetcher).toHaveBeenCalledTimes(3)
  })

  it('refetches when the window regains focus', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn().mockResolvedValue(1)
    renderHook(() => usePolling(['logs'], fetcher), { wrapper: createWrapper() })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(fetcher).toHaveBeenCalledTimes(1)
    await act(async () => {
      window.dispatchEvent(new Event('visibilitychange'))
    })
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('stops polling when the query is removed', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn().mockResolvedValue(0)
    const wrapper = createWrapper()
    const { unmount } = renderHook(() => usePolling(['syncs'], fetcher), { wrapper })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    unmount()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLLING_INTERVAL_MS * 3)
    })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
})
