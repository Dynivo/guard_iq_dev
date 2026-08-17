import { useApiQuery } from '@/hooks/useApiQuery';
import { useJobPolling } from '@/hooks/useJobPolling';
import { useQueryClient } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { Spinner } from '@/components/Spinner';
import { ErrorState } from '@/components/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { apiClient } from '@/api/client';
import type { ApiEnvelope } from '@/api/types';
import { Lightbulb, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

interface ArticleRow {
  id: string;
  title: string;
  summary?: string | null;
  status?: string;
}

interface ArticlesPayload {
  items?: ArticleRow[];
}

export function ContentIdeasPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, refetch } = useApiQuery<ApiEnvelope<ArticlesPayload | ArticleRow[]>>(
    ['articles', 'ideas'],
    '/articles?status=relevant'
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const { job, isComplete: jobComplete, isFailed: jobFailed } = useJobPolling(jobId);

  // Draft generation now runs as a background Job instead of blocking the
  // request — this reacts once useJobPolling sees it finish or fail.
  useEffect(() => {
    if (!jobId || (!jobComplete && !jobFailed)) return;
    if (jobFailed) {
      toast.error(job?.error_message || 'Could not generate draft');
    }
    queryClient.invalidateQueries({ queryKey: ['drafts'] });
    setBusy(null);
    setJobId(null);
  }, [jobComplete, jobFailed, jobId, job, queryClient]);

  if (isLoading) return <Spinner />;
  if (isError) return <ErrorState message="Unable to load content ideas." onRetry={refetch} />;

  const payload = data?.data;
  const articles: ArticleRow[] = Array.isArray(payload) ? payload : (payload?.items ?? []);

  const generate = async (id: string) => {
    setBusy(id);
    try {
      const res = await apiClient.post<ApiEnvelope<{ job_id: string }>>(
        `/articles/${id}/generate-draft`,
        { content_type: 'educational' }
      );
      const newJobId = res.data?.data?.job_id;
      if (newJobId) setJobId(newJobId);
      else {
        toast.error('Could not start draft generation');
        setBusy(null);
      }
    } catch {
      toast.error('Could not start draft generation');
      setBusy(null);
    }
  };

  if (articles.length === 0) {
    return (
      <div>
        <PageHeader title="Content Ideas" description="High-relevance articles ready for content creation" />
        <EmptyState
          icon={<Lightbulb className="w-8 h-8 text-navy-400" />}
          title="No content ideas yet"
          description="Score articles from the News Feed. Relevant ones appear here."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Content Ideas" description="High-relevance articles ready for content creation" />
      <div className="space-y-3">
        {articles.map((article) => (
          <Card key={article.id}>
            <CardContent className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <Badge className="mb-2">{article.status || 'relevant'}</Badge>
                <h3 className="font-semibold">{article.title}</h3>
                <p className="text-sm text-[var(--color-text-secondary)] mt-1 line-clamp-2">{article.summary}</p>
              </div>
              <Button size="sm" loading={busy === article.id} onClick={() => generate(article.id)}>
                <Sparkles size={14} className="mr-1" /> Generate
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
