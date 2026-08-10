import type { LogEntry } from '../../types'

function formatTimestamp(iso: string): string {
  return iso.slice(0, 16).replace('T', ' ')
}

interface LogRowProps {
  log: LogEntry
  index: number
  onSelect: (id: number) => void
}

export default function LogRow({ log, index, onSelect }: LogRowProps) {
  return (
    <div
      className={`log-row${index % 2 === 1 ? ' log-row--odd' : ' log-row--even'}`}
      style={{ top: `${index * 56}px`, height: '56px' }}
      onClick={() => onSelect(log.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onSelect(log.id)
        }
      }}
    >
      <span className={`level-badge level-badge--${log.nivel_error}`}>{log.nivel_error}</span>
      <span className="log-code">{log.codigo_error}</span>
      <span className="log-message">{log.mensaje}</span>
      <span className="log-servicio">{log.servicio_responsable}</span>
      <span className="log-time">{formatTimestamp(log.creado_at)}</span>
    </div>
  )
}
