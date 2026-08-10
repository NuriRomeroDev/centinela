import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import VirtualLogList from '../components/logs/VirtualLogList'
import LogsFooter from '../components/logs/LogsFooter'
import StackTraceModal from '../components/logs/StackTraceModal'
import { useDebounce } from '../hooks/useDebounce'
import { useLogDetail, useLogs } from '../api/queries'

const PAGE_SIZE = 25

function useOpenLogIdFromRoute() {
  const location = useLocation()
  const [openLogId, setOpenLogId] = useState<number | null>(
    (location.state as { openLogId?: number } | null)?.openLogId ?? null,
  )
  const navigate = useNavigate()
  const close = () => {
    setOpenLogId(null)
    navigate(location.pathname, { replace: true })
  }
  return { openLogId, setOpenLogId, close }
}

export default function Logs() {
  const [searchRaw, setSearchRaw] = useState('')
  const [, search] = useDebounce(searchRaw, 300)
  const [page, setPage] = useState(1)
  const { openLogId, setOpenLogId, close } = useOpenLogIdFromRoute()

  const logsQuery = useLogs(search, page, PAGE_SIZE)
  const detailQuery = useLogDetail(openLogId)

  useEffect(() => {
    setPage(1)
  }, [search])

  const items = logsQuery.data?.items ?? []
  const total = logsQuery.data?.total ?? 0
  const isDebouncing = searchRaw !== search

  return (
    <section className="page">
      <div className="logs-toolbar">
        <div className="logs-search">
          <span className="logs-search-icon">⌕</span>
          <input
            className="p-inputtext"
            value={searchRaw}
            onChange={(event) => setSearchRaw(event.target.value)}
            placeholder="Buscar por mensaje, código o servicio…"
            aria-label="Buscar logs"
          />
          {searchRaw && (
            <button
              type="button"
              className="logs-search-clear"
              aria-label="Limpiar búsqueda"
              onClick={() => setSearchRaw('')}
            >
              ×
            </button>
          )}
        </div>
        <div className="logs-count">
          {isDebouncing && <span className="logs-busy">buscando…</span>}
          <span className="logs-total mono">
            {items.length} / {total} registros
          </span>
        </div>
      </div>

      <div className="logs-card">
        <div className="logs-header">
          <span>Nivel</span>
          <span>Código</span>
          <span>Mensaje</span>
          <span>Servicio</span>
          <span>Fecha</span>
        </div>
        {logsQuery.isPending ? (
          <div aria-busy="true" aria-label="Cargando logs">
            {Array.from({ length: 8 }, (_, i) => (
              <div className="skeleton-row" key={i}>
                <div className="skeleton skeleton-cell skeleton-cell--short" />
                <div className="skeleton skeleton-cell" />
                <div className="skeleton skeleton-cell" />
                <div className="skeleton skeleton-cell skeleton-cell--short" />
                <div className="skeleton skeleton-cell skeleton-cell--short" />
              </div>
            ))}
          </div>
        ) : logsQuery.isError ? (
          <div className="logs-state">
            <p>No se pudieron cargar los logs</p>
            <button type="button" className="btn-ghost" onClick={() => logsQuery.refetch()}>
              Reintentar
            </button>
          </div>
        ) : (
          <VirtualLogList items={items} onSelect={setOpenLogId} />
        )}
        <LogsFooter
          total={total}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
        />
      </div>

      {openLogId !== null && detailQuery.data && (
        <StackTraceModal log={detailQuery.data} onClose={close} />
      )}
    </section>
  )
}
