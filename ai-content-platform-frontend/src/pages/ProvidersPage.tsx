import { useApiQuery } from '@/hooks/useApiQuery'
import type { ApiEnvelope } from '@/api/types'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { DataTable } from '@/components/DataTable'
import { StatusChip } from '@/components/ai/StatusChip'
import { Skeleton } from '@/design-system/ui/skeleton'
import { Cpu } from 'lucide-react'
import { useMemo } from 'react'
import type { ColumnDef } from '@tanstack/react-table'

interface ProviderRow {
  id: string
  provider: string
  status: string
  configured: boolean
  requests: number
  availability: number | null
  failures: number
  timeouts: number
  average_latency_ms: number
}

export function ProvidersPage() {
  const { data, isLoading, isError, refetch } = useApiQuery<ApiEnvelope<ProviderRow[] | unknown[]>>(
    ['providers-health'],
    '/analytics/providers/health',
    { staleTime: 0 }
  )

  const rows = useMemo(() => {
    const list = Array.isArray(data?.data) ? data!.data! : []
    return list.map((p, i) => {
      const row = p as Record<string, unknown>
      const availabilityRaw = row.availability
      const availability =
        availabilityRaw === null || availabilityRaw === undefined
          ? null
          : Number(availabilityRaw)
      return {
        id: String(row.provider || i),
        provider: String(row.provider || 'unknown'),
        status: String(row.status || 'idle'),
        configured: Boolean(row.configured),
        requests: Number(row.requests ?? 0),
        availability,
        failures: Number(row.failures ?? 0),
        timeouts: Number(row.timeouts ?? 0),
        average_latency_ms: Number(row.average_latency_ms ?? 0),
      } satisfies ProviderRow
    })
  }, [data])

  const columns = useMemo<ColumnDef<ProviderRow>[]>(
    () => [
      { accessorKey: 'provider', header: 'Provider' },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => {
          const s = row.original.status
          const label =
            s === 'active'
              ? 'In use'
              : s === 'configured'
                ? 'Configured'
                : s === 'observed'
                  ? 'Observed'
                  : s
          const chip =
            s === 'active' ? 'completed' : s === 'configured' ? 'pending' : 'pending'
          return <StatusChip status={chip} label={label} />
        },
      },
      {
        accessorKey: 'availability',
        header: 'Availability',
        cell: ({ row }) => {
          const a = row.original.availability
          if (a === null || row.original.requests === 0) {
            return <span className="text-muted-foreground">—</span>
          }
          return (
            <StatusChip
              status={a > 0.8 ? 'completed' : row.original.failures ? 'failed' : 'pending'}
              label={`${(a * 100).toFixed(0)}%`}
            />
          )
        },
      },
      { accessorKey: 'requests', header: 'Calls' },
      { accessorKey: 'failures', header: 'Failures' },
      { accessorKey: 'timeouts', header: 'Timeouts' },
      {
        accessorKey: 'average_latency_ms',
        header: 'Avg latency',
        cell: ({ row }) =>
          row.original.requests === 0
            ? '—'
            : `${Number(row.original.average_latency_ms).toFixed(0)} ms`,
      },
    ],
    []
  )

  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (isError) return <ErrorState onRetry={refetch} />

  return (
    <div>
      <PageHeader
        title="AI Providers"
        description="Draft generation scores all working keyed models and keeps the best. Call counts update after you generate a new draft. Providers with bad model/deployment names show as failures."
      />
      {rows.length === 0 ? (
        <EmptyState
          icon={<Cpu className="h-8 w-8" />}
          title="No providers configured"
          description="Add OPENAI_API_KEY, GEMINI_API_KEY, PERPLEXITY_API_KEY, or GROK_API_KEY in the backend .env, then refresh."
        />
      ) : (
        <DataTable columns={columns} data={rows} searchKey="provider" />
      )}
    </div>
  )
}
