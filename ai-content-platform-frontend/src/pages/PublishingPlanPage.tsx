import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useApiQuery } from '@/hooks/useApiQuery';
import { useJobPolling } from '@/hooks/useJobPolling';
import { apiClient } from '@/api/client';
import type { ApiEnvelope } from '@/api/types';
import { PageHeader } from '@/components/PageHeader';
import { ErrorState } from '@/components/ErrorState';
import { Skeleton } from '@/design-system/ui/skeleton';
import { toast } from 'sonner';
import { MonthlyCalendar } from '@/components/calendar/MonthlyCalendar';
import { PlanCommandBar, type StrategistBriefing } from '@/components/plan';

interface FillEducationalResult {
  generated?: unknown[];
  message?: string;
  plan?: { needs_capture?: Record<string, number> };
}

export function PublishingPlanPage() {
  const queryClient = useQueryClient();
  const [generating, setGenerating] = useState(false);
  const [seedingCalendar, setSeedingCalendar] = useState(false);
  const [clearingCalendar, setClearingCalendar] = useState(false);
  const [autoGenJobId, setAutoGenJobId] = useState<string | null>(null);
  const {
    job: autoGenJob,
    isComplete: autoGenComplete,
    isFailed: autoGenFailed,
  } = useJobPolling(autoGenJobId);

  const briefingQ = useApiQuery<ApiEnvelope<StrategistBriefing>>(
    ['strategist-briefing'],
    '/strategist/briefing'
  );

  const briefing = briefingQ.data?.data;

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['strategist-briefing'] });
    queryClient.invalidateQueries({ queryKey: ['publishing-plan'] });
    queryClient.invalidateQueries({ queryKey: ['publishing-calendar'] });
    queryClient.invalidateQueries({ queryKey: ['drafts'] });
    queryClient.invalidateQueries({ queryKey: ['to-post'] });
  };

  const autoGeneratePosts = async () => {
    setGenerating(true);
    try {
      const res = await apiClient.post<ApiEnvelope<{ job_id: string }>>(
        '/publishing-plan/fill-educational',
        {}
      );
      const jobId = res.data?.data?.job_id;
      if (!jobId) throw new Error('No job id returned');
      setAutoGenJobId(jobId);
    } catch {
      toast.error('Could not generate posts');
      setGenerating(false);
    }
  };

  // Auto Generate now runs as a background Job — was previously a blocking
  // request that looped generating up to 10-15 drafts sequentially.
  useEffect(() => {
    if (!autoGenJobId) return;
    if (autoGenFailed) {
      toast.error(autoGenJob?.error_message || 'Could not generate posts');
      setGenerating(false);
      setAutoGenJobId(null);
      return;
    }
    if (autoGenComplete) {
      const result = (autoGenJob?.result || {}) as FillEducationalResult;
      const n = result.generated?.length ?? 0;
      toast.success(
        n > 0
          ? `${n} educational post(s) generated — approve them in Drafts to schedule.`
          : result.message || 'Educational quota already filled for this window'
      );
      const needs = result.plan?.needs_capture || {};
      const needParts = Object.entries(needs)
        .filter(([, v]) => Number(v) > 0)
        .map(([k, v]) => `${v} ${k.replace(/_/g, ' ')}`);
      if (needParts.length) {
        toast.message(`Still need Capture: ${needParts.join(', ')}`);
      }
      invalidate();
      setGenerating(false);
      setAutoGenJobId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoGenComplete, autoGenFailed, autoGenJobId]);

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
            ? `Removed ${cleared} manual draft(s) from calendar — Auto Generate to fill AI posts`
            : 'No AI plan posts to place yet — Auto Generate first'
      );
      invalidate();
      document.getElementById('calendar')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch {
      toast.error('Could not seed calendar');
    } finally {
      setSeedingCalendar(false);
    }
  };

  const clearCalendar = async () => {
    if (!window.confirm('Unschedule every post from the calendar? Drafts stay in Drafts — nothing is deleted.')) {
      return;
    }
    setClearingCalendar(true);
    try {
      const res = await apiClient.post<ApiEnvelope<{ cleared?: number }>>(
        '/publishing-plan/clear-calendar',
        {}
      );
      const n = res.data?.data?.cleared ?? 0;
      toast.success(n > 0 ? `Cleared ${n} post(s) from the calendar` : 'Calendar was already empty');
      invalidate();
    } catch {
      toast.error('Could not clear calendar');
    } finally {
      setClearingCalendar(false);
    }
  };

  const loading = briefingQ.isLoading;
  const error = briefingQ.isError;

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
        message="Unable to load Plan workspace."
        onRetry={() => {
          briefingQ.refetch();
        }}
      />
    );
  }

  const gaps = briefing.plan_health?.gaps ?? {};
  const planWindow = briefing.plan_health?.window;
  const windowMode = planWindow?.mode || 'fortnight';
  const goal = briefing.strategic_goal;

  return (
    <div className="pb-10">
      <PageHeader
        title="Plan"
        description="AI selects news to match your brand mix, then generates LinkedIn posts + images. Approve a draft in Drafts and it's ready to schedule here."
      />

      <div className="space-y-8">
        <PlanCommandBar
          windowMode={windowMode}
          windowStart={planWindow?.start}
          windowEnd={planWindow?.end}
          daysLeft={briefing.plan_health?.days_left}
          counts={briefing.plan_health?.counts}
          target={briefing.plan_health?.target}
          gaps={gaps}
          generating={generating}
          seedingCalendar={seedingCalendar}
          clearingCalendar={clearingCalendar}
          onAutoGenerate={autoGeneratePosts}
          onSeedCalendar={seedCalendar}
          onClearCalendar={clearCalendar}
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
      </div>
    </div>
  );
}
