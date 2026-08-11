import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { useApiQuery } from '@/hooks/useApiQuery';
import { apiClient } from '@/api/client';
import type { ApiEnvelope, BrandKit } from '@/api/types';
import { PageHeader } from '@/components/PageHeader';
import { ErrorState } from '@/components/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { Button } from '@/design-system/ui/button';
import { Skeleton } from '@/design-system/ui/skeleton';
import { toast } from 'sonner';
import { routes } from '@/lib/routes';
import { MonthlyCalendar } from '@/components/calendar/MonthlyCalendar';
import {
  StrategistCopilot,
  OpportunityRow,
  OpportunityTimeline,
  filterByBucket,
  PlanCommandBar,
  LinkedInReadyCard,
  ReviewQueueEmpty,
  type ContentOpportunity,
  type StrategistBriefing,
} from '@/components/plan';

export function PublishingPlanPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [bucket, setBucket] = useState('today');
  const [showOpps, setShowOpps] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [seedingCalendar, setSeedingCalendar] = useState(false);
  const [reviewBusy, setReviewBusy] = useState<{
    id: string;
    action: 'approve' | 'reject' | 'regenerate';
  } | null>(null);

  const briefingQ = useApiQuery<ApiEnvelope<StrategistBriefing>>(
    ['strategist-briefing'],
    '/strategist/briefing',
    {
      refetchInterval: (query) => {
        const queue = query.state.data?.data?.review_queue || [];
        const waitingImage = queue.some((d) => d.image_generating && !d.image_url);
        return waitingImage ? 4000 : false;
      },
    }
  );
  const oppsQ = useApiQuery<ApiEnvelope<{ items?: ContentOpportunity[] }>>(
    ['opportunities'],
    '/opportunities?limit=40'
  );
  const brandQ = useApiQuery<ApiEnvelope<BrandKit>>(['brand-kit'], '/brand-kit');

  const briefing = briefingQ.data?.data;
  const opportunities = oppsQ.data?.data?.items ?? [];
  const reviewQueue = briefing?.review_queue ?? [];
  const brand = brandQ.data?.data;

  const counts = useMemo(() => {
    const c: Record<string, number> = { today: 0, this_week: 0, later: 0 };
    for (const o of opportunities) {
      const b = o.timeline_bucket || 'later';
      c[b] = (c[b] || 0) + 1;
    }
    return c;
  }, [opportunities]);

  const visible = useMemo(
    () => filterByBucket(opportunities, bucket),
    [opportunities, bucket]
  );

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['strategist-briefing'] });
    queryClient.invalidateQueries({ queryKey: ['opportunities'] });
    queryClient.invalidateQueries({ queryKey: ['publishing-plan'] });
    queryClient.invalidateQueries({ queryKey: ['publishing-calendar'] });
    queryClient.invalidateQueries({ queryKey: ['drafts'] });
    queryClient.invalidateQueries({ queryKey: ['to-post'] });
  };

  const regeneratePlan = async () => {
    setRegenerating(true);
    try {
      const res = await apiClient.post<
        ApiEnvelope<{
          generated?: unknown[];
          from_capture?: unknown[];
          needs_capture?: Record<string, number>;
          calendar_seeded?: { assigned?: number };
          message?: string;
        }>
      >('/publishing-plan/regenerate', {});
      const n = res.data?.data?.generated?.length ?? 0;
      const seeded = res.data?.data?.calendar_seeded?.assigned ?? 0;
      const needs = res.data?.data?.needs_capture || {};
      const needParts = Object.entries(needs)
        .filter(([, v]) => Number(v) > 0)
        .map(([k, v]) => `${v} ${k.replace(/_/g, ' ')}`);
      toast.success(
        n > 0
          ? `Plan regenerated — ${n} post(s), ${seeded} labeled on calendar`
          : res.data?.data?.message || 'Plan is already filled for this window'
      );
      if (needParts.length) {
        toast.message(`Still need Capture: ${needParts.join(', ')}`);
      }
      invalidate();
      document.getElementById('calendar')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch {
      toast.error('Could not regenerate plan');
    } finally {
      setRegenerating(false);
    }
  };

  const seedCalendar = async () => {
    setSeedingCalendar(true);
    try {
      const res = await apiClient.post<
        ApiEnvelope<{
          assigned?: number;
          skipped?: number;
          cleared_manual?: number;
          message?: string;
        }>
      >('/publishing-plan/seed-calendar', { rebalance: false });
      const n = res.data?.data?.assigned ?? 0;
      const cleared = res.data?.data?.cleared_manual ?? 0;
      toast.success(
        n > 0
          ? `Calendar seeded — ${n} AI plan post(s) labeled`
          : cleared > 0
            ? `Removed ${cleared} manual draft(s) from calendar — Regenerate plan to fill AI posts`
            : 'No AI plan posts to place yet — Regenerate plan first'
      );
      invalidate();
      document.getElementById('calendar')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch {
      toast.error('Could not seed calendar');
    } finally {
      setSeedingCalendar(false);
    }
  };

  const generateLinkedInPost = async (opp: ContentOpportunity) => {
    const articleId = opp.primary_article_id;
    if (!articleId) {
      toast.error('No source available to generate from');
      return;
    }
    setBusyId(opp.id);
    try {
      const res = await apiClient.post<
        ApiEnvelope<{ id?: string; image_generation?: { batch_job_id?: string } }>
      >(`/articles/${articleId}/generate-draft`, {
        content_type: 'educational',
      });
      const draftId = res.data?.data?.id;
      const autoQueued = Boolean(res.data?.data?.image_generation?.batch_job_id);
      if (draftId && !autoQueued) {
        await apiClient.post(`/drafts/${draftId}/images/generate`, { count: 1 });
      }
      toast.success('LinkedIn post ready for review');
      invalidate();
      document.getElementById('linkedin-ready')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch {
      toast.error('Generate failed');
    } finally {
      setBusyId(null);
    }
  };

  const decide = async (opp: ContentOpportunity, action: 'save' | 'ignore') => {
    try {
      await apiClient.post(`/opportunities/${opp.id}/decision`, { action });
      toast.success(action === 'save' ? 'Saved for later' : 'Ignored');
      invalidate();
    } catch {
      toast.error('Could not update decision');
    }
  };

  const onRecommend = async (_oppId: string, articleId?: string) => {
    const match = opportunities.find((o) => o.id === _oppId);
    if (match) {
      await generateLinkedInPost(match);
      return;
    }
    if (!articleId) return;
    setBusyId(_oppId);
    try {
      const res = await apiClient.post<ApiEnvelope<{ id?: string }>>(
        `/articles/${articleId}/generate-draft`,
        { content_type: 'educational' }
      );
      const draftId = res.data?.data?.id;
      if (draftId) {
        await apiClient.post(`/drafts/${draftId}/images/generate`, { count: 1 });
      }
      toast.success('LinkedIn post ready for review');
      invalidate();
    } catch {
      toast.error('Generate failed');
    } finally {
      setBusyId(null);
    }
  };

  const approveDraft = async (id: string) => {
    setReviewBusy({ id, action: 'approve' });
    try {
      await apiClient.post(`/drafts/${id}/approve`, {});
      toast.success('Approved — schedule it below');
      invalidate();
    } catch {
      toast.error('Approve failed');
    } finally {
      setReviewBusy(null);
    }
  };

  const rejectDraft = async (id: string) => {
    setReviewBusy({ id, action: 'reject' });
    try {
      await apiClient.post(`/drafts/${id}/reject`, {
        reason: 'Does not match brand voice',
        category: 'tone',
      });
      toast.success('Rejected');
      invalidate();
    } catch {
      toast.error('Reject failed');
    } finally {
      setReviewBusy(null);
    }
  };

  const regenerateDraft = async (id: string) => {
    setReviewBusy({ id, action: 'regenerate' });
    try {
      await apiClient.post(`/drafts/${id}/regenerate`, { section: 'full' });
      const draft = reviewQueue.find((d) => d.id === id);
      if (draft && !draft.image_url) {
        await apiClient.post(`/drafts/${id}/images/generate`, { count: 1 });
      }
      toast.success('Post regenerated from backend');
      invalidate();
    } catch {
      toast.error('Regenerate failed');
    } finally {
      setReviewBusy(null);
    }
  };

  const loading = briefingQ.isLoading || oppsQ.isLoading;
  const error = briefingQ.isError || oppsQ.isError;

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (error || !briefing) {
    return (
      <ErrorState
        message="Unable to load Content Intelligence workspace."
        onRetry={() => {
          briefingQ.refetch();
          oppsQ.refetch();
        }}
      />
    );
  }

  const gaps = briefing.plan_health?.gaps ?? {};
  const window = briefing.plan_health?.window;
  const windowMode = window?.mode || 'fortnight';
  const authorName = brand?.name || 'Your brand';
  const authorHeadline =
    brand?.services_line || brand?.tagline || 'LinkedIn · Content Intelligence';
  const goal = briefing.strategic_goal;

  return (
    <div className="pb-10">
      <PageHeader
        title="Content Intelligence"
        description="AI selects news to match your brand mix, then generates LinkedIn posts + images. Manual News drafts stay in Drafts — not here."
      />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_min(100%,300px)]">
        <div className="min-w-0 space-y-8">
          <PlanCommandBar
            windowMode={windowMode}
            windowStart={window?.start}
            windowEnd={window?.end}
            daysLeft={briefing.plan_health?.days_left}
            counts={briefing.plan_health?.counts}
            target={briefing.plan_health?.target}
            gaps={gaps}
            regenerating={regenerating}
            seedingCalendar={seedingCalendar}
            onRegenerate={regeneratePlan}
            onSeedCalendar={seedCalendar}
            onCaptureSuccess={() => navigate(`${routes.capture}?content_type=success_story`)}
            onCapturePersonal={() =>
              navigate(`${routes.capture}?content_type=personal_achievement`)
            }
          />

          {goal?.statement && (
            <p className="text-sm leading-relaxed text-muted-foreground">
              <span className="font-medium text-foreground">Goal · </span>
              {goal.statement}
            </p>
          )}

          <section className="space-y-3" id="calendar">
            <MonthlyCalendar title="Publishing calendar" />
          </section>

          <div className="lg:hidden">
            <StrategistCopilot
              data={briefing}
              onRecommend={onRecommend}
              onRegenerate={regeneratePlan}
              regenerating={regenerating}
            />
          </div>

          <section id="linkedin-ready" className="space-y-4 scroll-mt-4">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
                  <Sparkles className="h-5 w-5 text-accent" />
                  LinkedIn-ready posts
                </h2>
                <p className="text-sm text-muted-foreground">
                  Only AI plan posts for this mix (not one-off News drafts). Approve, reject, or regenerate.
                </p>
              </div>
              {reviewQueue.length > 0 && (
                <span className="rounded-full bg-[var(--color-surface)] px-2.5 py-1 text-xs font-medium tabular-nums text-muted-foreground">
                  {reviewQueue.length} to review
                </span>
              )}
            </div>
            {reviewQueue.length === 0 ? (
              <ReviewQueueEmpty onRegenerate={regeneratePlan} regenerating={regenerating} />
            ) : (
              <div className="space-y-5">
                {reviewQueue.map((d) => (
                  <LinkedInReadyCard
                    key={d.id}
                    draft={d}
                    authorName={authorName}
                    authorHeadline={authorHeadline}
                    busy={reviewBusy?.id === d.id ? reviewBusy.action : null}
                    onApprove={approveDraft}
                    onReject={rejectDraft}
                    onRegenerate={regenerateDraft}
                  />
                ))}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <button
              type="button"
              className="flex w-full items-center justify-between rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-left"
              onClick={() => setShowOpps((v) => !v)}
              aria-expanded={showOpps}
            >
              <div>
                <p className="text-sm font-semibold">News opportunities</p>
                <p className="text-xs text-muted-foreground">
                  Optional one-off generate · {opportunities.length} scored for your brand
                </p>
              </div>
              {showOpps ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </button>

            {showOpps && (
              <div className="space-y-4 pt-1">
                <OpportunityTimeline active={bucket} onChange={setBucket} counts={counts} />
                {visible.length === 0 ? (
                  <EmptyState
                    title="No opportunities in this window"
                    description="Score news as relevant, or regenerate the plan from articles already screened."
                    actionLabel="Open news"
                    onAction={() => navigate(routes.news)}
                  />
                ) : (
                  <div className="space-y-3">
                    {visible.map((opp) => (
                      <OpportunityRow
                        key={opp.id}
                        opportunity={opp}
                        busy={busyId === opp.id}
                        onGenerate={generateLinkedInPost}
                        onSave={(o) => decide(o, 'save')}
                        onIgnore={(o) => decide(o, 'ignore')}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>
        </div>

        <div className="hidden lg:block">
          <StrategistCopilot
            data={briefing}
            onRecommend={onRecommend}
            onRegenerate={regeneratePlan}
            regenerating={regenerating}
          />
          <div className="mt-4 px-1">
            <Button
              variant="outline"
              className="w-full"
              size="sm"
              onClick={() => navigate(routes.brand)}
            >
              Brand cadence & mix
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
