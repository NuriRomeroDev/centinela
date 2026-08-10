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
  return d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', hour12: false }) + ' UTC'
}

function truncateHash(hash: string): string {
  return hash.length > 12 ? `${hash.slice(0, 6)}…${hash.slice(-4)}` : hash
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
        <Column expander className="sync-expander" />
        <Column
          field="correlation_id"
          header="Correlation ID"
          body={(row: Sync) => <span className="sync-correlation mono">{row.correlation_id}</span>}
        />
        <Column field="estado" header="Estado" body={estadoBadge} />
        <Column field="fecha_ejecucion" header="Fecha" />
        <Column
          field="iniciado_at"
          header="Iniciado"
          body={(row: Sync) => <span className="sync-time mono">{fmtTime(row.iniciado_at)}</span>}
        />
        <Column
          field="finalizado_at"
          header="Finalizado"
          body={(row: Sync) => (
            <span className="sync-time mono">{fmtTime(row.finalizado_at)}</span>
          )}
        />
        <Column field="usuario_origen" header="Usuario" />
        <Column field="archivos_resumen" header="Archivos" />
        <Column
          header=""
          body={(row: Sync) => retryAction(row, onRemediate)}
          className="sync-actions"
        />
      </DataTable>
    </div>
  )
}
