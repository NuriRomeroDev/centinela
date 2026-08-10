import React, { useState } from 'react'
import type { Archivo, Sync } from '../../types'

interface SyncTableProps {
  syncs: Sync[]
  onRemediate: (id: string, accion: 'RETRY_JOB' | 'FORCE_SKIP_VALIDATION') => void
}

function fmtDate(iso: string): string {
  return iso.slice(0, 10)
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  const m = iso.match(/T(\d{2}):(\d{2})/)
  return m ? `${m[1]}:${m[2]}` : '—'
}

function truncateHash(hash: string): string {
  return hash.length > 16 ? `${hash.slice(0, 8)}…${hash.slice(-6)}` : hash
}

function truncateCid(cid: string): string {
  return cid.length > 18 ? `${cid.slice(0, 8)}…${cid.slice(-4)}` : cid
}

const ESTADO_LABEL: Record<string, string> = {
  completed: 'Completado',
  running:   'En curso',
  failed:    'Fallido',
  pending:   'Pendiente',
  rejected:  'Rechazado',
}

function EstadoBadge({ estado }: { estado: string }) {
  return (
    <span className={`status-badge status-badge--${estado}`}>
      {ESTADO_LABEL[estado] ?? estado}
    </span>
  )
}

function ArchivoEstadoBadge({ estado }: { estado: string }) {
  return (
    <span className={`status-badge status-badge--${estado}`}>
      {estado === 'accepted' ? 'Aceptado' : 'Rechazado'}
    </span>
  )
}

function FilesPanel({ row }: { row: Sync }) {
  const archivos = row.archivos ?? []
  return (
    <div className="syncs-files-panel">
      <div className="syncs-files-header">
        <div className="syncs-files-title">
          <span className="syncs-files-icon">📂</span>
          Archivos procesados
          <span className="syncs-files-count">{archivos.length}</span>
        </div>
        <div className="syncs-files-timing mono">
          <span className="syncs-timing-label">Inicio</span>
          <span>{fmtTime(row.iniciado_at)} UTC</span>
          <span className="syncs-timing-sep">→</span>
          <span className="syncs-timing-label">Fin</span>
          <span>{fmtTime(row.finalizado_at)} UTC</span>
        </div>
      </div>

      <table className="syncs-files-table">
        <thead>
          <tr>
            <th>Nombre del archivo</th>
            <th>Tipo</th>
            <th>Checksum SHA-256</th>
            <th>Estado</th>
            <th className="syncs-files-col-num">Registros</th>
          </tr>
        </thead>
        <tbody>
          {archivos.map((file: Archivo) => (
            <tr key={file.checksum} className={file.estado === 'rejected' ? 'syncs-files-row--rejected' : ''}>
              <td className="syncs-files-nombre mono">{file.nombre_archivo}</td>
              <td><span className="tipo-badge">{file.tipo_archivo}</span></td>
              <td className="syncs-files-checksum mono" title={file.checksum}>{truncateHash(file.checksum)}</td>
              <td><ArchivoEstadoBadge estado={file.estado} /></td>
              <td className="syncs-files-col-num mono">{file.registros_totales.toLocaleString('es-AR')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ArchivosPill({ resumen }: { resumen: string }) {
  const m = resumen.match(/(\d+) total · (\d+)/)
  if (!m) return <span className="syncs-archivos-plain">{resumen}</span>
  const total = Number(m[1])
  const rej = Number(m[2])
  return (
    <div className="syncs-archivos-pill">
      <div className="syncs-archivos-top">
        <span className="syncs-archivos-num">{total}</span>
        <span className="syncs-archivos-label">archivos</span>
      </div>
      {rej > 0
        ? <span className="syncs-archivos-rej">{rej} rechazado{rej > 1 ? 's' : ''}</span>
        : <span className="syncs-archivos-ok">sin rechazos</span>}
    </div>
  )
}

export default function SyncTable({ syncs, onRemediate }: SyncTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  function toggle(id: string) {
    setExpandedRows(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  if (syncs.length === 0) {
    return (
      <div className="syncs-card">
        <div className="syncs-empty">Sin sincronizaciones registradas</div>
      </div>
    )
  }

  return (
    <div className="syncs-card">
      <table className="syncs-table">
        <thead>
          <tr>
            <th className="syncs-col-expander" aria-label="Expandir" />
            <th className="syncs-col-cid">Correlation ID</th>
            <th className="syncs-col-estado">Estado</th>
            <th className="syncs-col-fecha">Fecha</th>
            <th className="syncs-col-usuario">Usuario</th>
            <th className="syncs-col-archivos">Archivos</th>
            <th className="syncs-col-action">Acciones</th>
          </tr>
        </thead>
        <tbody>
          {syncs.map((row) => {
            const expanded = expandedRows.has(row.id)
            const canRetry = row.estado === 'failed' || row.estado === 'rejected'
            return (
              <React.Fragment key={row.id}>
                <tr
                  className={`syncs-row${expanded ? ' syncs-row--expanded' : ''}`}
                  onClick={() => toggle(row.id)}
                  aria-expanded={expanded}
                >
                  <td className="syncs-col-expander">
                    <span className={`syncs-chevron${expanded ? ' syncs-chevron--open' : ''}`}>›</span>
                  </td>
                  <td className="syncs-col-cid">
                    <span className="mono syncs-cid" title={row.correlation_id}>
                      {truncateCid(row.correlation_id)}
                    </span>
                  </td>
                  <td className="syncs-col-estado">
                    <EstadoBadge estado={row.estado} />
                  </td>
                  <td className="syncs-col-fecha">
                    <span className="syncs-fecha">{fmtDate(row.fecha_ejecucion)}</span>
                  </td>
                  <td className="syncs-col-usuario">
                    <span className="syncs-usuario">{row.usuario_origen}</span>
                  </td>
                  <td className="syncs-col-archivos">
                    <ArchivosPill resumen={row.archivos_resumen} />
                  </td>
                  <td className="syncs-col-action" onClick={e => e.stopPropagation()}>
                    {canRetry && (
                      <button
                        type="button"
                        className="sync-retry"
                        onClick={() => onRemediate(row.id, 'RETRY_JOB')}
                      >
                        Reintentar
                      </button>
                    )}
                  </td>
                </tr>
                {expanded && (
                  <tr className="syncs-row-files">
                    <td colSpan={7}>
                      <FilesPanel row={row} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
