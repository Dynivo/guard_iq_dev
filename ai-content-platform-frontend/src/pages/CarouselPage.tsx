import { useNavigate } from 'react-router-dom';
import { Layers } from 'lucide-react';
import { useApiQuery } from '@/hooks/useApiQuery';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { WorkflowStageRail } from '@/components/ai/WorkflowStageRail';
import { Button } from '@/design-system/ui/button';
import { Badge } from '@/design-system/ui/badge';
import { Skeleton } from '@/design-system/ui/skeleton';
import type { ApiEnvelope } from '@/api/types';
import { routes } from '@/lib/routes';

interface CarouselRow {
  id: string;
  title?: string | null;
  slides_count?: number;
  status?: string;
  draft_id?: string;
  created_at?: string | null;
}

export function CarouselPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useApiQuery<
    ApiEnvelope<CarouselRow[] | { items?: CarouselRow[] }>
  >(['carousels'], '/carousels');

  const payload = data?.data;
  const rows: CarouselRow[] = Array.isArray(payload) ? payload : (payload?.items ?? []);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (isError) {
    return <ErrorState message="Unable to load carousels." onRetry={refetch} />;
  }

  return (
    <div>
      <PageHeader
        title="Carousel"
        description="Preview and open generated carousel decks. Create new ones from a draft."
        actions={<Button onClick={() => navigate(routes.drafts)}>Go to Drafts</Button>}
      />
      <div className="mb-4">
        <WorkflowStageRail current="Visuals" />
      </div>

      {rows.length === 0 ? (
        <EmptyState
          icon={<Layers className="h-8 w-8" />}
          title="No carousels yet"
          description="Open a draft, expand optional extras, and generate a carousel."
          actionLabel="Open Drafts"
          onAction={() => navigate(routes.drafts)}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((row) => (
            <button
              key={row.id}
              type="button"
              className="rounded-lg border border-[var(--color-border)] p-4 text-left hover:bg-[var(--color-surface)]"
              onClick={() =>
                row.draft_id ? navigate(routes.draft(row.draft_id)) : undefined
              }
            >
              <div className="mb-2 flex items-center gap-2">
                <Badge variant="secondary">{row.status || 'ready'}</Badge>
                <span className="text-xs text-muted-foreground">
                  {row.slides_count ?? 0} slides
                </span>
              </div>
              <p className="font-medium">{row.title || 'Untitled carousel'}</p>
              {row.created_at && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {new Date(row.created_at).toLocaleString()}
                </p>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
