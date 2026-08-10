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
      <table className="remediation-table">
        <thead>
          <tr>
            <th className="rem-col-fecha">Fecha</th>
            <th className="rem-col-sync">Sincronización</th>
            <th className="rem-col-accion">Acción</th>
            <th className="rem-col-actor">Ejecutado por</th>
            <th className="rem-col-resultado">Resultado</th>
            <th className="rem-col-notas">Notas</th>
          </tr>
        </thead>
        <tbody>
          {remediations.map((r) => (
            <tr className="remediation-row" key={r.id}>
              <td className="remediation-time mono">{formatTimestamp(r.ejecutada_at)}</td>
              <td className="remediation-correlation mono">
                {r.correlation_id ?? r.sincronizacion_id}
              </td>
              <td><span className="action-pill">{r.accion_ejecutada}</span></td>
              <td className="remediation-actor">{r.ejecutado_por}</td>
              <td>
                <span className={`status-badge status-badge--${r.resultado}`}>{r.resultado}</span>
              </td>
              <td className="remediation-notes">{r.notas ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
