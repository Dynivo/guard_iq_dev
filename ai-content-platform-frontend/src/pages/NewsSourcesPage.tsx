import { useCallback, useEffect, useRef, useState } from 'react';
import { useApiQuery } from '@/hooks/useApiQuery';
import { apiClient } from '@/api/client';
import { Card, CardContent } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { Spinner } from '@/components/Spinner';
import { ErrorState } from '@/components/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { Input } from '@/design-system/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/design-system/ui/dialog';
import { SchedulePicker } from '@/components/SchedulePicker';
import { describeCron } from '@/lib/schedulePresets';
import type { ApiEnvelope } from '@/api/types';
import { Rss, Play, Globe, Loader2, Settings2 } from 'lucide-react';
import { toast } from 'sonner';

interface SourceConfig {
  url?: string;
  feed_url?: string;
  query?: string;
  language?: string;
  country?: string;
  category?: string;
  categories?: string[];
  max_items?: number;
  paid_plan?: boolean;
  api_key?: string;
  api_endpoint?: string;
}

interface SourceRow {
  id: string;
  name: string;
  connector_type?: string;
  type?: string;
  category?: string | null;
  enabled?: boolean;
  status?: string;
  last_fetched_at?: string | null;
  schedule_cron?: string | null;
  credibility_score?: number | null;
  priority?: number | null;
  api_key_name?: string | null;
  rss_url?: string | null;
  api_endpoint?: string | null;
  health?: {
    circuit_state?: string | null;
    failure_rate?: number | null;
    last_error?: string | null;
    healthy?: boolean;
  };
  config_json?: SourceConfig;
  url?: string;
}

type JobStatus = 'pending' | 'running' | 'complete' | 'completed' | 'failed' | 'queued';

interface JobRow {
  id: string;
  type?: string;
  status: JobStatus;
  error_message?: string | null;
  payload?: { source_id?: string } | null;
  result?: {
    fetched?: number;
    saved?: number;
    duplicates?: number;
    source_id?: string;
  } | null;
}

interface RunState {
  jobId: string;
  status: JobStatus;
  error?: string | null;
  result?: JobRow['result'];
}

interface RunResponse {
  job_id: string;
  status: string;
  source_id: string;
  source_name: string;
}

interface RunAllResponse {
  jobs: RunResponse[];
  count: number;
}

interface EditForm {
  name: string;
  enabled: boolean;
  schedule_cron: string;
  feed_url: string;
  query: string;
  language: string;
  country: string;
  categories: string[];
  max_items: string;
  paid_plan: boolean;
}

const TERMINAL = new Set(['complete', 'completed', 'failed']);
const POLL_MS = 1500;
const POLL_MAX_TICKS = 120; // ~3 minutes then stop spinning on stuck jobs

const FALLBACK_NEWSDATA_CATEGORIES = [
  'business',
  'crime',
  'domestic',
  'education',
  'entertainment',
  'environment',
  'food',
  'health',
  'lifestyle',
  'politics',
  'science',
  'sports',
  'technology',
  'top',
  'tourism',
  'world',
  'other',
];

function isActive(status: JobStatus | undefined): boolean {
  return !!status && !TERMINAL.has(status);
}

function runBadge(
  state: RunState | undefined
): { label: string; variant: 'success' | 'warning' | 'destructive' | 'info' } | null {
  if (!state) return null;
  if (state.status === 'pending' || state.status === 'queued') return { label: 'queued', variant: 'warning' };
  if (state.status === 'running') return { label: 'running', variant: 'info' };
  if (state.status === 'failed') return { label: 'failed', variant: 'destructive' };
  if (state.status === 'complete' || state.status === 'completed') return { label: 'fetched', variant: 'success' };
  return null;
}

function selectedCategories(cfg?: SourceConfig): string[] {
  if (!cfg) return [];
  if (Array.isArray(cfg.categories) && cfg.categories.length) {
    return cfg.categories.map((c) => c.toLowerCase());
  }
  if (cfg.category) return [cfg.category.toLowerCase()];
  return [];
}

function sourceDetail(source: SourceRow): string {
  const cfg = source.config_json;
  const connector = source.connector_type || source.type || 'rss';
  if (connector === 'news_api') {
    const cats = selectedCategories(cfg);
    const parts = [
      cfg?.query ? `query: ${cfg.query}` : 'query: (latest all)',
      cfg?.language ? `lang: ${cfg.language}` : null,
      cfg?.country ? `country: ${cfg.country}` : null,
      cats.length ? `categories: ${cats.join(', ')}` : 'categories: (any)',
      cfg?.max_items ? `max: ${cfg.max_items}` : null,
    ].filter(Boolean);
    return parts.join(' · ');
  }
  if (['gnews', 'guardian', 'currents', 'hackernews'].includes(connector)) {
    return source.api_endpoint || cfg?.api_endpoint || cfg?.query || connector;
  }
  return source.rss_url || source.url || cfg?.feed_url || cfg?.url || '';
}

const CATEGORY_LABELS: Record<string, string> = {
  government: 'Government',
  vendor: 'Vendor',
  threat_intelligence: 'Threat Intelligence',
  cloud: 'Cloud',
  ai: 'AI',
  technology: 'Technology',
  developer: 'Developer',
  open_source: 'Open Source',
};

function toEditForm(source: SourceRow): EditForm {
  const cfg = source.config_json || {};
  return {
    name: source.name,
    enabled: source.enabled !== false,
    schedule_cron: source.schedule_cron || '',
    feed_url: cfg.feed_url || cfg.url || '',
    query: cfg.query || '',
    language: cfg.language || 'en',
    country: cfg.country || '',
    categories: selectedCategories(cfg),
    max_items: String(cfg.max_items ?? (source.connector_type === 'news_api' ? 30 : 25)),
    paid_plan: Boolean(cfg.paid_plan),
  };
}

export function NewsSourcesPage() {
  const { data, isLoading, isError, refetch } = useApiQuery<ApiEnvelope<SourceRow[]>>(
    ['sources'],
    '/sources'
  );
  const { data: jobsData } = useApiQuery<ApiEnvelope<JobRow[]>>(['jobs', 'sources-page'], '/jobs');
  const { data: newsdataCats } = useApiQuery<
    ApiEnvelope<{ items?: string[]; max_selected?: number; note?: string }>
  >(['newsdata-categories'], '/sources/newsdata/categories');
  const categoryOptions = newsdataCats?.data?.items?.length
    ? newsdataCats.data.items
    : FALLBACK_NEWSDATA_CATEGORIES;
  const maxSelected = newsdataCats?.data?.max_selected ?? 5;
  const [runStates, setRunStates] = useState<Record<string, RunState>>({});
  const [startingAll, setStartingAll] = useState(false);
  const [startingId, setStartingId] = useState<string | null>(null);
  const [editing, setEditing] = useState<SourceRow | null>(null);
  const [form, setForm] = useState<EditForm | null>(null);
  const [filterText, setFilterText] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterEnabled, setFilterEnabled] = useState<'all' | 'enabled' | 'disabled'>('all');
  const [saving, setSaving] = useState(false);

  const timersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const hydratedRef = useRef(false);

  const clearTimer = useCallback((sourceId: string) => {
    const timer = timersRef.current[sourceId];
    if (timer) {
      clearTimeout(timer);
      delete timersRef.current[sourceId];
    }
  }, []);

  useEffect(() => {
    return () => {
      Object.values(timersRef.current).forEach(clearTimeout);
      timersRef.current = {};
    };
  }, [clearTimer]);

  const pollJob = useCallback(
    (sourceId: string, jobId: string) => {
      clearTimer(sourceId);
      let ticks = 0;
      const tick = async () => {
        ticks += 1;
        try {
          const response = await apiClient.get<ApiEnvelope<JobRow>>(`/jobs/${jobId}`);
          const job = response.data.data;
          setRunStates((prev) => ({
            ...prev,
            [sourceId]: {
              jobId,
              status: job.status,
              error: job.error_message,
              result: job.result,
            },
          }));
          if (TERMINAL.has(job.status)) {
            clearTimer(sourceId);
            refetch();
            return;
          }
          if (ticks >= POLL_MAX_TICKS) {
            setRunStates((prev) => ({
              ...prev,
              [sourceId]: {
                jobId,
                status: 'failed',
                error:
                  'Job still pending after several minutes — restart the worker and try Run again.',
              },
            }));
            clearTimer(sourceId);
            return;
          }
        } catch {
          setRunStates((prev) => ({
            ...prev,
            [sourceId]: { jobId, status: 'failed', error: 'Unable to poll job status' },
          }));
          clearTimer(sourceId);
          return;
        }
        timersRef.current[sourceId] = setTimeout(tick, POLL_MS);
      };
      void tick();
    },
    [clearTimer, refetch]
  );

  useEffect(() => {
    const jobs = jobsData?.data;
    if (!jobs || !Array.isArray(jobs) || hydratedRef.current) return;

    const latestBySource: Record<string, JobRow> = {};
    for (const job of jobs) {
      if (job.type && job.type !== 'ingest') continue;
      const sourceId = job.payload?.source_id || job.result?.source_id;
      if (!sourceId || latestBySource[sourceId]) continue;
      latestBySource[sourceId] = job;
    }

    const restored: Record<string, RunState> = {};
    for (const [sourceId, job] of Object.entries(latestBySource)) {
      restored[sourceId] = {
        jobId: job.id,
        status: job.status,
        error: job.error_message,
        result: job.result,
      };
    }
    if (Object.keys(restored).length) {
      setRunStates((prev) => ({ ...restored, ...prev }));
    }
    hydratedRef.current = true;
    for (const [sourceId, job] of Object.entries(latestBySource)) {
      if (isActive(job.status)) pollJob(sourceId, job.id);
    }
  }, [jobsData, pollJob]);

  const trackRuns = useCallback(
    (jobs: RunResponse[]) => {
      setRunStates((prev) => {
        const next = { ...prev };
        for (const job of jobs) {
          next[job.source_id] = {
            jobId: job.job_id,
            status: (job.status as JobStatus) || 'pending',
          };
        }
        return next;
      });
      for (const job of jobs) pollJob(job.source_id, job.job_id);
    },
    [pollJob]
  );

  const handleRun = async (sourceId: string) => {
    setStartingId(sourceId);
    try {
      const response = await apiClient.post<ApiEnvelope<RunResponse>>(`/sources/${sourceId}/run`);
      trackRuns([response.data.data]);
    } catch {
      setRunStates((prev) => ({
        ...prev,
        [sourceId]: { jobId: '', status: 'failed', error: 'Failed to start ingest' },
      }));
    } finally {
      setStartingId(null);
    }
  };

  const handleRunAll = async () => {
    setStartingAll(true);
    try {
      const response = await apiClient.post<ApiEnvelope<RunAllResponse>>('/sources/run-all');
      trackRuns(response.data.data.jobs ?? []);
    } finally {
      setStartingAll(false);
    }
  };

  const openEdit = (source: SourceRow) => {
    setEditing(source);
    setForm(toEditForm(source));
  };

  const saveEdit = async () => {
    if (!editing || !form) return;
    setSaving(true);
    try {
      const connector = editing.connector_type || editing.type || 'rss';
      const maxItems = Number.parseInt(form.max_items || '50', 10);
      const config_json =
        connector === 'news_api'
          ? {
              ...(editing.config_json || {}),
              query: form.query.trim(),
              language: form.language.trim() || undefined,
              country: form.country.trim() || undefined,
              categories: form.categories.slice(0, maxSelected),
              category: undefined,
              max_items: Number.isFinite(maxItems) ? maxItems : 30,
              paid_plan: form.paid_plan,
            }
          : connector === 'rss' || connector === 'ncsc' || connector === 'msrc'
            ? {
                ...(editing.config_json || {}),
                feed_url: form.feed_url.trim(),
                max_items: Number.isFinite(maxItems) ? maxItems : 25,
              }
            : {
                ...(editing.config_json || {}),
                query: form.query.trim() || (editing.config_json as SourceConfig | undefined)?.query,
                max_items: Number.isFinite(maxItems) ? maxItems : 25,
              };

      await apiClient.patch(`/sources/${editing.id}`, {
        name: form.name.trim(),
        enabled: form.enabled,
        schedule_cron: form.schedule_cron.trim() || null,
        config_json,
      });
      toast.success('Source updated');
      setEditing(null);
      setForm(null);
      refetch();
    } catch {
      toast.error('Failed to update source');
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) return <Spinner />;
  if (isError) return <ErrorState message="Unable to load news sources." onRetry={refetch} />;

  const sources = data?.data ?? [];
  const categories = Array.from(
    new Set(sources.map((s) => (s.category || 'technology').toLowerCase()))
  ).sort();
  const filtered = sources.filter((s) => {
    const cat = (s.category || 'technology').toLowerCase();
    if (filterCategory !== 'all' && cat !== filterCategory) return false;
    if (filterEnabled === 'enabled' && s.enabled === false) return false;
    if (filterEnabled === 'disabled' && s.enabled !== false) return false;
    const q = filterText.trim().toLowerCase();
    if (!q) return true;
    const hay = `${s.name} ${s.connector_type || ''} ${cat} ${sourceDetail(s)}`.toLowerCase();
    return hay.includes(q);
  });
  const grouped = filtered.reduce<Record<string, SourceRow[]>>((acc, source) => {
    const key = (source.category || 'technology').toLowerCase();
    (acc[key] ||= []).push(source);
    return acc;
  }, {});
  const groupOrder = Object.keys(grouped).sort((a, b) => {
    const ai = Object.keys(CATEGORY_LABELS).indexOf(a);
    const bi = Object.keys(CATEGORY_LABELS).indexOf(b);
    return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi) || a.localeCompare(b);
  });
  const anyRunning = Object.values(runStates).some((s) => isActive(s.status)) || startingAll;

  return (
    <div>
      <PageHeader
        title="News Sources"
        description="Enterprise free RSS + API sources — schedule, run, and monitor health"
        actions={
          sources.length > 0 ? (
            <Button onClick={handleRunAll} loading={startingAll} disabled={anyRunning && !startingAll}>
              <Play size={14} className="mr-1" />
              Run all
            </Button>
          ) : undefined
        }
      />

      {sources.length > 0 && (
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            className="sm:max-w-xs"
            placeholder="Search sources…"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
          />
          <select
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
          >
            <option value="all">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABELS[c] || c}
              </option>
            ))}
          </select>
          <select
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={filterEnabled}
            onChange={(e) => setFilterEnabled(e.target.value as 'all' | 'enabled' | 'disabled')}
          >
            <option value="all">All status</option>
            <option value="enabled">Enabled</option>
            <option value="disabled">Disabled</option>
          </select>
          <p className="text-xs text-muted-foreground sm:ml-auto">
            Showing {filtered.length} of {sources.length}
          </p>
        </div>
      )}

      {sources.length === 0 ? (
        <EmptyState
          icon={<Rss className="w-8 h-8 text-navy-400" />}
          title="No sources configured"
          description="Run alembic upgrade / seed_database to load the enterprise free catalog."
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<Rss className="w-8 h-8 text-navy-400" />}
          title="No matching sources"
          description="Try clearing search or category filters."
        />
      ) : (
        <div className="space-y-8">
          {groupOrder.map((cat) => (
            <section key={cat} className="space-y-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {CATEGORY_LABELS[cat] || cat} · {grouped[cat].length}
              </h2>
              <div className="space-y-3">
                {grouped[cat]
                  .slice()
                  .sort((a, b) => (b.priority || 0) - (a.priority || 0) || a.name.localeCompare(b.name))
                  .map((source) => {
                    const connector = source.connector_type || source.type || 'rss';
                    const active = source.enabled !== false && source.status !== 'inactive';
                    const detail = sourceDetail(source);
                    const runState = runStates[source.id];
                    const badge = runBadge(runState);
                    const running = startingId === source.id || isActive(runState?.status);
                    const healthy = source.health?.healthy !== false;
                    const fetchCount = runState?.result?.fetched;
                    const saved = runState?.result?.saved;
                    const successRate =
                      fetchCount && fetchCount > 0 && saved != null
                        ? Math.round((saved / fetchCount) * 100)
                        : null;

                    return (
                      <Card key={source.id}>
                        <CardContent className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-lg bg-navy-50 flex items-center justify-center shrink-0">
                            {running ? (
                              <Loader2 size={18} className="text-navy-500 animate-spin" />
                            ) : (
                              <Globe size={18} className="text-navy-500" />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h3 className="font-semibold">{source.name}</h3>
                              <Badge variant={active ? 'success' : 'default'}>
                                {active ? 'enabled' : 'disabled'}
                              </Badge>
                              <Badge>{connector}</Badge>
                              <Badge variant={healthy ? 'success' : 'destructive'}>
                                {healthy ? 'healthy' : 'degraded'}
                              </Badge>
                              {badge && <Badge variant={badge.variant}>{badge.label}</Badge>}
                            </div>
                            {detail && (
                              <p className="text-sm text-[var(--color-text-secondary)] truncate">{detail}</p>
                            )}
                            <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
                              Credibility {source.credibility_score ?? '—'} · Priority{' '}
                              {source.priority ?? '—'} · Schedule: {describeCron(source.schedule_cron)}
                            </p>
                            {source.last_fetched_at && (
                              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                                Last fetched: {new Date(source.last_fetched_at).toLocaleString()}
                              </p>
                            )}
                            {runState?.status === 'failed' && runState.error && (
                              <p className="text-xs text-destructive mt-1 truncate">{runState.error}</p>
                            )}
                            {(runState?.status === 'complete' || runState?.status === 'completed') &&
                              runState.result && (
                                <p className="text-xs text-[var(--color-text-muted)] mt-1">
                                  Saved {runState.result.saved ?? 0} · duplicates{' '}
                                  {runState.result.duplicates ?? 0} · fetched{' '}
                                  {runState.result.fetched ?? 0}
                                  {successRate != null ? ` · save rate ${successRate}%` : ''}
                                </p>
                              )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <Button variant="outline" size="sm" onClick={() => openEdit(source)}>
                              <Settings2 size={14} className="mr-1" />
                              Configure
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              loading={running}
                              disabled={anyRunning && !running}
                              onClick={() => handleRun(source.id)}
                            >
                              <Play size={14} className="mr-1" />
                              {running ? 'Running' : 'Run'}
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
              </div>
            </section>
          ))}
        </div>
      )}

      <Dialog open={!!editing} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Configure source</DialogTitle>
            <DialogDescription>
              Query and categories are optional. Leave both empty to fetch latest news. NewsData free
              plans allow about 10 articles per request (we paginate up to max items). Select up to{' '}
              {maxSelected} categories.
            </DialogDescription>
          </DialogHeader>
          {form && editing && (
            <div className="space-y-3 pt-2">
              <label className="block space-y-1 text-sm">
                <span className="text-muted-foreground">Name</span>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </label>
              {(editing.connector_type === 'news_api' || editing.type === 'news_api') ? (
                <>
                  <label className="block space-y-1 text-sm">
                    <span className="text-muted-foreground">Search query (optional)</span>
                    <Input
                      placeholder="Empty = latest all news"
                      value={form.query}
                      onChange={(e) => setForm({ ...form, query: e.target.value })}
                    />
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="block space-y-1 text-sm">
                      <span className="text-muted-foreground">Language</span>
                      <Input
                        placeholder="en"
                        value={form.language}
                        onChange={(e) => setForm({ ...form, language: e.target.value })}
                      />
                    </label>
                    <label className="block space-y-1 text-sm">
                      <span className="text-muted-foreground">Country</span>
                      <Input
                        placeholder="gb / us"
                        value={form.country}
                        onChange={(e) => setForm({ ...form, country: e.target.value })}
                      />
                    </label>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">
                        Categories (optional, max {maxSelected})
                      </span>
                      <button
                        type="button"
                        className="text-xs text-muted-foreground underline"
                        onClick={() => setForm({ ...form, categories: [] })}
                      >
                        Clear
                      </button>
                    </div>
                    <div className="grid max-h-40 grid-cols-2 gap-2 overflow-y-auto rounded-md border border-border p-2 sm:grid-cols-3">
                      {categoryOptions.map((cat) => {
                        const checked = form.categories.includes(cat);
                        const disabled = !checked && form.categories.length >= maxSelected;
                        return (
                          <label
                            key={cat}
                            className={`flex items-center gap-2 rounded px-1 py-0.5 text-sm ${
                              disabled ? 'opacity-40' : ''
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              disabled={disabled}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setForm({
                                    ...form,
                                    categories: [...form.categories, cat].slice(0, maxSelected),
                                  });
                                } else {
                                  setForm({
                                    ...form,
                                    categories: form.categories.filter((c) => c !== cat),
                                  });
                                }
                              }}
                            />
                            <span className="capitalize">{cat}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="block space-y-1 text-sm">
                      <span className="text-muted-foreground">Max items</span>
                      <Input
                        type="number"
                        min={1}
                        max={100}
                        value={form.max_items}
                        onChange={(e) => setForm({ ...form, max_items: e.target.value })}
                      />
                    </label>
                    <label className="flex items-center gap-2 self-end pb-2 text-sm">
                      <input
                        type="checkbox"
                        checked={form.paid_plan}
                        onChange={(e) => setForm({ ...form, paid_plan: e.target.checked })}
                      />
                      Paid NewsData plan (size up to 50)
                    </label>
                  </div>
                </>
              ) : (
                <>
                  <label className="block space-y-1 text-sm">
                    <span className="text-muted-foreground">Feed URL</span>
                    <Input
                      value={form.feed_url}
                      onChange={(e) => setForm({ ...form, feed_url: e.target.value })}
                    />
                  </label>
                  <label className="block space-y-1 text-sm">
                    <span className="text-muted-foreground">Max items</span>
                    <Input
                      type="number"
                      min={1}
                      max={100}
                      value={form.max_items}
                      onChange={(e) => setForm({ ...form, max_items: e.target.value })}
                    />
                  </label>
                </>
              )}
              <SchedulePicker
                key={editing.id}
                value={form.schedule_cron}
                onChange={(cron) => setForm({ ...form, schedule_cron: cron })}
              />
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
                Enabled
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setEditing(null)}>
                  Cancel
                </Button>
                <Button loading={saving} onClick={saveEdit}>
                  Save
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
