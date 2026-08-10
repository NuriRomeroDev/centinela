import { useRef } from 'react'
import { Toast } from 'primereact/toast'
import SyncTable from '../components/syncs/SyncTable'
import { useRemediate, useSyncs } from '../api/queries'

export default function Sincronizaciones() {
  const syncsQuery = useSyncs()
  const remediate = useRemediate()
  const toastRef = useRef<Toast>(null)

  const handleRemediate = (id: string) => {
    remediate.mutate(
      { id, accion: 'RETRY_JOB' },
      {
        onSuccess: () => {
          toastRef.current?.show({
            severity: 'success',
            summary: 'Reintento programado',
            detail: 'La sincronización pasó a running',
          })
        },
        onError: () => {
          toastRef.current?.show({
            severity: 'error',
            summary: 'No se pudo reintentar',
            detail: 'Verificá el estado de la sincronización',
          })
        },
      },
    )
  }

  return (
    <section className="page">
      <Toast ref={toastRef} />
      {syncsQuery.isPending ? (
        <div className="widget-state" aria-busy="true" />
      ) : syncsQuery.isError ? (
        <div className="widget-state">
          <p className="widget-state-text">No se pudieron cargar las sincronizaciones</p>
          <button type="button" className="btn-ghost" onClick={() => syncsQuery.refetch()}>
            Reintentar
          </button>
        </div>
      ) : (
        <SyncTable syncs={syncsQuery.data ?? []} onRemediate={handleRemediate} />
      )}
    </section>
  )
}
