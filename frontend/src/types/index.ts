export type NivelError = 'WARNING' | 'ERROR' | 'CRITICAL'
export type SyncEstado = 'pending' | 'running' | 'completed' | 'failed' | 'rejected'
export type ArchivoEstado = 'accepted' | 'rejected'
export type Resultado = 'success' | 'failed'
export type TipoArchivo = 'ventas' | 'inventario' | 'clientes'

export interface LogEntry {
  id: number
  correlation_id: string
  nivel_error: NivelError
  codigo_error: string
  mensaje: string
  servicio_responsable: string
  creado_at: string
}

export interface LogDetail extends LogEntry {
  stack_trace: string | null
}

export interface Page<T> {
  items: T[]
  total: number
  next_cursor: number | null
  page_size: number
  page: number
}

export interface DashboardMetrics {
  sincronizaciones_activas: number
  completadas_hoy: number
  archivos_rechazados: number
  tasa_errores_criticos: string
}

export interface ThroughputPoint {
  fecha: string
  aceptados: number
  rechazados: number
}

export interface StatusDistributionItem {
  estado: SyncEstado
  count: number
  pct: string
}

export interface Archivo {
  nombre_archivo: string
  tipo_archivo: TipoArchivo
  checksum: string
  estado: ArchivoEstado
  registros_totales: number
}

export interface Sync {
  id: string
  correlation_id: string
  estado: SyncEstado
  fecha_ejecucion: string
  iniciado_at: string
  finalizado_at: string | null
  usuario_origen: string
  archivos_resumen: string
  archivos?: Archivo[]
}

export interface Remediation {
  id: number
  sincronizacion_id: string
  correlation_id: string | null
  accion_ejecutada: string
  ejecutado_por: string
  resultado: Resultado
  notas: string | null
  ejecutada_at: string
}

export type RemediationAction = 'RETRY_JOB' | 'FORCE_SKIP_VALIDATION'
