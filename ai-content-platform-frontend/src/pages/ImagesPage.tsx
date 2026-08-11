import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Image as ImageIcon } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/EmptyState';
import { WorkflowStageRail } from '@/components/ai/WorkflowStageRail';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/design-system/ui/card';
import { Button } from '@/design-system/ui/button';
import { useApiQuery } from '@/hooks/useApiQuery';
import type { ApiEnvelope, Draft } from '@/api/types';
import { routes } from '@/lib/routes';

/** Standalone images list — generate from a draft page, not a separate pipeline. */
export function ImagesPage() {
  const navigate = useNavigate();
  const { data } = useApiQuery<ApiEnvelope<{ items?: Draft[] } | Draft[]>>(['drafts'], '/drafts');
  const drafts = useMemo(() => {
    const p = data?.data;
    return Array.isArray(p) ? p : (p?.items ?? []);
  }, [data]);

  return (
    <div>
      <PageHeader
        title="Images"
        description="Open a draft and use “Generate images” on the right — no separate image tab needed."
        actions={<Button onClick={() => navigate(routes.drafts)}>Go to Drafts</Button>}
      />
      <div className="mb-4">
        <WorkflowStageRail current="Visuals" />
      </div>
      {drafts.length === 0 ? (
        <EmptyState
          icon={<ImageIcon className="h-8 w-8" />}
          title="No drafts yet"
          description="Generate a post from News, then create images from that draft page."
          actionLabel="Go to News"
          onAction={() => navigate(routes.news)}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {drafts.slice(0, 12).map((d) => (
            <Card key={d.id}>
              <CardHeader>
                <CardTitle className="text-sm line-clamp-2">{d.title || d.hook || d.id}</CardTitle>
                <CardDescription>Generate images on the draft page</CardDescription>
              </CardHeader>
              <CardContent>
                <Button size="sm" onClick={() => navigate(routes.draft(d.id))}>
                  Open draft
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
