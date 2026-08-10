import type { Remediation } from '../../types'

function formatTimestamp(iso: string): string {
  return iso.slice(0, 16).replace('T', ' ')
}

export default function RemediationTable({ remediations }: { remediations: Remediation[] }) {
  if (remediations.length === 0) {
    return <p className="remediation-empty">Sin acciones de remediación</p>
  }
  return (
    <div className="remediation-card">
      <div className="remediation-header">
        <span>Fecha</span>
        <span>Sincronización</span>
        <span>Acción</span>
        <span>Ejecutado por</span>
        <span>Resultado</span>
        <span>Notas</span>
      </div>
      {remediations.map((r) => (
        <div className="remediation-row" key={r.id}>
          <span className="remediation-time mono">{formatTimestamp(r.ejecutada_at)}</span>
          <span className="remediation-correlation mono">
            {r.correlation_id ?? r.sincronizacion_id}
          </span>
          <span className="action-pill">{r.accion_ejecutada}</span>
          <span className="remediation-actor">{r.ejecutado_por}</span>
          <span className={`status-badge status-badge--${r.resultado}`}>{r.resultado}</span>
          <span className="remediation-notes">{r.notas ?? '—'}</span>
        </div>
      ))}
    </div>
  )
}
