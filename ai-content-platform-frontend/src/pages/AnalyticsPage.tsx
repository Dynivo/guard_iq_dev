import { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useApiQuery } from '@/hooks/useApiQuery';
import type { ApiEnvelope } from '@/api/types';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/design-system/ui/card';
import { Skeleton } from '@/design-system/ui/skeleton';
import { ErrorState } from '@/components/ErrorState';
import { StatusChip } from '@/components/ai/StatusChip';
import { DataTable } from '@/components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';

export function AnalyticsPage() {
  const metrics = useApiQuery<ApiEnvelope<Record<string, unknown>>>(
    ['analytics-metrics'],
    '/analytics/metrics',
    { staleTime: 0 }
  );
  const cost = useApiQuery<ApiEnvelope<{ total?: number; usage?: Record<string, number> }>>(
    ['analytics-cost'],
    '/analytics/cost',
    { staleTime: 0 }
  );
  const usage = useApiQuery<ApiEnvelope<{ usage?: Record<string, number>; signals?: unknown[] }>>(
    ['analytics-usage'],
    '/analytics/usage',
    { staleTime: 0 }
  );
  const providers = useApiQuery<ApiEnvelope<unknown[] | { items?: unknown[] }>>(
    ['analytics-providers'],
    '/analytics/providers/health',
    { staleTime: 0 }
  );
  const models = useApiQuery<ApiEnvelope<unknown[] | { items?: unknown[] }>>(
    ['analytics-models'],
    '/analytics/models/health',
    { staleTime: 0 }
  );
  const workflows = useApiQuery<ApiEnvelope<Record<string, unknown>>>(
    ['analytics-workflows'],
    '/analytics/workflows/health',
    { staleTime: 0 }
  );
  const evaluations = useApiQuery<ApiEnvelope<unknown[]>>(
    ['analytics-evals'],
    '/analytics/evaluations',
    { staleTime: 0 }
  );

  const loading = metrics.isLoading || cost.isLoading;
  const errored = metrics.isError && cost.isError;

  const providerRows = useMemo(() => {
    const raw = providers.data?.data;
    const list = Array.isArray(raw) ? raw : [];
    return list.map((p, i) => {
      const row = p as Record<string, unknown>;
      const availabilityRaw = row.availability;
      const availability =
        availabilityRaw === null || availabilityRaw === undefined
          ? null
          : Number(availabilityRaw);
      return {
        id: String(row.provider || i),
        provider: String(row.provider || 'unknown'),
        status: String(row.status || 'idle'),
        configured: Boolean(row.configured),
        requests: Number(row.requests ?? 0),
        availability,
        failures: Number(row.failures ?? 0),
        avgLatency: Number(row.average_latency_ms ?? 0),
      };
    });
  }, [providers.data]);

  const providersUsed = useMemo(
    () => providerRows.filter((r) => r.requests > 0).length,
    [providerRows]
  );

  const providerColumns = useMemo<ColumnDef<(typeof providerRows)[0]>[]>(
    () => [
      { accessorKey: 'provider', header: 'Provider' },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => {
          const s = row.original.status;
          const label =
            s === 'active'
              ? 'In use'
              : s === 'configured'
                ? 'Configured'
                : s;
          return (
            <StatusChip
              status={s === 'active' ? 'completed' : 'pending'}
              label={label}
            />
          );
        },
      },
      {
        accessorKey: 'availability',
        header: 'Availability',
        cell: ({ row }) => {
          const a = row.original.availability;
          if (a === null || row.original.requests === 0) return '—';
          return `${(a * 100).toFixed(1)}%`;
        },
      },
      { accessorKey: 'failures', header: 'Failures' },
      {
        accessorKey: 'avgLatency',
        header: 'Avg latency',
        cell: ({ row }) =>
          row.original.requests === 0
            ? '—'
            : `${Number(row.original.avgLatency).toFixed(0)} ms`,
      },
    ],
    []
  );

  const costSeries = useMemo(() => {
    const usageMap = cost.data?.data?.usage || usage.data?.data?.usage || {};
    return Object.entries(usageMap).map(([name, value]) => ({ name, value: Number(value) }));
  }, [cost.data, usage.data]);

  const modelSeries = useMemo(() => {
    const raw = models.data?.data;
    const list = Array.isArray(raw) ? raw : [];
    return list.map((m) => {
      const row = m as Record<string, unknown>;
      return {
        name: String(row.model || row.provider || 'model'),
        requests: Number(row.requests ?? 0),
        cost: Number(row.total_cost ?? 0),
      };
    });
  }, [models.data]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (errored) {
    return <ErrorState message="Analytics APIs unavailable" onRetry={() => { metrics.refetch(); cost.refetch(); }} />;
  }

  const totalCost = cost.data?.data?.total ?? 0;
  const evalCount = Array.isArray(evaluations.data?.data) ? evaluations.data!.data!.length : 0;
  const metricsCounters = (metrics.data?.data?.counters || {}) as Record<string, number>;
  const wfTotal =
    Number((workflows.data?.data as { total_jobs?: number } | undefined)?.total_jobs) ||
    Number(metricsCounters.jobs_total) ||
    0;
  const llmCalls = Number(metricsCounters.llm_calls) || 0;

  return (
    <div>
      <PageHeader
        title="Analytics & Observability"
        description="Live data from LLM calls, image jobs, and ingest jobs stored in the database — not static config."
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="p-5">
            <p className="text-xs text-muted-foreground">Total cost (USD)</p>
            <p className="text-2xl font-semibold tabular-nums">${Number(totalCost).toFixed(4)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-xs text-muted-foreground">LLM calls recorded</p>
            <p className="text-2xl font-semibold tabular-nums">{llmCalls || evalCount}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-xs text-muted-foreground">Providers used</p>
            <p className="text-2xl font-semibold tabular-nums">{providersUsed}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {providerRows.length} configured
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-xs text-muted-foreground">Jobs tracked</p>
            <p className="text-2xl font-semibold tabular-nums">{wfTotal}</p>
            <StatusChip className="mt-2" status="completed" label="Live DB" />
          </CardContent>
        </Card>
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Cost by provider</CardTitle>
            <CardDescription>
              From recorded tokens × vendor list prices (USD per 1M tokens in pricing.yaml)
            </CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {costSeries.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={costSeries}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="value" fill="var(--accent)" radius={6} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground">
                No cost yet. Generate a draft or image — calls are saved to the database and show up
                here.
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Model usage</CardTitle>
            <CardDescription>Only models that actually ran for your org</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {modelSeries.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={modelSeries}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="requests" stroke="var(--accent)" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground">
                No model usage yet. After you score news or write a draft, openai / gemini rows appear
                here with real request counts.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Provider health</CardTitle>
          <CardDescription>
            Keys configured on this server plus live availability when calls exist
          </CardDescription>
        </CardHeader>
        <CardContent>
          {providerRows.length ? (
            <DataTable columns={providerColumns} data={providerRows} searchKey="provider" />
          ) : (
            <p className="text-sm text-muted-foreground">
              No provider traffic recorded yet for this organization.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
