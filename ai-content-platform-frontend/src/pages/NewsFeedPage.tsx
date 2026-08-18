import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  Check,
  EyeOff,
  FileText,
  ImageIcon,
  Loader2,
  Newspaper,
  Sparkles,
  RefreshCw,
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
  ChevronDown,
  ChevronRight,
  Gauge,
} from 'lucide-react';
import { useApiQuery } from '@/hooks/useApiQuery';
import { useJobPolling } from '@/hooks/useJobPolling';
import { apiClient } from '@/api/client';
import type { ApiEnvelope, Draft } from '@/api/types';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { StatusChip } from '@/components/ai/StatusChip';
import { Button } from '@/design-system/ui/button';
import { Input } from '@/design-system/ui/input';
import { Skeleton } from '@/design-system/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/design-system/ui/dialog';
import { toast } from 'sonner';
import { routes } from '@/lib/routes';
import { cn } from '@/lib/utils';

type DraftPhase = 'confirm' | 'writing' | 'opening' | 'error';

const DRAFT_STEPS = [
  { id: 'read', label: 'Read the story' },
  { id: 'write', label: 'Write a LinkedIn post in your brand voice' },
  { id: 'open', label: 'Open the draft so you can edit & add images' },
] as const;

interface SentimentInfo {
  label?: string;
  confidence?: number;
}

interface ArticleRow {
  id: string;
  title: string;
  summary?: string | null;
  url?: string | null;
  status?: string;
  hidden?: boolean;
  source_name?: string | null;
  category?: string | null;
  relevance_score?: number | null;
  ai_relevance?: number | null;
  admin_override?: { status?: string } | null;
  sentiment?: SentimentInfo | null;
  score_json?: { reason?: string | null } | null;
  created_at?: string | null;
}

interface ArticlesPayload {
  items?: ArticleRow[];
  total?: number;
}

interface CategoryRow {
  category: string;
  count: number;
}

interface TrendRow {
  id: string;
  topic_key: string;
  window_label?: string | null;
  growth?: number | null;
  momentum?: number | null;
  velocity?: number | null;
  popularity?: number | null;
  predicted_trend?: number | null;
  article_count?: number | null;
  created_at?: string | null;
}

interface ScreeningJob {
  id: string;
  type: string;
  status: string;
  payload?: { mode?: 'unscored' | 'relevant'; batch_size?: number };
  result?: {
    total?: number;
    completed?: number;
    succeeded?: number;
    failed?: number;
    waiting?: number;
  };
}

interface ScreeningStatusPayload {
  active: boolean;
  job?: ScreeningJob | null;
  pending: number;
  screening: number;
  relevant: number;
  irrelevant: number;
  batch_size: number;
  concurrency: number;
}

type RelevanceFilter = 'all' | 'relevant' | 'rejected' | 'unscored';
type SortKey = 'newest' | 'relevance' | 'trending';

const PAGE_SIZE = 10;

function statusChip(status?: string) {
  if (status === 'relevant') return { status: 'approved' as const, label: 'Relevant' };
  if (status === 'reference' || status === 'irrelevant') return { status: 'rejected' as const, label: 'Rejected' };
  if (status === 'screening') return { status: 'running' as const, label: 'Screening' };
  if (status === 'scored') return { status: 'waiting' as const, label: 'Not yet screened' };
  return { status: 'pending' as const, label: 'New' };
}

function fitLabel(score?: number | null, ai?: number | null): string {
  if (typeof ai === 'number') {
    if (ai >= 4) return 'Strong fit';
    if (ai >= 3) return 'Relevant';
    return 'Rejected';
  }
  if (score == null || Number.isNaN(Number(score))) return 'Unscored';
  const n = Number(score);
  const pct = n <= 1 ? n * 100 : n;
  if (pct >= 60) return 'Strong fit';
  if (pct >= 30) return 'Borderline';
  return 'Weak fit';
}

function relevanceRank(a: ArticleRow): number {
  if (typeof a.ai_relevance === 'number' && a.ai_relevance >= 1 && a.ai_relevance <= 5) {
    return a.ai_relevance;
  }
  const s = Number(a.relevance_score);
  if (!Number.isNaN(s)) return s <= 1 ? s * 5 : s;
  return 0;
}

function statusToApiParam(filter: RelevanceFilter): string | null {
  if (filter === 'relevant') return 'relevant';
  if (filter === 'rejected') return 'irrelevant';
  if (filter === 'unscored') return 'scored';
  return null;
}

function formatTopic(key: string): string {
  return key
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function NewsFeedPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [category, setCategory] = useState('');
  const [topicKey, setTopicKey] = useState('');
  const [relevanceFilter, setRelevanceFilter] = useState<RelevanceFilter>('relevant');
  const [sortBy, setSortBy] = useState<SortKey>('relevance');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [batchCommand, setBatchCommand] = useState<'unscored' | 'relevant' | null>(null);
  const [showHow, setShowHow] = useState(false);
  const [draftTarget, setDraftTarget] = useState<ArticleRow | null>(null);
  const [draftPhase, setDraftPhase] = useState<DraftPhase>('confirm');
  const [draftStep, setDraftStep] = useState(0);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [draftJobId, setDraftJobId] = useState<string | null>(null);
  const { job: draftJob, isComplete: draftJobComplete, isFailed: draftJobFailed } =
    useJobPolling(draftJobId);

  const params = new URLSearchParams({ limit: '100' });
  if (category) params.set('category', category);
  const statusParam = statusToApiParam(relevanceFilter);
  if (statusParam) params.set('status', statusParam);

  const { data, isLoading, isError, refetch, isFetching } = useApiQuery<
    ApiEnvelope<ArticlesPayload | ArticleRow[]>
  >(['articles', category || 'all', relevanceFilter], `/articles?${params.toString()}`);

  const { data: categoriesData } = useApiQuery<
    ApiEnvelope<{ items?: CategoryRow[]; total?: number }>
  >(['article-categories'], '/articles/categories');

  const { data: trendsData } = useApiQuery<
    ApiEnvelope<{ items?: TrendRow[]; total?: number }>
  >(['article-trends'], '/articles/trends?limit=40');

  const { data: screeningData, refetch: refetchScreening } = useApiQuery<
    ApiEnvelope<ScreeningStatusPayload>
  >(['article-screening-status'], '/articles/screening-status', {
    staleTime: 0,
    refetchInterval: (query) => (query.state.data?.data?.active ? 2500 : false),
  });

  const screeningStatus = screeningData?.data;
  const screeningJob = screeningStatus?.job;
  const screeningActive = Boolean(screeningStatus?.active);
  const screeningCompleted = Number(screeningJob?.result?.completed || 0);
  const screeningTotal = Number(screeningJob?.result?.total || screeningJob?.payload?.batch_size || 0);

  const articles: ArticleRow[] = useMemo(() => {
    const payload = data?.data;
    return Array.isArray(payload) ? payload : (payload?.items ?? []);
  }, [data]);

  const total = useMemo(() => {
    const payload = data?.data;
    return Array.isArray(payload) ? payload.length : (payload?.total ?? articles.length);
  }, [data, articles.length]);

  const categories = useMemo(() => {
    const all = categoriesData?.data?.items ?? [];
    return all.filter((c) => c.count >= 1).slice(0, 12);
  }, [categoriesData]);

  const trends = useMemo(() => {
    const items = trendsData?.data?.items ?? [];
    return [...items].sort(
      (a, b) => Number(b.momentum || 0) - Number(a.momentum || 0)
    );
  }, [trendsData]);

  const momentumByTopic = useMemo(() => {
    const map = new Map<string, number>();
    for (const t of trends) {
      map.set(t.topic_key.toLowerCase(), Number(t.momentum || 0));
    }
    return map;
  }, [trends]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let list = articles.filter((a) => {
      if (topicKey) {
        const cat = (a.category || '').toLowerCase();
        if (cat !== topicKey.toLowerCase() && !cat.includes(topicKey.toLowerCase())) {
          return false;
        }
      }
      if (!q) return true;
      return (
        a.title.toLowerCase().includes(q) ||
        (a.source_name || '').toLowerCase().includes(q) ||
        (a.summary || '').toLowerCase().includes(q) ||
        (a.category || '').toLowerCase().includes(q)
      );
    });

    list = [...list].sort((a, b) => {
      if (sortBy === 'relevance') {
        const diff = relevanceRank(b) - relevanceRank(a);
        if (diff !== 0) return diff;
      }
      if (sortBy === 'trending') {
        const ma = momentumByTopic.get((a.category || '').toLowerCase()) || 0;
        const mb = momentumByTopic.get((b.category || '').toLowerCase()) || 0;
        if (mb !== ma) return mb - ma;
        const rd = relevanceRank(b) - relevanceRank(a);
        if (rd !== 0) return rd;
      }
      const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
      const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
      return tb - ta;
    });

    return list;
  }, [articles, search, topicKey, sortBy, momentumByTopic]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageItems = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  const setRelevanceFilterAndReset = (key: RelevanceFilter) => {
    setRelevanceFilter(key);
    setPage(0);
  };

  const invalidateArticles = () => {
    queryClient.invalidateQueries({ queryKey: ['articles'] });
    queryClient.invalidateQueries({ queryKey: ['learning'] });
    queryClient.invalidateQueries({ queryKey: ['article-trends'] });
    queryClient.invalidateQueries({ queryKey: ['article-categories'] });
  };

  const setRelevance = async (id: string, status: 'relevant' | 'irrelevant') => {
    setBusy(`rel-${id}`);
    try {
      await apiClient.patch(`/articles/${id}/relevance`, { status });
      toast.success(
        status === 'relevant'
          ? 'Marked relevant — brand profile updated'
          : 'Marked rejected — brand profile updated'
      );
      invalidateArticles();
    } catch {
      toast.error('Could not update relevance');
    } finally {
      setBusy(null);
    }
  };

  const hideArticle = async (id: string) => {
    setBusy(`hide-${id}`);
    try {
      await apiClient.patch(`/articles/${id}/hide`, { hidden: true });
      toast.success('Hidden — still counts toward learning, just off your feed');
      invalidateArticles();
    } catch {
      toast.error('Could not hide story');
    } finally {
      setBusy(null);
    }
  };

  const openDraftDialog = (row: ArticleRow) => {
    setDraftTarget(row);
    setDraftPhase('confirm');
    setDraftStep(0);
    setDraftError(null);
  };

  const closeDraftDialog = () => {
    if (draftPhase === 'writing' || draftPhase === 'opening') return;
    setDraftTarget(null);
    setDraftPhase('confirm');
    setDraftStep(0);
    setDraftError(null);
  };

  useEffect(() => {
    if (draftPhase !== 'writing') return;
    const t = window.setTimeout(() => setDraftStep((s) => Math.max(s, 1)), 1200);
    return () => window.clearTimeout(t);
  }, [draftPhase]);

  const runCreateDraft = async () => {
    if (!draftTarget) return;
    const row = draftTarget;
    const lowFit = row.status === 'irrelevant';
    setBusy(`gen-${row.id}`);
    setDraftPhase('writing');
    setDraftStep(0);
    setDraftError(null);
    try {
      const res = await apiClient.post<ApiEnvelope<{ job_id: string; status: string }>>(
        `/articles/${row.id}/generate-draft`,
        { content_type: 'educational', force: lowFit }
      );
      const jobId = res.data?.data?.job_id;
      if (!jobId) throw new Error('No job id returned');
      setDraftJobId(jobId);
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { error?: string; detail?: string } }; message?: string };
      const apiMsg =
        ax.response?.data?.error ||
        ax.response?.data?.detail ||
        ax.message ||
        'Couldn’t write this draft. Try again in a moment.';
      setDraftPhase('error');
      setDraftError(apiMsg);
      toast.error('Draft failed');
      setBusy(null);
    }
  };

  // Draft generation now runs as a background Job — this reacts once
  // useJobPolling sees it finish, replacing the old blocking await.
  useEffect(() => {
    if (!draftJobId) return;
    if (draftJobFailed) {
      setDraftPhase('error');
      setDraftError(draftJob?.error_message || 'Couldn’t write this draft. Try again in a moment.');
      toast.error('Draft failed');
      setBusy(null);
      setDraftJobId(null);
      return;
    }
    if (draftJobComplete) {
      const draft = draftJob?.result as Draft | undefined;
      setDraftStep(2);
      setDraftPhase('opening');
      queryClient.invalidateQueries({ queryKey: ['drafts'] });
      toast.success('Draft ready — opening editor');
      setBusy(null);
      setDraftJobId(null);
      window.setTimeout(() => {
        if (draft?.id) navigate(routes.draft(draft.id));
        else navigate(routes.drafts);
      }, 450);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftJobComplete, draftJobFailed, draftJobId]);

  const runScreeningBatch = async (mode: 'unscored' | 'relevant') => {
    setBatchCommand(mode);
    try {
      const endpoint = mode === 'relevant' ? '/articles/rescore-relevant' : '/articles/rescore-new';
      const res = await apiClient.post<
        ApiEnvelope<{ queued?: number; already_active?: boolean; job_id?: string | null }>
      >(endpoint);
      const payload = res.data.data;
      if (payload?.already_active) {
        toast.info('A screening batch is already running');
      } else if ((payload?.queued || 0) > 0) {
        toast.success(
          mode === 'relevant'
            ? `Queued ${payload?.queued} relevant stories for rescoring`
            : `Queued ${payload?.queued} unscored stories for screening`
        );
      } else {
        toast.info(mode === 'relevant' ? 'No relevant stories to rescore' : 'No unscored stories waiting');
      }
      await refetchScreening();
      invalidateArticles();
    } catch {
      toast.error('Could not start scoring');
    } finally {
      setBatchCommand(null);
    }
  };

  useEffect(() => {
    if (screeningJob?.status !== 'complete') return;
    invalidateArticles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screeningJob?.id, screeningJob?.status]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-10 w-full max-w-lg" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (isError) {
    return <ErrorState message="Unable to load articles." onRetry={refetch} />;
  }

  const filters: { key: RelevanceFilter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'relevant', label: 'Relevant' },
    { key: 'rejected', label: 'Rejected' },
    { key: 'unscored', label: 'Unscored' },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        title="News"
        description="See what’s trending, sort by fit, and draft from the stories that match your brand."
        actions={
          <div className="flex flex-col items-end gap-1.5">
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => runScreeningBatch('unscored')}
                disabled={screeningActive || batchCommand !== null || Number(screeningStatus?.pending || 0) === 0}
              >
                {(screeningActive && screeningJob?.payload?.mode === 'unscored') || batchCommand === 'unscored' ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : null}
                {screeningActive && screeningJob?.payload?.mode === 'unscored'
                  ? 'Screening…'
                  : 'Screen next 100'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => runScreeningBatch('relevant')}
                disabled={screeningActive || batchCommand !== null || Number(screeningStatus?.relevant || 0) === 0}
              >
                {(screeningActive && screeningJob?.payload?.mode === 'relevant') || batchCommand === 'relevant' ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : null}
                {screeningActive && screeningJob?.payload?.mode === 'relevant'
                  ? 'Rescoring…'
                  : 'Rescore relevant'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  refetch();
                  refetchScreening();
                  invalidateArticles();
                }}
                disabled={isFetching}
              >
                <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
                Refresh
              </Button>
            </div>
            {screeningActive && screeningTotal > 0 ? (
              <p className="text-xs text-muted-foreground">
                {screeningJob?.payload?.mode === 'relevant' ? 'Rescoring' : 'Screening'}{' '}
                {screeningCompleted}/{screeningTotal}
                {screeningJob?.payload?.mode === 'unscored'
                  ? ` · ${screeningStatus?.pending ?? screeningJob?.result?.waiting ?? 0} waiting`
                  : ''}
              </p>
            ) : Number(screeningStatus?.pending || 0) > 0 ? (
              <p className="text-xs text-muted-foreground">
                {screeningStatus?.pending} waiting · runs only when commanded
              </p>
            ) : null}
          </div>
        }
      />

      <div>
        <button
          type="button"
          className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          onClick={() => setShowHow((v) => !v)}
        >
          <HelpCircle className="h-3.5 w-3.5" />
          How relevance works
          {showHow ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </button>
        {showHow && (
          <div className="mt-2 max-w-xl space-y-1.5 rounded-lg border border-border bg-card px-3 py-2.5 text-sm text-muted-foreground">
            <p>
              Each command screens up to 100 waiting stories against your brand profile. The AI
              receives the title, summary and available article excerpt. Useful score 3–5
              opportunities become Relevant; everything else is Rejected.
            </p>
            <p>
              Batches stop when complete. Run the next 100 when you are ready, or use Rescore
              relevant to explicitly reassess existing recommendations.
            </p>
            <p>
              Use Yes / No to correct a call — that updates Learning and your Brand profile.
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {filters.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setRelevanceFilterAndReset(f.key)}
              className={cn(
                'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                relevanceFilter === f.key
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              {f.label}
              {f.key === relevanceFilter ? ` · ${total}` : ''}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="h-9 rounded-md border border-border bg-background px-2.5 text-sm"
            value={sortBy}
            onChange={(e) => {
              setSortBy(e.target.value as SortKey);
              setPage(0);
            }}
            aria-label="Sort stories"
          >
            <option value="newest">Sort: Newest</option>
            <option value="relevance">Sort: Relevance</option>
            <option value="trending">Sort: Trending</option>
          </select>
          <Input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            placeholder="Search stories…"
            className="w-full max-w-xs sm:w-56"
            aria-label="Search stories"
          />
          <select
            className="h-9 rounded-md border border-border bg-background px-2.5 text-sm"
            value={category}
            onChange={(e) => {
              const v = e.target.value;
              setCategory(v);
              setTopicKey(v);
              setPage(0);
            }}
            aria-label="Topic filter"
          >
            <option value="">All topics</option>
            {categories.map((c) => (
              <option key={c.category} value={c.category}>
                {c.category} ({c.count})
              </option>
            ))}
          </select>
          {(topicKey || category) && (
            <button
              type="button"
              className="text-xs text-muted-foreground hover:text-foreground"
              onClick={() => {
                setTopicKey('');
                setCategory('');
                setPage(0);
              }}
            >
              Clear topic filter: {formatTopic(topicKey || category)}
            </button>
          )}
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={<Newspaper className="h-8 w-8" />}
          title="No stories here"
          description={
            relevanceFilter === 'relevant'
              ? 'Mark a story as Relevant, or switch to All.'
              : search || topicKey
                ? 'Try a different search or clear the topic filter.'
                : 'Run a source to pull in articles.'
          }
          actionLabel={relevanceFilter !== 'all' || topicKey ? 'Show all' : 'Open sources'}
          onAction={() => {
            if (topicKey || category) {
              setTopicKey('');
              setCategory('');
              setPage(0);
            } else if (relevanceFilter !== 'all') {
              setRelevanceFilterAndReset('all');
            } else {
              navigate(routes.sources);
            }
          }}
        />
      ) : (
        <div className="space-y-3">
          <ul className="divide-y divide-border overflow-hidden rounded-[var(--radius)] border border-border bg-card">
            {pageItems.map((a) => {
              const chip = statusChip(a.status);
              const relBusy = busy === `rel-${a.id}`;
              const hideBusy = busy === `hide-${a.id}`;
              const score = typeof a.ai_relevance === 'number' ? a.ai_relevance : null;
              return (
                <li
                  key={a.id}
                  className="flex flex-col gap-3 p-4 transition-colors hover:bg-hover/60 sm:flex-row sm:items-center sm:gap-4"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusChip status={chip.status} label={chip.label} />
                      <span className="text-xs text-muted-foreground">
                        {fitLabel(a.relevance_score, a.ai_relevance)}
                      </span>
                      {score != null && (
                        <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
                          <Gauge className="h-3 w-3" />
                          {score}/5
                        </span>
                      )}
                      {a.admin_override?.status && (
                        <span className="text-xs text-muted-foreground">· You decided</span>
                      )}
                    </div>
                    {a.url ? (
                      <a
                        href={a.url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-1.5 block font-medium leading-snug text-foreground hover:underline"
                      >
                        {a.title}
                      </a>
                    ) : (
                      <p className="mt-1.5 font-medium leading-snug text-foreground">{a.title}</p>
                    )}
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {[a.source_name, a.category, a.sentiment?.label].filter(Boolean).join(' · ') ||
                        '—'}
                    </p>
                    {(a.status === 'relevant' || a.status === 'irrelevant') &&
                      a.score_json?.reason && (
                        <p className="mt-1.5 line-clamp-2 text-sm text-muted-foreground">
                          {a.score_json.reason}
                        </p>
                      )}
                  </div>

                  <div className="flex shrink-0 flex-wrap items-center gap-1.5 sm:justify-end">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      disabled={hideBusy}
                      title="Hide from feed — still counts toward learning"
                      onClick={() => hideArticle(a.id)}
                    >
                      {hideBusy ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <EyeOff className="h-3.5 w-3.5" />
                      )}
                    </Button>
                    <Button
                      size="sm"
                      variant={a.status === 'relevant' ? 'default' : 'outline'}
                      disabled={relBusy || a.status === 'relevant'}
                      title="Mark relevant"
                      onClick={() => setRelevance(a.id, 'relevant')}
                    >
                      <ThumbsUp className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">Yes</span>
                    </Button>
                    <Button
                      size="sm"
                      variant={a.status === 'irrelevant' ? 'destructive' : 'outline'}
                      disabled={relBusy || a.status === 'irrelevant'}
                      title="Mark rejected"
                      onClick={() => setRelevance(a.id, 'irrelevant')}
                    >
                      <ThumbsDown className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">No</span>
                    </Button>
                    <Button
                      size="sm"
                      disabled={Boolean(busy?.startsWith('gen-'))}
                      onClick={() => openDraftDialog(a)}
                      title="Write a LinkedIn draft from this story"
                    >
                      {busy === `gen-${a.id}` ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Sparkles className="h-3.5 w-3.5" />
                      )}
                      {busy === `gen-${a.id}` ? 'Writing…' : 'Draft'}
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              Page {safePage + 1} of {pageCount}
              {filtered.length !== total ? ` · ${filtered.length} shown` : ''}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={safePage <= 0}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                disabled={safePage >= pageCount - 1}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}

      <Dialog
        open={Boolean(draftTarget)}
        onOpenChange={(open) => {
          if (!open) closeDraftDialog();
        }}
      >
        <DialogContent
          className="max-w-md"
          onPointerDownOutside={(e) => {
            if (draftPhase === 'writing' || draftPhase === 'opening') e.preventDefault();
          }}
          onEscapeKeyDown={(e) => {
            if (draftPhase === 'writing' || draftPhase === 'opening') e.preventDefault();
          }}
        >
          {draftTarget && draftPhase === 'confirm' && (
            <>
              <DialogHeader>
                <DialogTitle>Write a LinkedIn draft?</DialogTitle>
                <DialogDescription>
                  AI will turn this story into a post using your brand profile. You’ll land on the
                  draft editor next.
                </DialogDescription>
              </DialogHeader>

              <div className="rounded-[var(--radius)] border border-border bg-muted/40 p-3">
                <p className="text-sm font-medium leading-snug text-foreground">
                  {draftTarget.title}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {[draftTarget.source_name, draftTarget.category].filter(Boolean).join(' · ') ||
                    'News story'}
                </p>
              </div>

              {draftTarget.status === 'irrelevant' && (
                <p className="rounded-[var(--radius)] border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-100">
                  This story is rejected. You can still draft it if you want.
                </p>
              )}

              <ol className="space-y-2.5 text-sm">
                <li className="flex gap-2.5">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Sparkles className="h-3 w-3" />
                  </span>
                  <span>
                    <span className="font-medium text-foreground">Write</span>
                    <span className="text-muted-foreground"> — hook, body, CTA & hashtags</span>
                  </span>
                </li>
                <li className="flex gap-2.5">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <FileText className="h-3 w-3" />
                  </span>
                  <span>
                    <span className="font-medium text-foreground">Review</span>
                    <span className="text-muted-foreground"> — edit, approve, or rewrite</span>
                  </span>
                </li>
                <li className="flex gap-2.5">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <ImageIcon className="h-3 w-3" />
                  </span>
                  <span>
                    <span className="font-medium text-foreground">Visuals</span>
                    <span className="text-muted-foreground"> — generate automatically with your draft</span>
                  </span>
                </li>
              </ol>

              <div className="flex justify-end gap-2 pt-1">
                <Button variant="outline" onClick={closeDraftDialog}>
                  Cancel
                </Button>
                <Button onClick={runCreateDraft}>
                  <Sparkles className="h-3.5 w-3.5" />
                  Write draft
                </Button>
              </div>
            </>
          )}

          {draftTarget && (draftPhase === 'writing' || draftPhase === 'opening') && (
            <>
              <DialogHeader>
                <DialogTitle>
                  {draftPhase === 'opening' ? 'Opening your draft…' : 'Writing your draft…'}
                </DialogTitle>
                <DialogDescription>
                  Usually takes a few seconds. Stay on this page — we’ll open the editor when it’s
                  ready.
                </DialogDescription>
              </DialogHeader>

              <div className="rounded-[var(--radius)] border border-border bg-muted/40 p-3">
                <p className="line-clamp-2 text-sm font-medium leading-snug">{draftTarget.title}</p>
              </div>

              <ul className="space-y-3">
                {DRAFT_STEPS.map((step, index) => {
                  const done = draftStep > index || draftPhase === 'opening';
                  const active = draftStep === index && draftPhase === 'writing';
                  return (
                    <li key={step.id} className="flex items-center gap-3 text-sm">
                      <span
                        className={cn(
                          'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border',
                          done
                            ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                            : active
                              ? 'border-primary/40 bg-primary/10 text-primary'
                              : 'border-border text-muted-foreground'
                        )}
                      >
                        {done ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : active ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <span className="text-xs">{index + 1}</span>
                        )}
                      </span>
                      <span
                        className={cn(
                          done || active ? 'text-foreground' : 'text-muted-foreground',
                          active && 'font-medium'
                        )}
                      >
                        {step.label}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </>
          )}

          {draftTarget && draftPhase === 'error' && (
            <>
              <DialogHeader>
                <DialogTitle>Draft didn’t finish</DialogTitle>
                <DialogDescription>{draftError}</DialogDescription>
              </DialogHeader>
              <div className="flex justify-end gap-2 pt-1">
                <Button variant="outline" onClick={closeDraftDialog}>
                  Close
                </Button>
                <Button onClick={runCreateDraft}>Try again</Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
