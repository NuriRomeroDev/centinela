import type {
  DashboardMetrics,
  LogDetail,
  LogEntry,
  Page,
  Remediation,
  RemediationAction,
  StatusDistributionItem,
  Sync,
  ThroughputPoint,
} from '../types'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const BASE = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, init)
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor')
  }
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: string }
      detail = body.detail ?? detail
    } catch {
      // keep statusText when the body is not JSON
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export const api = {
  dashboardMetrics: () => request<DashboardMetrics>('/dashboard/metrics'),
  throughput: (days = 7) => request<ThroughputPoint[]>(`/throughput?days=${days}`),
  statusDistribution: () => request<StatusDistributionItem[]>('/status-distribution'),
  recentLogs: (limit = 5) => request<LogEntry[]>(`/logs/recent?limit=${limit}`),

  logs: (params: Record<string, string | number | undefined>) => {
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== '') query.set(key, String(value))
    }
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request<Page<LogEntry>>(`/logs${suffix}`)
  },
  logDetail: (id: number) => request<LogDetail>(`/logs/${id}`),

  syncs: (includeFiles = true) =>
    request<Sync[]>(`/syncs?include_files=${includeFiles}`),
  remediations: () => request<Remediation[]>('/remediations'),
  remediate: (sincronizacionId: string, accion: RemediationAction) =>
    request<Sync>(`/syncs/${sincronizacionId}/remediate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ accion }),
    }),
}
