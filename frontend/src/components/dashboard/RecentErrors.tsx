import { useNavigate } from 'react-router-dom'
import type { LogEntry } from '../../types'

const LEVEL_DOT: Record<string, string> = {
  CRITICAL: '#c0392b',
  ERROR: '#c0392b',
  WARNING: '#d4860a',
}

function formatTimestamp(iso: string): string {
  return iso.slice(0, 16).replace('T', ' ')
}

export default function RecentErrors({ logs }: { logs: LogEntry[] }) {
  const navigate = useNavigate()
  if (logs.length === 0) {
    return <p className="recent-empty">Sin errores recientes</p>
  }
  return (
    <div className="recent-list">
      {logs.map((log) => (
        <button
          type="button"
          className="recent-row"
          key={log.id}
          onClick={() => navigate('/logs', { state: { openLogId: log.id } })}
        >
          <span
            className="recent-dot"
            style={{ background: LEVEL_DOT[log.nivel_error] ?? 'var(--text-secondary)' }}
          />
          <span className="recent-code">{log.codigo_error}</span>
          <span className="recent-message">{log.mensaje}</span>
          <span className="recent-time">{formatTimestamp(log.creado_at)}</span>
        </button>
      ))}
    </div>
  )
}
