import RemediationTable from '../components/syncs/RemediationTable'
import { useRemediations } from '../api/queries'

export default function Remediacion() {
  const remediationsQuery = useRemediations()
  return (
    <section className="page">
      {remediationsQuery.isPending ? (
        <div className="widget-state" aria-busy="true" />
      ) : remediationsQuery.isError ? (
        <div className="widget-state">
          <p className="widget-state-text">No se pudieron cargar las remediaciones</p>
          <button type="button" className="btn-ghost" onClick={() => remediationsQuery.refetch()}>
            Reintentar
          </button>
        </div>
      ) : (
        <RemediationTable remediations={remediationsQuery.data ?? []} />
      )}
    </section>
  )
}
