import { useState, useEffect, useRef, type FormEvent, type ChangeEvent } from 'react';
import { Link } from 'react-router-dom';
import {
  Copy,
  Check,
  FileText,
  Upload,
  Pencil,
  Sparkles,
  RefreshCw,
  BarChart3,
  RotateCcw,
  ExternalLink,
  ImageIcon,
} from 'lucide-react';
import { useApiQuery } from '@/hooks/useApiQuery';
import { apiClient } from '@/api/client';
import { Card, CardContent, CardHeader } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { Spinner } from '@/components/Spinner';
import { ErrorState } from '@/components/ErrorState';
import { ComboboxField } from '@/components/ComboboxField';
import { BrandProfileReadable } from '@/components/BrandProfileReadable';
import { AuthenticatedImage } from '@/components/AuthenticatedImage';
import { Badge } from '@/design-system/ui/badge';
import type { BrandKit, BrandProfileTemplate, ApiEnvelope } from '@/api/types';
import {
  getBrandProfileHub,
  listBrandProfiles,
  syncBrandLatest,
  uploadBrandAsset,
  type BrandProfileHub,
  type BrandIntelligenceProfile,
} from '@/api/brandIntelligence';
import { routes } from '@/lib/routes';
import { toast } from 'sonner';

const INDUSTRY_OPTIONS = [
  'IT Support & Managed Services',
  'Cybersecurity',
  'Healthcare / Care',
  'Legal services',
  'Accountancy / Professional services',
  'Financial services',
  'Education',
  'Manufacturing',
  'Retail & hospitality',
  'Construction & property',
  'Public sector',
  'Technology / SaaS',
  'Telecommunications',
  'Other / multi-industry',
];

const TONE_OPTIONS = [
  'Professional',
  'Direct, founder-led, no fluff',
  'Friendly and plain English',
  'Authoritative / expert',
  'Educational and calm',
  'Warm and reassuring',
  'Bold and opinionated',
];

const AUDIENCE_OPTIONS = [
  'Owners and practice managers (5–70 staff)',
  'Regulated SMEs (care, legal, accountancy)',
  'IT decision-makers in mid-market',
  'Founders and operators',
  'Compliance / IG leads',
  'General SME business owners',
];

export function BrandKitPage() {
  const { data, isLoading, isError, refetch } = useApiQuery<ApiEnvelope<BrandKit>>(
    ['brand-kit'],
    '/brand-kit'
  );
  const { data: templateData } = useApiQuery<ApiEnvelope<BrandProfileTemplate>>(
    ['brand-profile-template'],
    '/brand-kit/profile-template'
  );

  const [form, setForm] = useState<Partial<BrandKit>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [editingProfile, setEditingProfile] = useState(false);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const [showPrompt, setShowPrompt] = useState(false);
  const [copied, setCopied] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [biProfile, setBiProfile] = useState<BrandIntelligenceProfile | null>(null);
  const [hub, setHub] = useState<BrandProfileHub | null>(null);
  const [hubLoading, setHubLoading] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (data?.data) {
      setForm({
        ...data.data,
        organization_name: data.data.name || data.data.organization_name,
        tone_of_voice:
          data.data.tone_of_voice ||
          (typeof data.data.tone_json?.voice === 'string'
            ? data.data.tone_json.voice
            : ''),
        target_audience:
          data.data.target_audience ||
          (typeof data.data.tone_json?.audience === 'string'
            ? data.data.tone_json.audience
            : ''),
        industry:
          data.data.industry ||
          (typeof data.data.tone_json?.industry === 'string'
            ? data.data.tone_json.industry
            : ''),
        default_image_count: data.data.default_image_count ?? 1,
        auto_generate_image_with_draft: Boolean(data.data.auto_generate_image_with_draft),
        publishing_window:
          data.data.publishing_window === 'weekly' ? 'weekly' : 'fortnight',
        publishing_targets: {
          educational: data.data.publishing_targets?.educational ?? (data.data.publishing_window === 'weekly' ? 3 : 6),
          success_story: data.data.publishing_targets?.success_story ?? (data.data.publishing_window === 'weekly' ? 1 : 3),
          personal_achievement:
            data.data.publishing_targets?.personal_achievement ?? 1,
        },
        client_profile_md: data.data.client_profile_md || '',
      });
    }
  }, [data]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setHubLoading(true);
      try {
        const profiles = await listBrandProfiles();
        const selected = profiles.find((p) => p.is_default) || profiles[0] || null;
        if (cancelled) return;
        setBiProfile(selected);
        if (selected) {
          const h = await getBrandProfileHub(selected.id);
          if (!cancelled) setHub(h);
        }
      } catch {
        if (!cancelled) {
          setBiProfile(null);
          setHub(null);
        }
      } finally {
        if (!cancelled) setHubLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [data?.data?.id, saved]);

  const logoKey =
    hub?.logo?.primary_key ||
    (data?.data as BrandKit & { logo_object_key?: string })?.logo_object_key ||
    null;

  const handleLogoUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || !biProfile) {
      toast.error('Create a Brand Intelligence profile first');
      return;
    }
    setUploadingLogo(true);
    try {
      await uploadBrandAsset(biProfile.id, file, 'logo', true);
      toast.success('Logo uploaded and linked to Brand Kit');
      const h = await getBrandProfileHub(biProfile.id);
      setHub(h);
      await refetch();
    } catch {
      toast.error('Logo upload failed');
    } finally {
      setUploadingLogo(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    try {
      await apiClient.patch('/brand-kit', {
        name: form.organization_name || form.name,
        primary_color: form.primary_color,
        secondary_color: form.secondary_color,
        description: form.description,
        footer_text: form.footer_text,
        services_line: form.services_line || form.tagline,
        tone_json: {
          ...(form.tone_json || {}),
          voice: form.tone_of_voice,
          audience: form.target_audience,
          industry: form.industry,
        },
        default_image_count: Number(form.default_image_count || 1),
        auto_generate_image_with_draft: Boolean(form.auto_generate_image_with_draft),
        publishing_window: form.publishing_window === 'weekly' ? 'weekly' : 'fortnight',
        publishing_targets: {
          educational: Math.max(0, Math.min(10, Number(form.publishing_targets?.educational ?? 6))),
          success_story: Math.max(0, Math.min(10, Number(form.publishing_targets?.success_story ?? 3))),
          personal_achievement: Math.max(
            0,
            Math.min(5, Number(form.publishing_targets?.personal_achievement ?? 1))
          ),
        },
        client_profile_md: form.client_profile_md ?? '',
      });
      setSaved(true);
      setEditingProfile(false);
      setPasteOpen(false);
      toast.success('Brand saved');
      refetch();
      setTimeout(() => setSaved(false), 3000);
    } catch {
      toast.error('Failed to save brand');
    } finally {
      setSaving(false);
    }
  };

  const applyPaste = () => {
    const next = pasteText.trim();
    if (!next) {
      toast.error('Paste a profile first');
      return;
    }
    if (
      (form.client_profile_md || '').trim() &&
      !window.confirm('Replace the current brand profile with what you pasted?')
    ) {
      return;
    }
    setForm({ ...form, client_profile_md: next });
    setPasteOpen(false);
    setPasteText('');
    setEditingProfile(false);
    toast.success('Profile loaded — click Save Brand to keep it');
  };

  const copyGeneratorPrompt = async () => {
    const prompt = templateData?.data?.generator_prompt;
    if (!prompt) {
      toast.error('Prompt not loaded yet');
      return;
    }
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      toast.success('Prompt copied — paste into Claude or ChatGPT');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Could not copy');
    }
  };

  const handleSyncLatest = async () => {
    setSyncing(true);
    try {
      const profiles = await listBrandProfiles();
      const selected = profiles.find((p) => p.is_default) || profiles[0];
      if (!selected) {
        toast.error('Create a Brand Intelligence profile first');
        return;
      }
      const result = await syncBrandLatest({ brand_profile_id: selected.id });
      toast.success(
        result.job_id
          ? `Sync started (job ${result.job_id.slice(0, 8)}…)`
          : 'Sync started'
      );
    } catch {
      toast.error('Sync failed — complete onboarding with LinkedIn/website first');
    } finally {
      setSyncing(false);
    }
  };

  if (isLoading) return <Spinner />;
  if (isError) return <ErrorState message="Unable to load brand kit." onRetry={refetch} />;

  const profile = form.client_profile_md || '';

  return (
    <div className="space-y-6">
      <PageHeader
        title="Brand"
        description="Tell us who you are. This shapes News scoring, draft writing, and LinkedIn visuals."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" asChild>
              <Link to={routes.brandOnboarding}>
                <Sparkles className="h-3.5 w-3.5" />
                Complete Brand Intelligence
              </Link>
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              loading={syncing}
              onClick={() => void handleSyncLatest()}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Sync Latest
            </Button>
            <Button type="button" variant="outline" size="sm" asChild>
              <Link to={routes.brandOnboarding}>
                <RotateCcw className="h-3.5 w-3.5" />
                Re-analyze
              </Link>
            </Button>
            <Button type="button" size="sm" asChild>
              <Link to={routes.brandDashboard}>
                <BarChart3 className="h-3.5 w-3.5" />
                Intelligence dashboard
              </Link>
            </Button>
          </div>
        }
      />

      <Card>
        <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Brand Intelligence</p>
            <p className="text-xs text-muted-foreground">
              Import LinkedIn, website, and assets into versioned Brand Memory — then review scores
              and DNA on the dashboard.
            </p>
          </div>
          <Button type="button" asChild>
            <Link to={routes.brandOnboarding}>Start 12-step wizard</Link>
          </Button>
        </CardContent>
      </Card>

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground">
              Scraped brand sources
            </h2>
            <p className="text-xs text-muted-foreground">
              LinkedIn / website / uploads connected to{' '}
              {biProfile?.name || 'your Brand Intelligence profile'}. Add a logo anytime.
            </p>
          </div>
          {biProfile && (
            <Button type="button" variant="outline" size="sm" asChild>
              <Link to={`${routes.brandDashboard}?profileId=${biProfile.id}`}>
                <BarChart3 className="h-3.5 w-3.5" />
                Open dashboard
              </Link>
            </Button>
          )}
        </div>

        {hubLoading && (
          <Card>
            <CardContent className="py-6 text-sm text-muted-foreground">
              Loading Brand Intelligence…
            </CardContent>
          </Card>
        )}

        {!hubLoading && !hub && (
          <Card>
            <CardContent className="flex flex-col gap-3 py-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                No scraped Brand Memory yet. Run the wizard with a LinkedIn URL (e.g. Shailesh
                Bhudia / Hybrd).
              </p>
              <Button type="button" asChild>
                <Link to={routes.brandOnboarding}>Connect LinkedIn</Link>
              </Button>
            </CardContent>
          </Card>
        )}

        {hub && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader>
                <h3 className="font-semibold text-foreground">Logo & assets</h3>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex h-28 items-center justify-center rounded-md border border-dashed border-border bg-muted/30">
                  {logoKey ? (
                    <AuthenticatedImage
                      src={`/media/objects/${logoKey}`}
                      alt="Brand logo"
                      className="max-h-24 max-w-full object-contain"
                    />
                  ) : (
                    <div className="flex flex-col items-center gap-1 text-muted-foreground">
                      <ImageIcon className="h-6 w-6" />
                      <span className="text-xs">No logo yet</span>
                    </div>
                  )}
                </div>
                <input
                  ref={logoInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/svg+xml"
                  className="hidden"
                  onChange={(e) => void handleLogoUpload(e)}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full"
                  loading={uploadingLogo}
                  onClick={() => logoInputRef.current?.click()}
                >
                  <Upload className="h-3.5 w-3.5" />
                  {logoKey ? 'Replace logo' : 'Upload logo'}
                </Button>
                {hub.memory && (
                  <div className="space-y-1 text-xs text-muted-foreground">
                    <p>
                      Memory{' '}
                      <Badge variant="secondary">{hub.memory.lifecycle}</Badge> · v
                      {hub.memory.version_no}
                    </p>
                    <p>
                      Confidence {Math.round((hub.memory.confidence || 0) * 100)}% · score{' '}
                      {(hub.memory.completeness as { overall_brand_score?: number } | undefined)
                        ?.overall_brand_score ?? '—'}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <h3 className="font-semibold text-foreground">From LinkedIn & imports</h3>
              </CardHeader>
              <CardContent className="space-y-3">
                {(() => {
                  const dna = (hub.memory?.brand_dna || {}) as Record<string, unknown>;
                  const linkedin =
                    (typeof dna.linkedin_url === 'string' && dna.linkedin_url) ||
                    hub.sources.find((s) => s.source_type === 'linkedin')?.canonical_url;
                  const topics = Array.isArray(dna.topics)
                    ? dna.topics
                        .map((t) =>
                          typeof t === 'object' && t && 'label' in t
                            ? String((t as { label: string }).label)
                            : String(t)
                        )
                        .slice(0, 8)
                    : [];
                  return (
                    <div className="space-y-2 text-sm">
                      {typeof dna.founder === 'string' && (
                        <p>
                          <span className="text-muted-foreground">Founder:</span> {dna.founder}
                        </p>
                      )}
                      {typeof dna.company === 'string' && (
                        <p>
                          <span className="text-muted-foreground">Company:</span> {dna.company}
                        </p>
                      )}
                      {typeof dna.headline === 'string' && (
                        <p>
                          <span className="text-muted-foreground">Headline:</span> {dna.headline}
                        </p>
                      )}
                      {linkedin && (
                        <p className="flex flex-wrap items-center gap-2">
                          <span className="text-muted-foreground">LinkedIn:</span>
                          <a
                            href={linkedin}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
                          >
                            {linkedin.replace(/^https?:\/\//, '')}
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </p>
                      )}
                      {topics.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {topics.map((t) => (
                            <Badge key={t} variant="outline">
                              {t}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })()}

                <div className="max-h-64 space-y-2 overflow-y-auto border-t border-border pt-3">
                  {hub.sources.length === 0 && (
                    <p className="text-xs text-muted-foreground">No source objects stored yet.</p>
                  )}
                  {hub.sources.map((s) => (
                    <div
                      key={s.id}
                      className="rounded-md border border-border/80 px-3 py-2 text-xs"
                    >
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <Badge variant="secondary">{s.source_type}</Badge>
                        <Badge variant="outline">{s.object_type}</Badge>
                        {s.title && (
                          <span className="font-medium text-foreground">{s.title}</span>
                        )}
                      </div>
                      {s.body_preview && (
                        <p className="whitespace-pre-wrap text-muted-foreground">
                          {s.body_preview}
                          {(s.body_preview.length || 0) >= 400 ? '…' : ''}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </section>

      <form onSubmit={handleSubmit} className="space-y-6">
        <section className="space-y-3">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground">1. Basics</h2>
            <p className="text-xs text-muted-foreground">
              Who you are and who you write for — pick a suggestion or type your own.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <h3 className="font-semibold text-foreground">Organization</h3>
              </CardHeader>
              <CardContent className="space-y-4">
                <Input
                  id="org_name"
                  label="Organization name"
                  value={form.organization_name || ''}
                  onChange={(e) => setForm({ ...form, organization_name: e.target.value })}
                />
                <Input
                  id="tagline"
                  label="Tagline / services"
                  value={form.tagline || form.services_line || ''}
                  onChange={(e) =>
                    setForm({ ...form, tagline: e.target.value, services_line: e.target.value })
                  }
                  placeholder="e.g., IT Support | Cybersecurity | Compliance"
                />
                <ComboboxField
                  id="industry"
                  label="Industry"
                  value={form.industry || ''}
                  onChange={(v) => setForm({ ...form, industry: v })}
                  options={INDUSTRY_OPTIONS}
                  placeholder="Select or type your industry"
                  hint="Choose from the list or type a custom industry."
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="font-semibold text-foreground">Voice & audience</h3>
              </CardHeader>
              <CardContent className="space-y-4">
                <ComboboxField
                  id="tone"
                  label="Tone of voice"
                  value={form.tone_of_voice || ''}
                  onChange={(v) => setForm({ ...form, tone_of_voice: v })}
                  options={TONE_OPTIONS}
                  placeholder="Select or describe your tone"
                  hint="How should posts sound when someone reads them?"
                />
                <ComboboxField
                  id="audience"
                  label="Target audience"
                  value={form.target_audience || ''}
                  onChange={(v) => setForm({ ...form, target_audience: v })}
                  options={AUDIENCE_OPTIONS}
                  placeholder="Select or describe who you write for"
                  hint="Who should feel these posts were written for them?"
                />
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="space-y-3">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground">2. Look & visuals</h2>
            <p className="text-xs text-muted-foreground">
              Colors and default image count for LinkedIn posts.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <h3 className="font-semibold text-foreground">Colors</h3>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={form.primary_color || '#0A1F2B'}
                    onChange={(e) => setForm({ ...form, primary_color: e.target.value })}
                    className="h-10 w-10 cursor-pointer rounded border border-border"
                    aria-label="Primary color picker"
                  />
                  <Input
                    id="primary_color"
                    label="Primary color"
                    value={form.primary_color || ''}
                    onChange={(e) => setForm({ ...form, primary_color: e.target.value })}
                    className="flex-1"
                  />
                </div>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={form.secondary_color || '#3B6991'}
                    onChange={(e) => setForm({ ...form, secondary_color: e.target.value })}
                    className="h-10 w-10 cursor-pointer rounded border border-border"
                    aria-label="Secondary color picker"
                  />
                  <Input
                    id="secondary_color"
                    label="Secondary color"
                    value={form.secondary_color || ''}
                    onChange={(e) => setForm({ ...form, secondary_color: e.target.value })}
                    className="flex-1"
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="font-semibold text-foreground">LinkedIn visuals</h3>
              </CardHeader>
              <CardContent className="space-y-4">
                <label className="flex items-start justify-between gap-3 rounded-lg border border-border/80 px-3 py-2.5">
                  <span className="text-sm">
                    <span className="font-medium text-foreground">Generate image with draft</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      When a draft is created from News, also start image generation automatically.
                    </span>
                  </span>
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 shrink-0 accent-[var(--color-accent)]"
                    checked={Boolean(form.auto_generate_image_with_draft)}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        auto_generate_image_with_draft: e.target.checked,
                      })
                    }
                  />
                </label>
                <Input
                  id="default_image_count"
                  label="Default images per draft"
                  type="number"
                  min={1}
                  max={4}
                  value={String(form.default_image_count ?? 1)}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      default_image_count: Math.max(1, Math.min(4, Number(e.target.value) || 1)),
                    })
                  }
                />
                <p className="text-xs text-muted-foreground">
                  Used for auto-generate and the one-click button on drafts (usually 1).
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="font-semibold text-foreground">Publishing cadence</h3>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-xs text-muted-foreground">
                  The Plan tab uses this mix. Weekly = this Mon–Fri; fortnight = this week + next.
                </p>
                <fieldset className="space-y-2">
                  <legend className="text-sm font-medium text-foreground">Window</legend>
                  <div className="flex flex-wrap gap-3">
                    {(
                      [
                        { value: 'weekly', label: 'Weekly (5 posts)' },
                        { value: 'fortnight', label: 'Fortnight (10 posts)' },
                      ] as const
                    ).map((opt) => (
                      <label key={opt.value} className="flex items-center gap-2 text-sm">
                        <input
                          type="radio"
                          name="publishing_window"
                          checked={(form.publishing_window || 'fortnight') === opt.value}
                          onChange={() => {
                            const weekly = opt.value === 'weekly';
                            setForm({
                              ...form,
                              publishing_window: opt.value,
                              publishing_targets: weekly
                                ? { educational: 3, success_story: 1, personal_achievement: 1 }
                                : { educational: 6, success_story: 3, personal_achievement: 1 },
                            });
                          }}
                        />
                        {opt.label}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <div className="grid gap-3 sm:grid-cols-3">
                  <Input
                    id="mix_educational"
                    label="Educational"
                    type="number"
                    min={0}
                    max={10}
                    value={String(form.publishing_targets?.educational ?? 6)}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        publishing_targets: {
                          ...form.publishing_targets,
                          educational: Math.max(0, Math.min(10, Number(e.target.value) || 0)),
                        },
                      })
                    }
                  />
                  <Input
                    id="mix_success"
                    label="Success stories"
                    type="number"
                    min={0}
                    max={10}
                    value={String(form.publishing_targets?.success_story ?? 3)}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        publishing_targets: {
                          ...form.publishing_targets,
                          success_story: Math.max(0, Math.min(10, Number(e.target.value) || 0)),
                        },
                      })
                    }
                  />
                  <Input
                    id="mix_personal"
                    label="Personal"
                    type="number"
                    min={0}
                    max={5}
                    value={String(form.publishing_targets?.personal_achievement ?? 1)}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        publishing_targets: {
                          ...form.publishing_targets,
                          personal_achievement: Math.max(
                            0,
                            Math.min(5, Number(e.target.value) || 0)
                          ),
                        },
                      })
                    }
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="space-y-3">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground">
              3. Brand profile (memory)
            </h2>
            <p className="text-xs text-muted-foreground">
              This is what News uses to decide Relevant vs Not relevant, and what drafts write from.
              Reading view is for clients — use Edit only when you need to change the text.
            </p>
          </div>

          <Card>
            <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="font-semibold text-foreground">Your brand profile</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Yes / No on News also adds short lessons here automatically.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" size="sm" onClick={copyGeneratorPrompt}>
                  {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  Copy Claude / GPT prompt
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowPrompt((v) => !v)}
                >
                  <FileText className="h-3.5 w-3.5" />
                  {showPrompt ? 'Hide prompt' : 'Show prompt'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setPasteOpen((v) => !v);
                    setEditingProfile(false);
                  }}
                >
                  <Upload className="h-3.5 w-3.5" />
                  Paste profile
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setEditingProfile((v) => !v);
                    setPasteOpen(false);
                  }}
                >
                  <Pencil className="h-3.5 w-3.5" />
                  {editingProfile ? 'Reading view' : 'Edit text'}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {showPrompt && (
                <div className="rounded-lg border border-border bg-muted/40 p-4">
                  <p className="mb-2 text-sm font-medium text-foreground">
                    How to generate a profile
                  </p>
                  <ol className="mb-3 list-decimal space-y-1 pl-4 text-xs text-muted-foreground">
                    <li>Copy the prompt below into Claude or ChatGPT.</li>
                    <li>Answer with details about your business.</li>
                    <li>Copy their Markdown reply and use Paste profile.</li>
                    <li>Click Save Brand.</li>
                  </ol>
                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-background p-3 text-xs leading-relaxed text-foreground">
                    {templateData?.data?.generator_prompt || 'Loading…'}
                  </pre>
                </div>
              )}

              {pasteOpen && (
                <div className="space-y-2 rounded-lg border border-border bg-muted/20 p-4">
                  <label htmlFor="paste_profile" className="text-sm font-medium">
                    Paste the profile Markdown here
                  </label>
                  <textarea
                    id="paste_profile"
                    value={pasteText}
                    onChange={(e) => setPasteText(e.target.value)}
                    rows={8}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm"
                    placeholder="Paste the full profile from Claude or ChatGPT…"
                  />
                  <div className="flex gap-2">
                    <Button type="button" size="sm" onClick={applyPaste}>
                      Use this profile
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => setPasteOpen(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {editingProfile ? (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">
                    Advanced: edit the underlying text. Switch back to Reading view to preview.
                  </p>
                  <textarea
                    id="client_profile_md"
                    value={profile}
                    onChange={(e) => setForm({ ...form, client_profile_md: e.target.value })}
                    rows={16}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm leading-relaxed"
                    aria-label="Brand profile Markdown"
                  />
                </div>
              ) : (
                <BrandProfileReadable markdown={profile} />
              )}
            </CardContent>
          </Card>
        </section>

        <div className="flex items-center gap-3 border-t border-border pt-4">
          <Button type="submit" loading={saving}>
            Save Brand
          </Button>
          {saved && <span className="text-sm font-medium text-emerald-600">Saved</span>}
        </div>
      </form>
    </div>
  );
}
