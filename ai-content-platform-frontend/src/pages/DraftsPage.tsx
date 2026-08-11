import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import type { ColumnDef } from '@tanstack/react-table';
import { FileText, Newspaper, Check } from 'lucide-react';
import { useApiQuery } from '@/hooks/useApiQuery';
import { apiClient } from '@/api/client';
import type { ApiEnvelope, Draft } from '@/api/types';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { DataTable } from '@/components/DataTable';
import { StatusChip } from '@/components/ai/StatusChip';
import { Button } from '@/design-system/ui/button';
import { Skeleton } from '@/design-system/ui/skeleton';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { routes } from '@/lib/routes';

type FilterKey = 'all' | 'needs_review' | 'approved' | 'rejected';
type ContentTypeKey = 'all' | 'educational' | 'success_story' | 'personal_achievement';

function statusLabel(status?: string): string {
  if (status === 'approved' || status === 'published') return 'Approved';
  if (status === 'rejected') return 'Rejected';
  if (status === 'pending_review') return 'Needs review';
  if (status === 'draft') return 'Draft';
  return status ? status.replace(/_/g, ' ') : 'Draft';
}

function mapStatus(s?: string) {
  if (s === 'approved' || s === 'published') return 'approved' as const;
  if (s === 'rejected') return 'rejected' as const;
  if (s === 'pending_review') return 'waiting' as const;
  return 'pending' as const;
}

function draftTitle(d: Draft): string {
  return d.title || d.hook || d.article_title || 'Untitled draft';
}

function contentTypeLabel(t?: string | null): string {
  if (t === 'success_story') return 'Success';
  if (t === 'personal_achievement') return 'Personal';
  if (t === 'educational') return 'Educational';
  return 'Educational';
}

function formatUpdated(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const now = Date.now();
  const diff = now - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function matchesFilter(d: Draft, filter: FilterKey): boolean {
  const s = d.status || 'draft';
  if (filter === 'all') return true;
  if (filter === 'needs_review') return s === 'pending_review' || s === 'draft';
  if (filter === 'approved') return s === 'approved' || s === 'published';
  if (filter === 'rejected') return s === 'rejected';
  return true;
}

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'needs_review', label: 'Needs review' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
];

const CONTENT_TYPES: { key: ContentTypeKey; label: string }[] = [
  { key: 'all', label: 'All types' },
  { key: 'educational', label: 'Educational' },
  { key: 'success_story', label: 'Success' },
  { key: 'personal_achievement', label: 'Personal' },
];

export function DraftsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, refetch } = useApiQuery<ApiEnvelope<Draft[] | { items?: Draft[] }>>(
    ['drafts'],
    '/drafts'
  );
  const [busy, setBusy] = useState<string | null>(null);

  const filterParam = searchParams.get('status') || searchParams.get('filter') || 'all';
  const filter: FilterKey =
    filterParam === 'pending_review' || filterParam === 'needs_review'
      ? 'needs_review'
      : filterParam === 'approved'
        ? 'approved'
        : filterParam === 'rejected'
          ? 'rejected'
          : 'all';
  const contentType = (searchParams.get('type') as ContentTypeKey) || 'all';

  const drafts: Draft[] = useMemo(() => {
    const payload = data?.data;
    const list = Array.isArray(payload) ? payload : (payload?.items ?? []);
    return list.filter((d) => {
      if (!matchesFilter(d, filter)) return false;
      if (contentType === 'all') return true;
      return (d.content_type || 'educational') === contentType;
    });
  }, [data, filter, contentType]);

  const setFilter = (key: FilterKey) => {
    const next = new URLSearchParams(searchParams);
    if (key === 'all') next.delete('status');
    else if (key === 'needs_review') next.set('status', 'pending_review');
    else next.set('status', key);
    setSearchParams(next);
  };

  const setContentType = (key: ContentTypeKey) => {
    const next = new URLSearchParams(searchParams);
    if (key === 'all') next.delete('type');
    else next.set('type', key);
    setSearchParams(next);
  };

  const approve = async (id: string) => {
    setBusy(id);
    try {
      await apiClient.post(`/drafts/${id}/approve`, {});
      toast.success('Approved');
      queryClient.invalidateQueries({ queryKey: ['drafts'] });
    } catch {
      toast.error('Approve failed');
    } finally {
      setBusy(null);
    }
  };

  const columns = useMemo<ColumnDef<Draft>[]>(
    () => [
      {
        id: 'title',
        header: 'Post',
        accessorFn: (row) => draftTitle(row),
        cell: ({ row }) => {
          const d = row.original;
          return (
            <button
              type="button"
              className="max-w-md text-left transition-colors hover:text-accent"
              onClick={() => navigate(routes.draft(d.id))}
            >
              <span className="line-clamp-2 font-medium leading-snug">{draftTitle(d)}</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                {contentTypeLabel(d.content_type)}
                {d.article_title ? ` · ${d.article_title}` : ''}
              </span>
            </button>
          );
        },
      },
      {
        accessorKey: 'status',
        header: 'Status',
        size: 130,
        cell: ({ row }) => (
          <StatusChip status={mapStatus(row.original.status)} label={statusLabel(row.original.status)} />
        ),
      },
      {
        accessorKey: 'updated_at',
        header: 'Updated',
        size: 100,
        cell: ({ getValue }) => (
          <span className="whitespace-nowrap text-sm text-muted-foreground">
            {formatUpdated(String(getValue() || ''))}
          </span>
        ),
      },
      {
        id: 'actions',
        header: '',
        enableSorting: false,
        size: 180,
        cell: ({ row }) => {
          const d = row.original;
          const needsReview = d.status === 'pending_review' || d.status === 'draft';
          return (
            <div className="flex items-center justify-end gap-2">
              {needsReview && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy === d.id}
                  onClick={() => approve(d.id)}
                >
                  <Check className="h-3.5 w-3.5" />
                  Approve
                </Button>
              )}
              <Button size="sm" variant={needsReview ? 'default' : 'outline'} onClick={() => navigate(routes.draft(d.id))}>
                Open
              </Button>
            </div>
          );
        },
      },
    ],
    [busy, navigate, queryClient]
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-36" />
        <Skeleton className="h-10 w-full max-w-md" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (isError) return <ErrorState onRetry={refetch} />;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Drafts"
        description="Review posts, approve when ready, then add visuals."
        actions={
          <Button onClick={() => navigate(routes.news)}>
            <Newspaper className="h-4 w-4" />
            New from News
          </Button>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              className={cn(
                'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                filter === f.key
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <select
          className="h-9 rounded-md border border-border bg-background px-2.5 text-sm"
          value={contentType}
          onChange={(e) => setContentType(e.target.value as ContentTypeKey)}
          aria-label="Post type"
        >
          {CONTENT_TYPES.map((t) => (
            <option key={t.key} value={t.key}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {drafts.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-8 w-8" />}
          title={filter === 'needs_review' ? 'Nothing waiting for review' : 'No drafts yet'}
          description={
            filter === 'needs_review'
              ? 'Generate a draft from News and it will show up here.'
              : 'Pick a news story and turn it into a LinkedIn post.'
          }
          actionLabel="Go to News"
          onAction={() => navigate(routes.news)}
        />
      ) : (
        <DataTable
          columns={columns}
          data={drafts}
          searchKey="title"
          searchPlaceholder="Search drafts…"
          simple
          pageSize={10}
        />
      )}
    </div>
  );
}
