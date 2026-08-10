import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './client'

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  fetchMock.mockReset()
})

describe('ApiError', () => {
  it('carries status and message', () => {
    const err = new ApiError(422, 'bad')
    expect(err.status).toBe(422)
    expect(err.message).toBe('bad')
  })
})

describe('request() — network error branch (client.ts:28-29)', () => {
  it('throws ApiError(0) when fetch rejects', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(api.dashboardMetrics()).rejects.toMatchObject({ status: 0 })
  })
})

describe('request() — non-ok response branch (client.ts:31-35)', () => {
  it('throws ApiError with server status on non-2xx with detail', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 }),
    )
    await expect(api.dashboardMetrics()).rejects.toMatchObject({
      status: 404,
      message: 'Not found',
    })
  })

  it('falls back to statusText when body has no detail', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({}), {
        status: 500,
        statusText: 'Internal Server Error',
      }),
    )
    await expect(api.dashboardMetrics()).rejects.toMatchObject({
      status: 500,
      message: 'Internal Server Error',
    })
  })

  it('falls back to statusText when body is not JSON', async () => {
    fetchMock.mockResolvedValue(
      new Response('plain text error', {
        status: 503,
        statusText: 'Service Unavailable',
      }),
    )
    await expect(api.dashboardMetrics()).rejects.toMatchObject({
      status: 503,
      message: 'Service Unavailable',
    })
  })
})

describe('api.logs() URL building (client.ts:46-52)', () => {
  it('builds query string omitting undefined values', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], total: 0, next_cursor: null, page_size: 25, page: 1 }),
      ),
    )
    await api.logs({ search: 'err', page: 1, page_size: 25, cursor: undefined })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('search=err')
    expect(url).toContain('page=1')
    expect(url).not.toContain('cursor')
  })

  it('omits the query string entirely when all values are undefined', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], total: 0, next_cursor: null, page_size: 25, page: 1 }),
      ),
    )
    await api.logs({ search: undefined, page: undefined })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toBe('/api/v1/logs')
  })
})

describe('api.syncs() (client.ts:56)', () => {
  it('calls /syncs with include_files param', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify([])))
    await api.syncs(false)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/syncs?include_files=false')
  })
})

describe('api.remediate() (client.ts:59-63)', () => {
  it('POSTs to /syncs/:id/remediate with JSON body', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ id: 'abc', estado: 'running' })),
    )
    await api.remediate('abc', 'RETRY_JOB')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/syncs/abc/remediate')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ accion: 'RETRY_JOB' })
  })
})
