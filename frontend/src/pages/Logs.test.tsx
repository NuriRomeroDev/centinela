import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Logs from './Logs'
import { api } from '../api/client'
import type { LogDetail, LogEntry, Page } from '../types'

vi.mock('primereact/virtualscroller', () => ({
  VirtualScroller: ({
    items,
    itemTemplate,
  }: {
    items: LogEntry[]
    itemTemplate: (item: LogEntry, options: { index: number }) => React.ReactNode
  }) => <div>{items.map((item, index) => itemTemplate(item, { index }))}</div>,
}))

vi.mock('../api/client', () => ({
  api: {
    logs: vi.fn(),
    logDetail: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

const pageOne: Page<LogEntry> = {
  items: Array.from({ length: 25 }, (_, index) => ({
    id: index + 1,
    correlation_id: `c-${index + 1}`,
    nivel_error: 'ERROR' as const,
    codigo_error: `ERR_${index}`,
    mensaje: `Mensaje ${index}`,
    servicio_responsable: 'ingesta',
    creado_at: '2026-08-10T10:00:00',
  })),
  total: 38,
  next_cursor: 25,
  page_size: 25,
  page: 1,
}

const filtered: Page<LogEntry> = {
  items: [pageOne.items[6]],
  total: 3,
  next_cursor: null,
  page_size: 25,
  page: 1,
}

const detail: LogDetail = {
  ...pageOne.items[0],
  stack_trace: 'Traceback (most recent call last):\npool.acquire(timeout=5.0)',
}

function renderLogs(initialState?: { openLogId?: number }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[{ pathname: '/logs', state: initialState }]}>
        <Routes>
          <Route path="/logs" element={<Logs />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
  mockedApi.logs.mockResolvedValue(pageOne)
  mockedApi.logDetail.mockResolvedValue(detail)
})

describe('Logs screen', () => {
  it('fetches page 1 on mount and renders the footer with server totals', async () => {
    renderLogs()
    expect(await screen.findByText('ERR_0')).toBeInTheDocument()
    expect(mockedApi.logs).toHaveBeenCalledWith({ search: undefined, page: 1, page_size: 25 })
    expect(document.querySelector('.logs-footer-count')?.textContent).toMatch(
      /Mostrando 1[-–]25 de 38/,
    )
  })

  it('debounces the search 300ms and fires exactly one request per burst', async () => {
    vi.useFakeTimers()
    renderLogs()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(mockedApi.logs).toHaveBeenCalledTimes(1)
    const input = screen.getByLabelText('Buscar logs')
    fireEvent.change(input, { target: { value: 'E' } })
    fireEvent.change(input, { target: { value: 'ER' } })
    fireEvent.change(input, { target: { value: 'ERR' } })
    expect(screen.getByText('buscando…')).toBeInTheDocument()
    expect(mockedApi.logs).toHaveBeenCalledTimes(1)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300)
    })
    expect(mockedApi.logs).toHaveBeenCalledTimes(2)
    expect(mockedApi.logs).toHaveBeenLastCalledWith({
      search: 'ERR',
      page: 1,
      page_size: 25,
    })
    vi.useRealTimers()
  })

  it('refetches page 1 with the server-filtered total after a search', async () => {
    mockedApi.logs.mockResolvedValueOnce(pageOne)
    mockedApi.logs.mockResolvedValueOnce(filtered)
    renderLogs()
    const input = await screen.findByLabelText('Buscar logs')
    await userEvent.type(input, 'DB_TIMEOUT')
    await waitFor(() => expect(mockedApi.logs).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: 'DB_TIMEOUT' }),
    ))
    expect(await screen.findByText('ERR_6')).toBeInTheDocument()
    expect(document.querySelector('.logs-footer-count')?.textContent).toMatch(
      /Mostrando 1[-–]3 de 3/,
    )
  })

  it('opens the stack-trace modal fetching the detail on row click', async () => {
    const user = userEvent.setup()
    renderLogs()
    await user.click(await screen.findByText('ERR_0'))
    expect(mockedApi.logDetail).toHaveBeenCalledWith(1)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/pool\.acquire\(timeout=5\.0\)/)).toBeInTheDocument()
  })

  it('opens the modal directly from the route state (recent-errors navigation)', async () => {
    renderLogs({ openLogId: 1 })
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getAllByText('ERR_0').length).toBeGreaterThanOrEqual(2)
  })

  it('closes the modal via the close button (covers close() in useOpenLogIdFromRoute)', async () => {
    const user = userEvent.setup()
    renderLogs({ openLogId: 1 })
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    await user.click(document.querySelector('.stack-modal-close') as HTMLElement)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('shows error state with refetch button when logs query fails', async () => {
    const user = userEvent.setup()
    mockedApi.logs.mockRejectedValueOnce(new Error('boom'))
    mockedApi.logs.mockResolvedValue(pageOne)
    renderLogs()
    const retryBtn = await screen.findByRole('button', { name: /Reintentar/ })
    expect(screen.getByText(/No se pudieron cargar los logs/)).toBeInTheDocument()
    await user.click(retryBtn)
    expect(await screen.findByText('ERR_0')).toBeInTheDocument()
  })

  it('navigates pages via the footer squares', async () => {
    mockedApi.logs.mockResolvedValueOnce(pageOne)
    mockedApi.logs.mockResolvedValueOnce({
      ...pageOne,
      items: pageOne.items.map((item) => ({ ...item, id: item.id + 25 })),
      page: 2,
    })
    const user = userEvent.setup()
    renderLogs()
    await user.click(await screen.findByRole('button', { name: '2' }))
    await waitFor(() =>
      expect(mockedApi.logs).toHaveBeenLastCalledWith({
        search: undefined,
        page: 2,
        page_size: 25,
      }),
    )
  })
})
