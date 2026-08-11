import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  Check,
  ExternalLink,
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
  TrendingUp,
} from 'lucide-react';
import { useApiQuery } from '@/hooks/useApiQuery';
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
  source_name?: string | null;
  category?: string | null;
  relevance_score?: number | null;
  ai_relevance?: number | null;
  admin_override?: { status?: string } | null;
  sentiment?: SentimentInfo | null;
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

type RelevanceFilter = 'all' | 'relevant' | 'not_relevant' | 'unscored';
type SortKey = 'newest' | 'relevance' | 'trending';

const PAGE_SIZE = 10;

function statusChip(status?: string) {
  if (status === 'relevant') return { status: 'approved' as const, label: 'Relevant' };
  if (status === 'irrelevant') return { status: 'rejected' as const, label: 'Not relevant' };
  if (status === 'scored') return { status: 'waiting' as const, label: 'Scoring…' };
  return { status: 'pending' as const, label: 'New' };
}

function fitLabel(score?: number | null, ai?: number | null): string {
  if (typeof ai === 'number') {
    if (ai >= 3) return 'Strong fit';
    if (ai >= 2) return 'Borderline';
    return 'Weak fit';
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
  if (filter === 'not_relevant') return 'irrelevant';
  if (filter === 'unscored') return 'raw';
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
  const [relevanceFilter, setRelevanceFilter] = useState<RelevanceFilter>('all');
  const [sortBy, setSortBy] = useState<SortKey>('newest');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [enriching, setEnriching] = useState(false);
  const [showHow, setShowHow] = useState(false);
  const [showAllTrends, setShowAllTrends] = useState(false);
  const [draftTarget, setDraftTarget] = useState<ArticleRow | null>(null);
  const [draftPhase, setDraftPhase] = useState<DraftPhase>('confirm');
  const [draftStep, setDraftStep] = useState(0);
  const [draftError, setDraftError] = useState<string | null>(null);

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

  const hotCategories = useMemo(() => {
    return [...categories]
      .map((c) => ({
        ...c,
        momentum: momentumByTopic.get(c.category.toLowerCase()) || c.count,
      }))
      .sort((a, b) => b.momentum - a.momentum)
      .slice(0, 8);
  }, [categories, momentumByTopic]);

  const visibleTrends = showAllTrends ? trends : trends.slice(0, 8);

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

  const selectTopic = (key: string) => {
    const next = topicKey === key ? '' : key;
    setTopicKey(next);
    // Prefer API category filter when it matches a known category
    const known = categories.some((c) => c.category.toLowerCase() === key.toLowerCase());
    setCategory(known && next ? key : '');
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
          : 'Marked not relevant — brand profile updated'
      );
      invalidateArticles();
    } catch {
      toast.error('Could not update relevance');
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
      const res = await apiClient.post<ApiEnvelope<Draft>>(
        `/articles/${row.id}/generate-draft`,
        { content_type: 'educational', force: lowFit }
      );
      setDraftStep(2);
      setDraftPhase('opening');
      queryClient.invalidateQueries({ queryKey: ['drafts'] });
      const draft = res.data.data;
      toast.success('Draft ready — opening editor');
      await new Promise((r) => setTimeout(r, 450));
      if (draft?.id) navigate(routes.draft(draft.id));
      else navigate(routes.drafts);
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
    } finally {
      setBusy(null);
    }
  };

  const runEnrichment = async () => {
    setEnriching(true);
    try {
      const res = await apiClient.post<ApiEnvelope<{ queued?: number }>>('/articles/rescore-new');
      toast.success(`Queued ${res.data.data?.queued ?? 0} stories for scoring`);
      invalidateArticles();
    } catch {
      toast.error('Could not start scoring');
    } finally {
      setEnriching(false);
    }
  };

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
    { key: 'not_relevant', label: 'Not relevant' },
    { key: 'unscored', label: 'Unscored' },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        title="News"
        description="See what’s trending, sort by fit, and draft from the stories that match your brand."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={runEnrichment} disabled={enriching}>
              {enriching ? 'Scoring…' : 'Rescore'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                refetch();
                invalidateArticles();
              }}
              disabled={isFetching}
            >
              <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
              Refresh
            </Button>
          </div>
        }
      />

      {/* Trending rail */}
      <section className="space-y-3 rounded-[var(--radius)] border border-border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold text-foreground">Trending now</h2>
          </div>
          {trends.length > 8 && (
            <button
              type="button"
              className="text-xs font-medium text-accent hover:underline"
              onClick={() => setShowAllTrends((v) => !v)}
            >
              {showAllTrends ? 'Show less' : `See all trends (${trends.length})`}
            </button>
          )}
        </div>

        {hotCategories.length > 0 && (
          <div>
            <p className="mb-1.5 text-xs text-muted-foreground">Hot categories</p>
            <div className="flex flex-wrap gap-1.5">
              {hotCategories.map((c) => {
                const active = category === c.category || topicKey === c.category;
                return (
                  <button
                    key={c.category}
                    type="button"
                    onClick={() => selectTopic(c.category)}
                    className={cn(
                      'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                      active
                        ? 'bg-accent text-accent-foreground'
                        : 'bg-muted text-muted-foreground hover:bg-hover hover:text-foreground'
                    )}
                  >
                    {formatTopic(c.category)}
                    <span className="ml-1 opacity-70">{c.count}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {trends.length > 0 ? (
          <div>
            <p className="mb-1.5 text-xs text-muted-foreground">Topic momentum</p>
            <div className="flex flex-wrap gap-1.5">
              {visibleTrends.map((t) => {
                const active = topicKey === t.topic_key;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => selectTopic(t.topic_key)}
                    title={t.window_label || undefined}
                    className={cn(
                      'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition-colors',
                      active
                        ? 'border-accent bg-accent/10 text-foreground'
                        : 'border-border bg-background text-muted-foreground hover:border-accent/40 hover:text-foreground'
                    )}
                  >
                    <span className="font-medium">{formatTopic(t.topic_key)}</span>
                    <span className="tabular-nums opacity-70">
                      {t.article_count != null ? `${t.article_count}` : '—'}
                      {typeof t.momentum === 'number' ? ` · ${Math.round(t.momentum)}` : ''}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            Trends appear after sources ingest. Run a source, then refresh.
          </p>
        )}

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
      </section>

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
              Stories are scored against your brand profile and auto-sorted into Relevant or Not
              relevant. Trends show which topics are moving in your feed.
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
              const trendHit = momentumByTopic.get((a.category || '').toLowerCase());
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
                      {typeof trendHit === 'number' && trendHit > 0 && (
                        <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
                          <TrendingUp className="h-3 w-3" />
                          {Math.round(trendHit)}
                        </span>
                      )}
                      {a.admin_override?.status && (
                        <span className="text-xs text-muted-foreground">· You decided</span>
                      )}
                    </div>
                    <p className="mt-1.5 font-medium leading-snug text-foreground">{a.title}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {[a.source_name, a.category, a.sentiment?.label].filter(Boolean).join(' · ') ||
                        '—'}
                    </p>
                    {a.summary && (
                      <p className="mt-1.5 line-clamp-2 text-sm text-muted-foreground">{a.summary}</p>
                    )}
                  </div>

                  <div className="flex shrink-0 flex-wrap items-center gap-1.5 sm:justify-end">
                    {a.url && (
                      <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
                        <a href={a.url} target="_blank" rel="noreferrer" aria-label="Open article">
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      </Button>
                    )}
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
                      title="Mark not relevant"
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
                  This story is marked not relevant. You can still draft it if you want.
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
                    <span className="text-muted-foreground"> — generate images on the draft page</span>
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
