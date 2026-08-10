import { useRef } from 'react'
import { useFocusTrap } from '../../hooks/useFocusTrap'
import type { LogDetail } from '../../types'

const LEVEL_VISUAL: Record<string, [string, string]> = {
  WARNING: ['var(--level-warn-bg)', 'var(--level-warn-text)'],
  ERROR: ['var(--level-err-bg)', 'var(--level-err-text)'],
  CRITICAL: ['var(--level-crt-bg)', 'var(--level-crt-text)'],
}

interface StackTraceModalProps {
  log: LogDetail
  onClose: () => void
}

export default function StackTraceModal({ log, onClose }: StackTraceModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const [bg, text] = LEVEL_VISUAL[log.nivel_error] ?? ['var(--tag-bg)', 'var(--text-secondary)']
  useFocusTrap(true, dialogRef, onClose)

  return (
    <div className="stack-modal-mask" onMouseDown={onClose}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Detalle de error ${log.codigo_error}`}
        className="stack-modal"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="stack-modal-header">
          <div className="stack-modal-heading">
            <span
              className={`level-badge level-badge--${log.nivel_error}`}
              style={{ background: bg, color: text }}
            >
              {log.nivel_error}
            </span>
            <div className="stack-modal-code">{log.codigo_error}</div>
          </div>
          <button type="button" className="stack-modal-close" aria-label="Cerrar" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="stack-modal-body">
          <p className="stack-modal-message">{log.mensaje}</p>
          <div className="stack-modal-meta">
            <div>
              <div className="stack-modal-meta-label">Correlation ID</div>
              <div className="stack-modal-meta-value mono">{log.correlation_id}</div>
            </div>
            <div>
              <div className="stack-modal-meta-label">Servicio</div>
              <div className="stack-modal-meta-value">{log.servicio_responsable}</div>
            </div>
            <div>
              <div className="stack-modal-meta-label">Registrado</div>
              <div className="stack-modal-meta-value mono">{log.creado_at}</div>
            </div>
          </div>
          <div className="stack-modal-trace-label">Stack trace</div>
          <pre className="stack-modal-trace">{log.stack_trace ?? 'Sin stack trace disponible'}</pre>
        </div>
        <div className="stack-modal-footer">
          <button type="button" className="btn-ghost" onClick={onClose}>
            Cerrar (Esc)
          </button>
          <button type="button" className="btn-accent" onClick={onClose}>
            Reintentar job
          </button>
        </div>
      </div>
    </div>
  )
}
