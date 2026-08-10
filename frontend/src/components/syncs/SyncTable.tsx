import { useState } from 'react'
import { Column } from 'primereact/column'
import { DataTable } from 'primereact/datatable'
import type { Archivo, Sync } from '../../types'

interface SyncTableProps {
  syncs: Sync[]
  onRemediate: (id: string, accion: 'RETRY_JOB' | 'FORCE_SKIP_VALIDATION') => void
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const hhmm = `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`
  return `${hhmm} UTC`
}

function truncateHash(hash: string): string {
  return hash.length > 12 ? `${hash.slice(0, 6)}…${hash.slice(-4)}` : hash
}

function truncateCid(cid: string): string {
  return cid.length > 20 ? `${cid.slice(0, 8)}…${cid.slice(-4)}` : cid
}

function estadoBadge(row: Sync) {
  return <span className={`status-badge status-badge--${row.estado}`}>{row.estado}</span>
}

function archivoEstadoBadge(file: Archivo) {
  return <span className={`status-badge status-badge--${file.estado}`}>{file.estado}</span>
}

function filesGrid(row: Sync) {
  return (
    <div className="archivos-grid">
      <div className="archivos-label">Archivos procesados</div>
      <div className="archivo-row archivo-row--header">
        <span>Archivo</span>
        <span>Tipo</span>
        <span>Checksum</span>
        <span>Estado</span>
        <span className="archivo-registros">Registros</span>
      </div>
      {row.archivos?.map((file) => (
        <div className="archivo-row" key={file.checksum}>
          <div className="archivo-nombre">{file.nombre_archivo}</div>
          <span className="tipo-badge">{file.tipo_archivo}</span>
          <div className="archivo-checksum mono" title={file.checksum}>{truncateHash(file.checksum)}</div>
          {archivoEstadoBadge(file)}
          <div className="archivo-registros mono">{file.registros_totales.toLocaleString('es-AR')}</div>
        </div>
      ))}
    </div>
  )
}

function retryAction(row: Sync, onRemediate: SyncTableProps['onRemediate']) {
  if (row.estado !== 'failed' && row.estado !== 'rejected') return null
  return (
    <button
      type="button"
      className="btn-ghost sync-retry"
      onClick={() => onRemediate(row.id, 'RETRY_JOB')}
    >
      Reintentar
    </button>
  )
}

export default function SyncTable({ syncs, onRemediate }: SyncTableProps) {
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({})
  return (
    <div className="syncs-card">
      <DataTable
        value={syncs}
        dataKey="id"
        expandedRows={expandedRows}
        onRowToggle={(event) => setExpandedRows(event.data as Record<string, boolean>)}
        rowExpansionTemplate={filesGrid}
        emptyMessage="Sin sincronizaciones"
      >
        <Column expander style={{ width: '3rem', flexShrink: 0 }} />
        <Column
          field="correlation_id"
          header="Correlation ID"
          style={{ width: '11rem' }}
          body={(row: Sync) => (
            <span className="sync-correlation mono" title={row.correlation_id}>
              {truncateCid(row.correlation_id)}
            </span>
          )}
        />
        <Column field="estado" header="Estado" style={{ width: '8rem' }} body={estadoBadge} />
        <Column field="fecha_ejecucion" header="Fecha" style={{ width: '7rem' }} />
        <Column
          field="iniciado_at"
          header="Iniciado"
          style={{ width: '7rem' }}
          body={(row: Sync) => <span className="sync-time mono">{fmtTime(row.iniciado_at)}</span>}
        />
        <Column
          field="finalizado_at"
          header="Finalizado"
          style={{ width: '7rem' }}
          body={(row: Sync) => (
            <span className="sync-time mono">{fmtTime(row.finalizado_at)}</span>
          )}
        />
        <Column field="usuario_origen" header="Usuario" style={{ width: '8rem' }} />
        <Column field="archivos_resumen" header="Archivos" style={{ minWidth: '10rem' }} />
        <Column
          header=""
          style={{ width: '7rem', textAlign: 'right' }}
          body={(row: Sync) => retryAction(row, onRemediate)}
        />
      </DataTable>
    </div>
  )
}
