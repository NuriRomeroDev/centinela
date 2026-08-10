import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { RemediationAction } from '../types'

export const POLLING_INTERVAL_MS = 30_000

export function useDashboardMetrics() {
  return useQuery({
    queryKey: ['dashboard', 'metrics'],
    queryFn: api.dashboardMetrics,
    refetchInterval: POLLING_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })
}

export function useThroughput(days = 7) {
  return useQuery({
    queryKey: ['dashboard', 'throughput', days],
    queryFn: () => api.throughput(days),
    refetchInterval: POLLING_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })
}

export function useStatusDistribution() {
  return useQuery({
    queryKey: ['dashboard', 'status-distribution'],
    queryFn: api.statusDistribution,
    refetchInterval: POLLING_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })
}

export function useRecentLogs(limit = 5) {
  return useQuery({
    queryKey: ['dashboard', 'recent-logs', limit],
    queryFn: () => api.recentLogs(limit),
    refetchInterval: POLLING_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })
}

export function useSyncs() {
  return useQuery({
    queryKey: ['syncs'],
    queryFn: () => api.syncs(true),
  })
}

export function useRemediations() {
  return useQuery({
    queryKey: ['remediations'],
    queryFn: api.remediations,
  })
}

export function useRemediate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, accion }: { id: string; accion: RemediationAction }) =>
      api.remediate(id, accion),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['syncs'] })
      queryClient.invalidateQueries({ queryKey: ['remediations'] })
    },
  })
}
