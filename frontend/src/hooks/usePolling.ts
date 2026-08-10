import { useQuery, type QueryKey } from '@tanstack/react-query'

export const POLLING_INTERVAL_MS = 30_000

export function usePolling<T>(queryKey: QueryKey, queryFn: () => Promise<T>) {
  return useQuery({
    queryKey,
    queryFn,
    refetchInterval: POLLING_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })
}
