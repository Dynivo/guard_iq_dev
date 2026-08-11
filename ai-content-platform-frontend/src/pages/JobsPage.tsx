import { useMemo } from 'react';
import type { ColumnDef } from '@tanstack/react-table';
import { useApiQuery } from '@/hooks/useApiQuery';
import { PageHeader } from '@/components/PageHeader';
import { DataTable } from '@/components/DataTable';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { StatusChip } from '@/components/ai/StatusChip';
import { Spinner } from '@/components/Spinner';
import type { Job, ApiEnvelope } from '@/api/types';
import { ListTodo } from 'lucide-react';

export function JobsPage() {
  const { data, isLoading, isError, refetch } = useApiQuery<
    ApiEnvelope<Job[] | { items?: Job[] }>
  >(['jobs'], '/jobs', { staleTime: 0 });

  const jobs = useMemo(() => {
    const p = data?.data;
    return Array.isArray(p) ? p : (p?.items ?? []);
  }, [data]);

  const columns = useMemo<ColumnDef<Job>[]>(
    () => [
      { accessorKey: 'type', header: 'Type' },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => <StatusChip status={row.original.status as any} />,
      },
      {
        id: 'provider',
        header: 'Provider',
        cell: ({ row }) => {
          const payload = (row.original.payload || {}) as Record<string, unknown>;
          return String(payload.provider || '—');
        },
      },
      {
        id: 'cost',
        header: 'Cost',
        cell: ({ row }) => {
          const payload = (row.original.payload || {}) as Record<string, unknown>;
          const cost = payload.cost_estimate;
          if (cost == null || cost === '') return '—';
          return `$${Number(cost).toFixed(4)}`;
        },
      },
      {
        accessorKey: 'progress',
        header: 'Progress',
        cell: ({ row }) =>
          row.original.status === 'running' || row.original.status === 'generating' ? (
            <div className="w-28">
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-accent transition-all duration-[var(--duration-normal)]"
                  style={{ width: `${row.original.progress}%` }}
                />
              </div>
            </div>
          ) : (
            '—'
          ),
      },
      {
        accessorKey: 'created_at',
        header: 'Created',
        cell: ({ getValue }) => {
          const v = String(getValue() || '');
          return v ? new Date(v).toLocaleString() : '—';
        },
      },
      {
        accessorKey: 'error_message',
        header: 'Error',
        cell: ({ getValue }) => (
          <span className="text-destructive">{String(getValue() || '')}</span>
        ),
      },
    ],
    []
  );

  if (isLoading) return <Spinner />;
  if (isError) return <ErrorState message="Unable to load jobs." onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Jobs"
        description="Ingest jobs plus image generation batches — live from the database."
      />
      {jobs.length === 0 ? (
        <EmptyState
          icon={<ListTodo className="h-8 w-8" />}
          title="No jobs yet"
          description="Run a news source or generate an image — jobs will list here with status and errors."
        />
      ) : (
        <DataTable columns={columns} data={jobs} searchKey="type" searchPlaceholder="Filter jobs…" />
      )}
    </div>
  );
}
