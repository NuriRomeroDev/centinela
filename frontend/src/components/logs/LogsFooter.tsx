interface LogsFooterProps {
  total: number
  page: number
  pageSize: number
  onPageChange: (page: number) => void
}

export default function LogsFooter({ total, page, pageSize, onPageChange }: LogsFooterProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(total, page * pageSize)
  return (
    <div className="logs-footer">
      <div className="logs-footer-count">
        Mostrando <b>{from}–{to}</b> de {total}
      </div>
      <div className="logs-footer-pages">
        <button
          type="button"
          className="page-square"
          aria-label="‹"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          ‹
        </button>
        {Array.from({ length: pages }, (_, index) => index + 1).map((p) => (
          <button
            type="button"
            key={p}
            className={`page-square${p === page ? ' page-square--active' : ''}`}
            onClick={() => onPageChange(p)}
          >
            {p}
          </button>
        ))}
        <button
          type="button"
          className="page-square"
          aria-label="›"
          disabled={page >= pages}
          onClick={() => onPageChange(page + 1)}
        >
          ›
        </button>
      </div>
    </div>
  )
}
