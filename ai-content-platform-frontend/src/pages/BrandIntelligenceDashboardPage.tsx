import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Eye,
  FileText,
  ImageIcon,
  Lightbulb,
  MessageSquare,
  RefreshCw,
  Sparkles,
  Target,
  Type,
  Upload,
  Users,
} from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Button } from '@/components/Button';
import { Card, CardContent, CardHeader } from '@/components/Card';
import { Spinner } from '@/components/Spinner';
import { ErrorState } from '@/components/ErrorState';
import { Badge } from '@/design-system/ui/badge';
import {
  getBrandDashboard,
  listBrandProfiles,
  type BrandIntelligenceDashboard,
  type BrandIntelligenceProfile,
} from '@/api/brandIntelligence';
import { routes } from '@/lib/routes';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

type RecItem = { title: string; detail?: string; priority?: number; code?: string };
type QualityPost = {
  post_id?: string;
  title?: string;
  quality_score?: number | null;
  engagement_score?: number | null;
  has_image?: boolean | null;
  word_count?: number | null;
};

function asTopicLabels(value: unknown): string[] {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          const o = item as { label?: unknown; name?: unknown };
          if (o.label != null) return String(o.label);
          if (o.name != null) return String(o.name);
        }
        return '';
      })
      .filter(Boolean);
  }
  if (typeof value === 'string') return [value];
  return [];
}

function asMissingAssets(value: unknown): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(String);
  return [];
}

function asRecommendations(value: unknown): RecItem[] {
  if (!value) return [];
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    if (typeof item === 'string') return { title: item };
    if (item && typeof item === 'object') {
      const o = item as RecItem & { message?: string };
      return {
        title: o.title || o.message || 'Recommendation',
        detail: o.detail && o.detail !== o.title ? o.detail : undefined,
        priority: typeof o.priority === 'number' ? o.priority : undefined,
        code: o.code,
      };
    }
    return { title: String(item) };
  });
}

function num(value: unknown): number | null {
  if (typeof value === 'number' && !Number.isNaN(value)) return value;
  if (typeof value === 'string' && value.trim() && !Number.isNaN(Number(value))) {
    return Number(value);
  }
  return null;
}

/** Normalize 0–1 or 0–100 scores to 0–100 display. */
function score100(value: unknown): number | null {
  const n = num(value);
  if (n == null) return null;
  return n <= 1 ? Math.round(n * 100) : Math.round(n);
}

function scoreLabel(value: unknown): string {
  const s = score100(value);
  return s == null ? '—' : String(s);
}

function humanize(value: unknown): string {
  if (value == null || value === '') return '—';
  if (typeof value !== 'string') return String(value);
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

function splitTone(tone: unknown): string[] {
  if (typeof tone !== 'string' || !tone.trim()) return [];
  return tone
    .split(/[,;/|]/)
    .map((t) => t.trim())
    .filter(Boolean);
}

function healthStatus(overall: number | null): { label: string; variant: 'success' | 'warning' | 'destructive' | 'secondary' } {
  if (overall == null) return { label: 'Not scored', variant: 'secondary' };
  if (overall >= 80) return { label: 'Strong', variant: 'success' };
  if (overall >= 60) return { label: 'Good', variant: 'success' };
  if (overall >= 40) return { label: 'Needs work', variant: 'warning' };
  return { label: 'Weak', variant: 'destructive' };
}

function priorityVariant(priority?: number): 'destructive' | 'warning' | 'secondary' {
  if (priority == null) return 'secondary';
  if (priority <= 20) return 'destructive';
  if (priority <= 40) return 'warning';
  return 'secondary';
}

function assetLabel(key: string): string {
  const map: Record<string, string> = {
    logo: 'Logo',
    brand_guidelines: 'Brand guidelines',
    website: 'Website',
    linkedin: 'LinkedIn',
  };
  return map[key] || humanize(key);
}

function recHref(rec: RecItem): string {
  const hay = `${rec.code || ''} ${rec.title} ${rec.detail || ''}`.toLowerCase();
  if (hay.includes('logo') || hay.includes('guideline') || hay.includes('upload')) {
    return routes.brand;
  }
  if (hay.includes('linkedin') || hay.includes('website') || hay.includes('import') || hay.includes('analyze')) {
    return routes.brandOnboarding;
  }
  return routes.brand;
}

export function BrandIntelligenceDashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [profiles, setProfiles] = useState<BrandIntelligenceProfile[]>([]);
  const [profileId, setProfileId] = useState<string | null>(searchParams.get('profileId'));
  const [dashboard, setDashboard] = useState<BrandIntelligenceDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async (pid?: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const list = await listBrandProfiles();
      setProfiles(list);
      const selected =
        pid ||
        profileId ||
        list.find((p) => p.is_default)?.id ||
        list[0]?.id ||
        null;
      if (!selected) {
        setError('No brand profiles yet. Complete Brand Intelligence onboarding first.');
        setDashboard(null);
        return;
      }
      if (selected !== profileId) setProfileId(selected);
      if (searchParams.get('profileId') !== selected) {
        setSearchParams({ profileId: selected }, { replace: true });
      }
      const data = await getBrandDashboard(selected);
      setDashboard(data);
    } catch {
      setError('Unable to load Brand Intelligence dashboard.');
      setDashboard(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(searchParams.get('profileId'));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial load
  }, []);

  const topics = useMemo(() => asTopicLabels(dashboard?.topics), [dashboard]);
  const missing = useMemo(() => asMissingAssets(dashboard?.missing_assets), [dashboard]);
  const recs = useMemo(() => asRecommendations(dashboard?.recommendations), [dashboard]);
  const writing = dashboard?.writing_dna || {};
  const visual = dashboard?.visual_dna || {};
  const health = dashboard?.health || {};
  const engagement = dashboard?.engagement || {};

  const overallScore = score100(dashboard?.overall_score);
  const confidenceScore = score100(dashboard?.confidence);
  const healthScore = score100(
    (health as { overall_health?: unknown }).overall_health ??
      (health as { score?: unknown }).score
  );
  const healthMeta = healthStatus(healthScore);

  const colors = asTopicLabels(
    (visual as { colors?: unknown }).colors || (visual as { palette?: unknown }).palette
  );
  const fonts = asTopicLabels((visual as { fonts?: unknown }).fonts);
  const logoPresence =
    (visual as { logo_presence?: unknown }).logo_presence ??
    (visual as { logo?: unknown }).logo ??
    (health as { has_logo?: unknown }).has_logo;
  const hasLogo =
    logoPresence === true ||
    logoPresence === 'true' ||
    (typeof logoPresence === 'string' && logoPresence.length > 1 && logoPresence !== '—');

  const toneChips = splitTone(writing.tone);
  const vocab = asTopicLabels(
    (writing as { vocabulary?: unknown }).vocabulary ??
      (writing as { preferred?: unknown }).preferred
  );
  const audienceLabel = humanize(
    typeof dashboard?.audience === 'string'
      ? dashboard.audience
      : writing.reading_level ?? dashboard?.audience
  );

  const postCount = num(engagement.post_count) ?? 0;
  const avgEngagement = num(engagement.average_engagement);
  const avgQuality = score100(engagement.average_quality_score);
  const imageRatio = num(engagement.image_post_ratio);
  const postsWithImages = num(engagement.posts_with_images);
  const bestLength = num(engagement.best_length);
  const topPosts = Array.isArray(engagement.top_quality_posts)
    ? (engagement.top_quality_posts as QualityPost[]).slice(0, 5)
    : [];

  const healthBars: { label: string; value: number | null }[] = [
    { label: 'Writing', value: score100((health as { writing_consistency?: unknown }).writing_consistency) },
    { label: 'Voice', value: score100((health as { voice_consistency?: unknown }).voice_consistency) },
    { label: 'Visual', value: score100((health as { visual_consistency?: unknown }).visual_consistency) },
    { label: 'Topics', value: score100((health as { topic_diversity?: unknown }).topic_diversity) },
    { label: 'Assets', value: score100((health as { asset_coverage?: unknown }).asset_coverage) },
  ];

  if (loading) return <Spinner />;
  if (error && !dashboard) {
    return (
      <div className="space-y-4">
        <PageHeader title="Brand Intelligence" description="Scores and DNA from your latest analysis." />
        <ErrorState message={error} onRetry={() => void load()} />
        <Button asChild>
          <Link to={routes.brandOnboarding}>Complete Brand Intelligence</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Brand Intelligence"
        description="Overall score, health, writing DNA, visuals, and recommendations."
        actions={
          <div className="flex flex-wrap gap-2">
            <select
              className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={profileId || ''}
              onChange={(e) => {
                setProfileId(e.target.value);
                void load(e.target.value);
              }}
            >
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                void load(profileId);
                toast.message('Dashboard refreshed');
              }}
            >
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link to={routes.brandOnboarding}>Re-analyze</Link>
            </Button>
            <Button size="sm" asChild>
              <Link to={routes.brand}>Brand kit</Link>
            </Button>
            <Button size="sm" asChild>
              <Link to={routes.plan}>
                <Sparkles className="h-3.5 w-3.5" /> Plan
              </Link>
            </Button>
          </div>
        }
      />

      <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 sm:flex sm:items-center sm:justify-between sm:gap-4">
        <div className="min-w-0">
          <p className="text-sm font-semibold tracking-tight">Ready to post?</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Open Plan to regenerate your weekly/fortnight LinkedIn mix from the backend
            (copy + image), then approve.
          </p>
        </div>
        <Button className="mt-3 shrink-0 sm:mt-0" asChild>
          <Link to={routes.plan}>Regenerate plan</Link>
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {dashboard?.lifecycle && (
          <Badge variant="secondary">{humanize(dashboard.lifecycle)}</Badge>
        )}
        {dashboard?.version_no != null && (
          <Badge variant="outline">v{dashboard.version_no}</Badge>
        )}
        <Badge variant={healthMeta.variant}>{healthMeta.label}</Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <ScoreMetric
          title="Overall score"
          icon={<Sparkles className="h-4 w-4" />}
          score={overallScore}
          hint="Completeness / brand score"
        />
        <ScoreMetric
          title="Confidence"
          icon={<Target className="h-4 w-4" />}
          score={confidenceScore}
          hint="Memory confidence"
        />
        <ScoreMetric
          title="Health"
          icon={<Activity className="h-4 w-4" />}
          score={healthScore}
          hint={healthMeta.label}
          suffixLabel={healthMeta.label}
        />
        <MetricCard
          title="Audience"
          icon={<Users className="h-4 w-4" />}
          value={audienceLabel}
          hint="Reading level / audience"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <h3 className="flex items-center gap-2 font-semibold">
              <Activity className="h-4 w-4 text-muted-foreground" /> Brand health
            </h3>
          </CardHeader>
          <CardContent className="space-y-3">
            {healthBars.every((b) => b.value == null) ? (
              <Empty>Health breakdown not available yet. Re-analyze to refresh.</Empty>
            ) : (
              healthBars.map((bar) => (
                <BarRow key={bar.label} label={bar.label} value={bar.value} />
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <h3 className="flex items-center gap-2 font-semibold">
              <Lightbulb className="h-4 w-4 text-muted-foreground" /> Topics
            </h3>
          </CardHeader>
          <CardContent>
            {topics.length ? (
              <div className="flex flex-wrap gap-2">
                {topics.slice(0, 20).map((t) => (
                  <Badge key={t} variant="secondary">
                    {t}
                  </Badge>
                ))}
              </div>
            ) : (
              <Empty>No topics detected yet.</Empty>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <h3 className="flex items-center gap-2 font-semibold">
              <Type className="h-4 w-4 text-muted-foreground" /> Writing DNA
            </h3>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div>
              <p className="mb-1.5 text-muted-foreground">Tone</p>
              {toneChips.length ? (
                <div className="flex flex-wrap gap-1.5">
                  {toneChips.map((t) => (
                    <Badge key={t} variant="outline">
                      {t}
                    </Badge>
                  ))}
                </div>
              ) : (
                <Empty>No tone detected.</Empty>
              )}
            </div>
            <Row
              label="Voice"
              value={
                writing.voice || writing.style
                  ? humanize(writing.voice ?? writing.style)
                  : toneChips.length
                    ? 'Matches tone (inferred)'
                    : '—'
              }
            />
            <Row label="Reading level" value={audienceLabel} />
            {vocab.length > 0 && (
              <div>
                <p className="mb-1.5 text-muted-foreground">Vocabulary</p>
                <div className="flex flex-wrap gap-1.5">
                  {vocab.slice(0, 12).map((v) => (
                    <Badge key={v} variant="secondary">
                      {v}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-2 pb-2 space-y-0">
            <h3 className="flex items-center gap-2 font-semibold">
              <Eye className="h-4 w-4 text-muted-foreground" /> Visual DNA
            </h3>
            {!hasLogo && (
              <Button variant="outline" size="sm" asChild>
                <Link to={routes.brand}>
                  <Upload className="h-3.5 w-3.5" /> Upload logo
                </Link>
              </Button>
            )}
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Logo</span>
              {hasLogo ? (
                <span className="inline-flex items-center gap-1.5 font-medium text-success">
                  <CheckCircle2 className="h-4 w-4" /> Detected
                </span>
              ) : (
                <span className="text-muted-foreground">Not uploaded</span>
              )}
            </div>
            <Row
              label="Preferred placement"
              value={humanize(
                (visual as { preferred_logo_position?: unknown }).preferred_logo_position ??
                  'Bottom right (default)'
              )}
            />
            <div>
              <p className="mb-1.5 text-muted-foreground">Colors</p>
              {colors.length ? (
                <div className="flex flex-wrap gap-2">
                  {colors.map((c) => {
                    const swatch = /^#?[0-9a-f]{3,8}$/i.test(c)
                      ? c.startsWith('#')
                        ? c
                        : `#${c}`
                      : null;
                    return (
                      <span
                        key={c}
                        className="inline-flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs"
                      >
                        {swatch && (
                          <span
                            className="inline-block h-3.5 w-3.5 rounded-sm border border-border"
                            style={{ background: swatch }}
                          />
                        )}
                        {swatch || c}
                      </span>
                    );
                  })}
                </div>
              ) : (
                <Empty>No palette yet.</Empty>
              )}
            </div>
            <div>
              <p className="mb-1.5 text-muted-foreground">Fonts</p>
              {fonts.length ? (
                <div className="flex flex-wrap gap-2">
                  {fonts.map((f) => (
                    <Badge key={f} variant="outline">
                      {f}
                    </Badge>
                  ))}
                </div>
              ) : (
                <Empty>No fonts detected — set them in Brand kit.</Empty>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <h3 className="flex items-center gap-2 font-semibold">
              <MessageSquare className="h-4 w-4 text-muted-foreground" /> Engagement
            </h3>
          </CardHeader>
          <CardContent className="space-y-4">
            {postCount === 0 && avgEngagement == null ? (
              <Empty>No engagement signals yet. Import LinkedIn posts to populate this.</Empty>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <StatTile label="Posts" value={String(postCount)} />
                  <StatTile
                    label="Avg engagement"
                    value={avgEngagement == null ? '—' : avgEngagement.toFixed(1)}
                  />
                  <StatTile
                    label="Avg quality"
                    value={avgQuality == null ? '—' : `${avgQuality}`}
                  />
                  <StatTile
                    label="With images"
                    value={
                      postsWithImages != null
                        ? `${postsWithImages}${
                            imageRatio != null ? ` (${Math.round(imageRatio * 100)}%)` : ''
                          }`
                        : '—'
                    }
                  />
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                  <Row
                    label="Best length"
                    value={bestLength != null ? `${bestLength} words` : '—'}
                  />
                  <Row
                    label="Best day"
                    value={engagement.best_day ? humanize(engagement.best_day) : 'Not enough data'}
                  />
                  <Row
                    label="Best time"
                    value={engagement.best_time ? String(engagement.best_time) : 'Not enough data'}
                  />
                </div>
                {topPosts.length > 0 && (
                  <div>
                    <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Top quality posts
                    </p>
                    <ul className="space-y-2">
                      {topPosts.map((p, i) => (
                        <li
                          key={p.post_id || i}
                          className="flex items-start justify-between gap-3 rounded-md border border-border/80 px-3 py-2 text-sm"
                        >
                          <div className="min-w-0">
                            <p className="truncate font-medium">
                              {p.title?.trim() || `Post ${i + 1}`}
                            </p>
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              {p.word_count != null ? `${p.word_count} words` : '—'}
                              {p.has_image ? ' · has image' : ''}
                            </p>
                          </div>
                          <div className="shrink-0 text-right text-xs">
                            <p className="font-semibold tabular-nums">
                              Q {scoreLabel(p.quality_score)}
                            </p>
                            <p className="text-muted-foreground tabular-nums">
                              E {p.engagement_score != null ? Number(p.engagement_score).toFixed(0) : '—'}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-2 pb-2 space-y-0">
            <h3 className="flex items-center gap-2 font-semibold">
              <AlertCircle className="h-4 w-4 text-muted-foreground" /> Missing assets
            </h3>
            {missing.length > 0 && (
              <Button variant="outline" size="sm" asChild>
                <Link to={routes.brand}>
                  <Upload className="h-3.5 w-3.5" /> Upload
                </Link>
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {missing.length ? (
              <ul className="space-y-2">
                {missing.map((m) => (
                  <li
                    key={m}
                    className="flex items-center justify-between gap-3 rounded-md border border-border/80 px-3 py-2 text-sm"
                  >
                    <span className="inline-flex items-center gap-2 font-medium">
                      {m.includes('logo') ? (
                        <ImageIcon className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <FileText className="h-4 w-4 text-muted-foreground" />
                      )}
                      {assetLabel(m)}
                    </span>
                    <Badge variant="warning">Missing</Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="flex items-center gap-2 text-sm text-success">
                <CheckCircle2 className="h-4 w-4" />
                No missing assets flagged.
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <h3 className="flex items-center gap-2 font-semibold">
              <Lightbulb className="h-4 w-4 text-muted-foreground" /> Recommendations
            </h3>
          </CardHeader>
          <CardContent>
            {recs.length ? (
              <ul className="grid gap-3 md:grid-cols-2">
                {recs.map((r, i) => (
                  <li
                    key={`${r.code || r.title}-${i}`}
                    className="flex flex-col gap-3 rounded-lg border border-border bg-muted/15 px-4 py-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium leading-snug">{r.title}</p>
                      {r.priority != null && (
                        <Badge variant={priorityVariant(r.priority)}>P{r.priority}</Badge>
                      )}
                    </div>
                    {r.detail && (
                      <p className="text-sm text-muted-foreground">{r.detail}</p>
                    )}
                    <div>
                      <Button variant="outline" size="sm" asChild>
                        <Link to={recHref(r)}>Take action</Link>
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>No recommendations yet.</Empty>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ScoreMetric({
  title,
  score,
  hint,
  icon,
  suffixLabel,
}: {
  title: string;
  score: number | null;
  hint: string;
  icon: ReactNode;
  suffixLabel?: string;
}) {
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score));
  return (
    <Card>
      <CardContent className="space-y-3 pt-5">
        <div className="flex items-center justify-between text-muted-foreground">
          <p className="text-xs font-medium uppercase tracking-wide">{title}</p>
          {icon}
        </div>
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-3xl font-semibold tracking-tight tabular-nums">
              {score == null ? '—' : score}
              {suffixLabel && score != null && (
                <span className="ml-2 text-sm font-medium text-muted-foreground">
                  {suffixLabel}
                </span>
              )}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
          </div>
          <ScoreRing value={pct} empty={score == null} />
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              score == null
                ? 'bg-muted'
                : pct >= 70
                  ? 'bg-success'
                  : pct >= 45
                    ? 'bg-warning'
                    : 'bg-destructive'
            )}
            style={{ width: score == null ? '0%' : `${pct}%` }}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function ScoreRing({ value, empty }: { value: number; empty?: boolean }) {
  const r = 16;
  const c = 2 * Math.PI * r;
  const offset = c - (empty ? 0 : value / 100) * c;
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" className="shrink-0 -rotate-90">
      <circle
        cx="22"
        cy="22"
        r={r}
        fill="none"
        stroke="currentColor"
        strokeWidth="4"
        className="text-muted"
      />
      <circle
        cx="22"
        cy="22"
        r={r}
        fill="none"
        stroke="currentColor"
        strokeWidth="4"
        strokeDasharray={c}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className={cn(
          empty
            ? 'text-muted'
            : value >= 70
              ? 'text-success'
              : value >= 45
                ? 'text-warning'
                : 'text-destructive'
        )}
      />
    </svg>
  );
}

function MetricCard({
  title,
  value,
  hint,
  icon,
}: {
  title: string;
  value: string;
  hint: string;
  icon: ReactNode;
}) {
  return (
    <Card>
      <CardContent className="space-y-2 pt-5">
        <div className="flex items-center justify-between text-muted-foreground">
          <p className="text-xs font-medium uppercase tracking-wide">{title}</p>
          {icon}
        </div>
        <p className="truncate text-2xl font-semibold tracking-tight capitalize">{value}</p>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border/80 bg-muted/20 px-3 py-2">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function BarRow({ label, value }: { label: string; value: number | null }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">{value == null ? '—' : value}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            'h-full rounded-full',
            value == null
              ? 'bg-muted'
              : pct >= 70
                ? 'bg-success'
                : pct >= 45
                  ? 'bg-warning'
                  : 'bg-destructive'
          )}
          style={{ width: value == null ? '0%' : `${pct}%` }}
        />
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <p className="flex justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate text-right font-medium">{value}</span>
    </p>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>;
}
