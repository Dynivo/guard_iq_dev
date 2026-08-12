import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApiQuery } from '@/hooks/useApiQuery';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/design-system/ui/card';
import { PageHeader } from '@/components/PageHeader';
import { Skeleton } from '@/design-system/ui/skeleton';
import { Button } from '@/design-system/ui/button';
import { WorkflowStageRail, type WorkflowStage } from '@/components/ai/WorkflowStageRail';
import { StatusChip } from '@/components/ai/StatusChip';
import type { ApiEnvelope, Draft, Job } from '@/api/types';
import { routes } from '@/lib/routes';
import {
  CalendarRange,
  Newspaper,
  FileText,
  ListTodo,
  DollarSign,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

function Kpi({
  label,
  value,
  icon,
  hint,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  hint?: string;
}) {
  return (
    <Card className="transition-transform duration-[var(--duration-fast)] hover:-translate-y-0.5">
      <CardContent className="flex items-start gap-3 p-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10 text-accent">
          {icon}
        </div>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold tabular-nums">{value}</p>
          {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
        </div>
      </CardContent>
    </Card>
  );
}

function startOfLocalDay(d = new Date()) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function dayKey(iso?: string | null) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function workWeekLabels() {
  const labels: { key: string; day: string }[] = [];
  const now = startOfLocalDay();
  const daysSinceMonday = (now.getDay() + 6) % 7;
  const monday = new Date(now);
  monday.setDate(now.getDate() - daysSinceMonday);
  for (let i = 0; i < 5; i += 1) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    labels.push({
      key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`,
      day: d.toLocaleDateString(undefined, { weekday: 'short' }),
    });
  }
  return labels;
}

function asList<T>(payload: T[] | { items?: T[] } | undefined | null): T[] {
  if (!payload) return [];
  return Array.isArray(payload) ? payload : (payload.items ?? []);
}

const RUNNING = new Set(['running', 'pending', 'queued', 'generating', 'retrying']);

export function DashboardPage() {
  const navigate = useNavigate();

  const draftsQ = useApiQuery<ApiEnvelope<Draft[] | { items?: Draft[] }>>(
    ['dashboard-drafts'],
    '/drafts',
    { staleTime: 0 }
  );
  const articlesQ = useApiQuery<
    ApiEnvelope<{ items?: unknown[]; total?: number } | unknown[]>
  >(['dashboard-articles'], '/articles?limit=1', { staleTime: 0 });
  const jobsQ = useApiQuery<ApiEnvelope<Job[] | { items?: Job[] }>>(
    ['dashboard-jobs'],
    '/jobs',
    { staleTime: 0 }
  );
  const costQ = useApiQuery<ApiEnvelope<{ total?: number; usage?: Record<string, number> }>>(
    ['dashboard-cost'],
    '/analytics/cost',
    { staleTime: 0 }
  );
  const metricsQ = useApiQuery<
    ApiEnvelope<{ counters?: Record<string, number>; source?: string }>
  >(['dashboard-metrics'], '/analytics/metrics', { staleTime: 0 });
  const queueQ = useApiQuery<ApiEnvelope<{ items?: unknown[]; total?: number } | unknown[]>>(
    ['dashboard-queue'],
    '/queue',
    { staleTime: 0 }
  );
  const planQ = useApiQuery<
    ApiEnvelope<{
      counts?: Record<string, number>;
      target?: Record<string, number>;
      total_count?: number;
      days_left?: number;
      gaps?: Record<string, number>;
    }>
  >(['publishing-plan'], '/publishing-plan?include_ideas=false', { staleTime: 0 });

  const loading = draftsQ.isLoading || articlesQ.isLoading || jobsQ.isLoading;

  const drafts = useMemo(() => asList(draftsQ.data?.data), [draftsQ.data]);
  const jobs = useMemo(() => asList(jobsQ.data?.data), [jobsQ.data]);

  const articleTotal = useMemo(() => {
    const payload = articlesQ.data?.data;
    if (!payload) return 0;
    if (Array.isArray(payload)) return payload.length;
    return Number(payload.total ?? payload.items?.length ?? 0);
  }, [articlesQ.data]);

  const todayStart = startOfLocalDay().getTime();
  const generatedToday = drafts.filter((d) => {
    if (!d.created_at) return false;
    const t = new Date(d.created_at).getTime();
    return !Number.isNaN(t) && t >= todayStart;
  }).length;

  const needsReview = drafts.filter((d) => {
    const s = d.status || 'draft';
    return s === 'pending_review' || s === 'draft';
  }).length;

  const queuePayload = queueQ.data?.data;
  const queueLen = Array.isArray(queuePayload)
    ? queuePayload.length
    : Number(queuePayload?.total ?? queuePayload?.items?.length ?? 0);
  const approvalQueue = Math.max(needsReview, queueLen);

  const runningJobs = jobs.filter((j) => RUNNING.has(String(j.status || '').toLowerCase())).length;
  const failedJobs = jobs.filter((j) => String(j.status || '').toLowerCase() === 'failed').length;
  const cost = Number(costQ.data?.data?.total ?? 0);
  const llmCalls = Number(metricsQ.data?.data?.counters?.llm_calls ?? 0);
  const planTotal = Number(planQ.data?.data?.total_count ?? 0);
  const planTarget = Number(planQ.data?.data?.target?.total ?? 10);
  const planDaysLeft = Number(planQ.data?.data?.days_left ?? 0);
  const planGapSum = Object.values(planQ.data?.data?.gaps ?? {}).reduce(
    (a, b) => a + Number(b || 0),
    0
  );

  const trendSeries = useMemo(() => {
    const labels = workWeekLabels();
    const counts: Record<string, number> = Object.fromEntries(labels.map((l) => [l.key, 0]));
    for (const d of drafts) {
      const key = dayKey(d.created_at);
      if (key && key in counts) counts[key] += 1;
    }
    return labels.map((l) => ({ day: l.day, generated: counts[l.key] }));
  }, [drafts]);

  const hasTrendData = trendSeries.some((r) => r.generated > 0);

  const pipelineStage: WorkflowStage = useMemo(() => {
    const approved = drafts.some((d) => d.status === 'approved' || d.status === 'published');
    const anyDraft = drafts.length > 0;
    if (approved) return 'Visuals';
    if (anyDraft) return 'Draft';
    if (articleTotal > 0) return 'News';
    return 'News';
  }, [drafts, articleTotal]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Live workspace counts from drafts, news, jobs, and analytics."
        actions={
          <Button onClick={() => navigate(routes.plan)}>
            <CalendarRange className="h-4 w-4" />
            Publishing Plan
          </Button>
        }
      />

      <div className="mb-6">
        <p className="mb-2 text-xs font-medium text-muted-foreground">Pipeline position</p>
        <WorkflowStageRail current={pipelineStage} />
      </div>

      <Card
        className="mb-6 cursor-pointer transition-transform duration-[var(--duration-fast)] hover:-translate-y-0.5"
        onClick={() => navigate(routes.plan)}
      >
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-5">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10 text-accent">
              <CalendarRange size={18} />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Fortnight mix</p>
              <p className="text-2xl font-semibold tabular-nums">
                {planTotal}
                <span className="text-base font-normal text-muted-foreground">/{planTarget}</span>
              </p>
              <p className="text-[11px] text-muted-foreground">
                {planDaysLeft} workday{planDaysLeft === 1 ? '' : 's'} left
                {planGapSum ? ` · ${planGapSum} gap${planGapSum === 1 ? '' : 's'}` : ' · on track'}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusChip
              label={`Edu ${planQ.data?.data?.counts?.educational ?? 0}/${planQ.data?.data?.target?.educational ?? 6}`}
            />
            <StatusChip
              label={`Success ${planQ.data?.data?.counts?.success_story ?? 0}/${planQ.data?.data?.target?.success_story ?? 3}`}
            />
            <StatusChip
              label={`Personal ${planQ.data?.data?.counts?.personal_achievement ?? 0}/${planQ.data?.data?.target?.personal_achievement ?? 1}`}
            />
          </div>
        </CardContent>
      </Card>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <Kpi
          label="Generated today"
          value={generatedToday}
          icon={<FileText size={18} />}
          hint={`${drafts.length} drafts total`}
        />
        <Kpi
          label="Approval queue"
          value={approvalQueue}
          icon={<CheckCircle size={18} />}
          hint="Needs review"
        />
        <Kpi label="Articles" value={articleTotal} icon={<Newspaper size={18} />} hint="In news feed" />
        <Kpi
          label="Running jobs"
          value={runningJobs}
          icon={<ListTodo size={18} />}
          hint={`${jobs.length} jobs tracked`}
        />
        <Kpi
          label="Cost (agg.)"
          value={`$${cost.toFixed(2)}`}
          icon={<DollarSign size={18} />}
          hint={llmCalls ? `${llmCalls} LLM calls` : 'From live analytics'}
        />
        <Kpi label="Failures" value={failedJobs} icon={<AlertTriangle size={18} />} hint="Jobs failed" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Drafts this week</CardTitle>
          <CardDescription>
            {hasTrendData
              ? 'Drafts created per day (Mon–Fri, this week).'
              : 'No drafts yet this week — generate from News to populate.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trendSeries}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="day" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="generated"
                stroke="var(--accent)"
                fill="var(--accent)"
                fillOpacity={0.15}
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
