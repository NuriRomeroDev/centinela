import { Link } from 'react-router-dom'
import KpiCard from '../components/dashboard/KpiCard'
import ThroughputChart from '../components/dashboard/ThroughputChart'
import StatusDistribution from '../components/dashboard/StatusDistribution'
import RecentErrors from '../components/dashboard/RecentErrors'
import {
  useDashboardMetrics,
  useRecentLogs,
  useStatusDistribution,
  useThroughput,
} from '../api/queries'

function WidgetError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="widget-state">
      <p className="widget-state-text">No se pudieron cargar los datos</p>
      <button type="button" className="widget-state-retry" onClick={onRetry}>
        Reintentar
      </button>
    </div>
  )
}

function WidgetLoading() {
  return <div className="widget-state" aria-busy="true" />
}

export default function Dashboard() {
  const metricsQuery = useDashboardMetrics()
  const throughputQuery = useThroughput(7)
  const distributionQuery = useStatusDistribution()
  const recentLogsQuery = useRecentLogs(5)

  return (
    <section className="page dashboard">
      <div className="kpi-grid">
        {metricsQuery.isPending ? (
          <WidgetLoading />
        ) : metricsQuery.isError ? (
          <WidgetError onRetry={() => metricsQuery.refetch()} />
        ) : metricsQuery.data ? (
          <>
            <KpiCard
              label="Sincronizaciones activas"
              value={String(metricsQuery.data.sincronizaciones_activas)}
              delta="+1 vs ayer"
              tone="accent"
              sub="Sincronizaciones en ejecución"
            />
            <KpiCard
              label="Completadas hoy"
              value={String(metricsQuery.data.completadas_hoy)}
              delta={`+${metricsQuery.data.completadas_hoy}`}
              tone="up"
              sub="Sin intervención manual requerida"
            />
            <KpiCard
              label="Archivos rechazados"
              value={String(metricsQuery.data.archivos_rechazados)}
              delta={metricsQuery.data.archivos_rechazados > 0 ? 'revisar' : 'ok'}
              tone={metricsQuery.data.archivos_rechazados > 0 ? 'down' : 'up'}
              sub="Por checksum o esquema inválido"
            />
            <KpiCard
              label="Tasa de errores críticos"
              value={`${metricsQuery.data.tasa_errores_criticos}%`}
              delta={Number(metricsQuery.data.tasa_errores_criticos) > 10 ? 'crítico' : 'en monitoreo'}
              tone={Number(metricsQuery.data.tasa_errores_criticos) > 10 ? 'down' : 'accent'}
              sub="Sobre el total de logs capturados"
            />
          </>
        ) : null}
      </div>

      <div className="dashboard-grid">
        <article className="card">
          <h2 className="card-title">Throughput de lotes · últimos 7 días</h2>
          {throughputQuery.isPending ? (
            <WidgetLoading />
          ) : throughputQuery.isError ? (
            <WidgetError onRetry={() => throughputQuery.refetch()} />
          ) : (
            <ThroughputChart points={throughputQuery.data ?? []} />
          )}
        </article>

        <article className="card">
          <h2 className="card-title">Distribución de estados</h2>
          {distributionQuery.isPending ? (
            <WidgetLoading />
          ) : distributionQuery.isError ? (
            <WidgetError onRetry={() => distributionQuery.refetch()} />
          ) : (
            <StatusDistribution items={distributionQuery.data ?? []} />
          )}
        </article>
      </div>

      <article className="card">
        <div className="card-head">
          <h2 className="card-title">Actividad reciente de errores</h2>
          <Link to="/logs" className="card-link">
            Ver todos →
          </Link>
        </div>
        {recentLogsQuery.isPending ? (
          <WidgetLoading />
        ) : recentLogsQuery.isError ? (
          <WidgetError onRetry={() => recentLogsQuery.refetch()} />
        ) : (
          <RecentErrors logs={recentLogsQuery.data ?? []} />
        )}
      </article>
    </section>
  )
}
