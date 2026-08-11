import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Button } from '@/design-system/ui/button';
import { Badge } from '@/design-system/ui/badge';
import { Input } from '@/components/Input';
import {
  BRAND_ANALYZE_STAGES,
  analyzeBrandImport,
  approveBrandReview,
  createBrandImport,
  createBrandProfile,
  getBrandImportJob,
  getBrandMemory,
  getBrandReview,
  importFromLinkedInUrl,
  listBrandProfiles,
  patchBrandReview,
  rejectBrandReview,
  startLinkedInSession,
  upsertBrandLogo,
  type BrandImportArtifact,
  type BrandImportJobProgress,
  type BrandIntelligenceProfile,
  type BrandMemoryReview,
  type CreateBrandImportRequest,
} from '@/api/brandIntelligence';
import { toast } from 'sonner';
import { routes } from '@/lib/routes';
import { cn } from '@/lib/utils';
import { PipelineProgress, type PipelineStep } from '@/components/ai/PipelineProgress';

type WizardStep =
  | 'profile'
  | 'linkedin'
  | 'website'
  | 'logo'
  | 'guidelines'
  | 'images'
  | 'videos'
  | 'documents'
  | 'emails'
  | 'review'
  | 'analyze'
  | 'done';

const STEPS: { key: WizardStep; label: string }[] = [
  { key: 'profile', label: 'Profile' },
  { key: 'linkedin', label: 'LinkedIn' },
  { key: 'website', label: 'Website' },
  { key: 'logo', label: 'Logo' },
  { key: 'guidelines', label: 'Guidelines' },
  { key: 'images', label: 'Images' },
  { key: 'videos', label: 'Videos' },
  { key: 'documents', label: 'Documents' },
  { key: 'emails', label: 'Emails' },
  { key: 'review', label: 'Review' },
  { key: 'analyze', label: 'Analyze' },
  { key: 'done', label: 'Dashboard' },
];

const PROFILE_KINDS = [
  { key: 'corporate', label: 'Corporate', hint: 'Company or agency brand' },
  { key: 'personal', label: 'Personal', hint: 'Founder or executive voice' },
  { key: 'product', label: 'Product', hint: 'Product line or offering' },
];

interface LogoVariantDraft {
  variant: string;
  filename: string;
  storage_key: string;
  make_primary: boolean;
}

function stepIndex(s: WizardStep) {
  return STEPS.findIndex((x) => x.key === s);
}

function readTextFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

function artifactKey(kind: string, filename: string) {
  const safe = filename.replace(/[^\w.\-]+/g, '_').slice(0, 120);
  return `brand-uploads/${kind}/${Date.now()}-${safe}`;
}

function parseLinkedInPosts(raw: string): unknown[] {
  const trimmed = raw.trim();
  if (!trimmed) return [];
  if (trimmed.startsWith('[')) {
    try {
      const parsed = JSON.parse(trimmed) as unknown;
      return Array.isArray(parsed) ? parsed : [{ text: trimmed }];
    } catch {
      /* fall through */
    }
  }
  return trimmed
    .split(/\n{2,}/)
    .map((t) => t.trim())
    .filter(Boolean)
    .map((text) => ({ text }));
}

function stageToPipelineSteps(job: BrandImportJobProgress | null): PipelineStep[] {
  const current = job?.stage || 'queued';
  const failed = current === 'failed';
  const stages = BRAND_ANALYZE_STAGES.filter((s) => s.id !== 'failed');
  const order = stages.map((s) => s.id as string);
  const idx = order.indexOf(current);
  return stages.map((s, i) => {
    let status: PipelineStep['status'] = 'pending';
    if (failed) {
      status = i === Math.max(idx, 0) ? 'failed' : i < Math.max(idx, 0) ? 'completed' : 'pending';
    } else if (idx < 0 && s.id === 'queued') status = 'running';
    else if (i < idx) status = 'completed';
    else if (i === idx) status = current === 'awaiting_validation' ? 'completed' : 'running';
    return {
      id: s.id,
      label: s.label,
      status,
      detail: i === idx || (failed && i === Math.max(idx, 0)) ? job?.message || undefined : undefined,
    };
  });
}

export function BrandOnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<WizardStep>('profile');
  const [busy, setBusy] = useState(false);
  const [profiles, setProfiles] = useState<BrandIntelligenceProfile[]>([]);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [profileMode, setProfileMode] = useState<'existing' | 'new'>('new');
  const [profileKind, setProfileKind] = useState('corporate');
  const [profileName, setProfileName] = useState('Corporate');
  const [isDefault, setIsDefault] = useState(true);

  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [linkedinAbout, setLinkedinAbout] = useState('');
  const [linkedinHeadline, setLinkedinHeadline] = useState('');
  const [linkedinDisplayName, setLinkedinDisplayName] = useState('');
  const [linkedinPostsRaw, setLinkedinPostsRaw] = useState('');
  const [usePlaywright, setUsePlaywright] = useState(false);
  const [sessionNote, setSessionNote] = useState<string | null>(null);

  const [websiteUrl, setWebsiteUrl] = useState('');
  const [maxPages, setMaxPages] = useState(8);

  const [logos, setLogos] = useState<LogoVariantDraft[]>([]);
  const [guidelines, setGuidelines] = useState<BrandImportArtifact[]>([]);
  const [images, setImages] = useState<BrandImportArtifact[]>([]);
  const [videos, setVideos] = useState<BrandImportArtifact[]>([]);
  const [documents, setDocuments] = useState<BrandImportArtifact[]>([]);
  const [emails, setEmails] = useState<BrandImportArtifact[]>([]);

  const [jobId, setJobId] = useState<string | null>(null);
  const [importId, setImportId] = useState<string | null>(null);
  const [job, setJob] = useState<BrandImportJobProgress | null>(null);
  const [review, setReview] = useState<BrandMemoryReview | null>(null);
  const [toneEdit, setToneEdit] = useState('');
  const pollRef = useRef<number | null>(null);

  const idx = stepIndex(step);
  const pipelineSteps = useMemo(() => stageToPipelineSteps(job), [job]);

  const loadProfiles = useCallback(async () => {
    try {
      const list = await listBrandProfiles();
      setProfiles(list);
      if (list.length) {
        setProfileMode('existing');
        const def = list.find((p) => p.is_default) || list[0];
        setProfileId(def.id);
      }
    } catch {
      toast.error('Could not load brand profiles');
    }
  }, []);

  useEffect(() => {
    void loadProfiles();
  }, [loadProfiles]);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  const ensureProfile = async (): Promise<string> => {
    if (profileMode === 'existing' && profileId) return profileId;
    const created = await createBrandProfile({
      kind: profileKind,
      name: profileName.trim() || 'Corporate',
      is_default: isDefault,
    });
    setProfileId(created.id);
    setProfiles((prev) => [...prev, created]);
    setProfileMode('existing');
    return created.id;
  };

  const addTextArtifacts = async (
    files: FileList | null,
    kind: BrandImportArtifact['kind'],
    setter: Dispatch<SetStateAction<BrandImportArtifact[]>>
  ) => {
    if (!files?.length) return;
    setBusy(true);
    try {
      const next: BrandImportArtifact[] = [];
      for (const file of Array.from(files)) {
        let extracted_text = '';
        if (
          file.type.startsWith('text/') ||
          /\.(txt|md|csv|html?|json)$/i.test(file.name)
        ) {
          extracted_text = await readTextFile(file);
        } else {
          extracted_text = `[Binary upload: ${file.name}]`;
        }
        next.push({
          kind,
          filename: file.name,
          storage_key: artifactKey(String(kind), file.name),
          extracted_text,
          mime_type: file.type || undefined,
        });
      }
      setter((prev) => [...prev, ...next]);
      toast.success(`${next.length} file(s) added`);
    } catch {
      toast.error('Could not read file(s)');
    } finally {
      setBusy(false);
    }
  };

  const addBinaryArtifacts = (
    files: FileList | null,
    kind: BrandImportArtifact['kind'],
    setter: Dispatch<SetStateAction<BrandImportArtifact[]>>
  ) => {
    if (!files?.length) return;
    const next = Array.from(files).map((file) => ({
      kind,
      filename: file.name,
      storage_key: artifactKey(String(kind), file.name),
      extracted_text: file.name,
      mime_type: file.type || undefined,
    }));
    setter((prev) => [...prev, ...next]);
    toast.success(`${next.length} file(s) added`);
  };

  const addLogoFiles = (files: FileList | null, variant: string) => {
    if (!files?.length) return;
    const file = files[0];
    const storage_key = artifactKey('logo', file.name);
    setLogos((prev) => {
      const without = prev.filter((l) => l.variant !== variant);
      return [
        ...without,
        {
          variant,
          filename: file.name,
          storage_key,
          make_primary: variant === 'primary' || prev.length === 0,
        },
      ];
    });
    toast.success(`Logo variant “${variant}” ready`);
  };

  const buildImportBody = (pid: string): CreateBrandImportRequest => {
    const artifacts: BrandImportArtifact[] = [
      ...logos.map((l) => ({
        kind: 'logo' as const,
        filename: l.filename,
        storage_key: l.storage_key,
        variant: l.variant,
      })),
      ...guidelines,
      ...images,
      ...videos,
      ...documents,
      ...emails,
    ];
    return {
      brand_profile_id: pid,
      linkedin_url: linkedinUrl.trim() || null,
      linkedin_about: linkedinAbout.trim() || null,
      linkedin_headline: linkedinHeadline.trim() || null,
      linkedin_display_name: linkedinDisplayName.trim() || null,
      linkedin_posts: parseLinkedInPosts(linkedinPostsRaw),
      website_url: websiteUrl.trim() || null,
      max_pages: maxPages,
      use_playwright: usePlaywright,
      artifacts,
    };
  };

  const stopPolling = () => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const loadReviewForProfile = async (pid: string) => {
    const memory = await getBrandMemory(pid);
    const open = await getBrandReview(memory.id);
    setReview(open);
    const tone =
      typeof open.detections?.tone === 'string'
        ? open.detections.tone
        : typeof (memory.writing_dna as { tone?: string } | undefined)?.tone === 'string'
          ? String((memory.writing_dna as { tone?: string }).tone)
          : '';
    setToneEdit(tone);
  };

  const startPolling = (jid: string, pid: string) => {
    stopPolling();
    const tick = async () => {
      try {
        const progress = await getBrandImportJob(jid);
        setJob(progress);
        if (progress.stage === 'failed') {
          stopPolling();
          toast.error(progress.message || 'Brand analysis failed');
          return;
        }
        if (progress.stage === 'awaiting_validation' || (progress.progress_pct ?? 0) >= 90) {
          stopPolling();
          try {
            await loadReviewForProfile(pid);
            toast.success('Analysis ready for review');
          } catch {
            toast.message('Analysis finished — open the dashboard to review');
            setStep('done');
          }
        }
      } catch {
        /* keep polling briefly; surface on next ticks */
      }
    };
    void tick();
    pollRef.current = window.setInterval(() => void tick(), 2000);
  };

  const startAnalyze = async () => {
    setBusy(true);
    setReview(null);
    setJob(null);
    try {
      const pid = await ensureProfile();
      for (const logo of logos) {
        await upsertBrandLogo(pid, {
          variant: logo.variant,
          storage_key: logo.storage_key,
          make_primary: logo.make_primary,
        });
      }

      const urlOnly =
        Boolean(linkedinUrl.trim()) &&
        !linkedinAbout.trim() &&
        !linkedinHeadline.trim() &&
        !linkedinDisplayName.trim() &&
        parseLinkedInPosts(linkedinPostsRaw).length === 0;

      let jid = '';
      let nextProfileId = pid;

      if (urlOnly) {
        const accepted = await importFromLinkedInUrl({
          linkedin_url: linkedinUrl.trim(),
          brand_profile_id: pid,
          website_url: websiteUrl.trim() || null,
          max_posts: 40,
        });
        setImportId(accepted.import_id);
        jid = accepted.job_id;
        nextProfileId = accepted.brand_profile_id || pid;
        setProfileId(nextProfileId);
        toast.success('Fetching LinkedIn profile, posts & images…');
      } else {
        const created = await createBrandImport(buildImportBody(pid));
        setImportId(created.id);
        const accepted = await analyzeBrandImport(created.id);
        jid = accepted.job_id;
        toast.success('Brand analysis started');
      }

      setJobId(jid);
      setStep('analyze');
      startPolling(jid, nextProfileId);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      let msg = 'Could not start analysis';
      if (typeof detail === 'string') msg = detail;
      else if (detail && typeof detail === 'object') {
        const d = detail as { message?: string; code?: string };
        if (d.message) msg = d.message;
        if (d.code === 'linkedin_session_required') {
          msg =
            'Connect LinkedIn once first (scripts/linkedin_session_login.py + save session). Then paste only the profile URL.';
        }
      }
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const retryAnalyze = async () => {
    if (!importId || !profileId) {
      await startAnalyze();
      return;
    }
    setBusy(true);
    try {
      const accepted = await analyzeBrandImport(importId);
      setJobId(accepted.job_id);
      setReview(null);
      startPolling(accepted.job_id, profileId);
      toast.success('Retrying analysis');
    } catch {
      toast.error('Retry failed');
    } finally {
      setBusy(false);
    }
  };

  const saveToneAndApprove = async () => {
    if (!review || !profileId) return;
    setBusy(true);
    try {
      if (toneEdit.trim()) {
        await patchBrandReview(review.id, { tone: toneEdit.trim() });
      }
      await approveBrandReview(review.id);
      toast.success('Brand memory approved');
      setStep('done');
    } catch {
      toast.error('Could not approve review');
    } finally {
      setBusy(false);
    }
  };

  const rejectOpenReview = async () => {
    if (!review) return;
    setBusy(true);
    try {
      await rejectBrandReview(review.id);
      toast.message('Review rejected — you can re-run analysis');
      setReview(null);
    } catch {
      toast.error('Could not reject review');
    } finally {
      setBusy(false);
    }
  };

  const bootstrapLinkedInSession = async () => {
    setBusy(true);
    try {
      const res = await startLinkedInSession();
      setSessionNote(res.instructions);
      setUsePlaywright(true);
      toast.success('LinkedIn session bootstrap ready');
    } catch {
      toast.error('Could not start LinkedIn session');
    } finally {
      setBusy(false);
    }
  };

  const goNext = async () => {
    const i = stepIndex(step);
    if (step === 'profile') {
      setBusy(true);
      try {
        await ensureProfile();
        setStep(STEPS[i + 1].key);
      } catch {
        toast.error('Could not save profile');
      } finally {
        setBusy(false);
      }
      return;
    }
    if (step === 'review') {
      await startAnalyze();
      return;
    }
    if (i < STEPS.length - 1) setStep(STEPS[i + 1].key);
  };

  const goBack = () => {
    const i = stepIndex(step);
    if (i > 0) setStep(STEPS[i - 1].key);
  };

  const artifactList = (
    items: BrandImportArtifact[],
    onRemove: (index: number) => void
  ) =>
    items.length === 0 ? (
      <p className="text-sm text-muted-foreground">Nothing added yet — optional.</p>
    ) : (
      <ul className="space-y-2">
        {items.map((a, i) => (
          <li
            key={`${a.filename}-${i}`}
            className="flex items-center justify-between rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm"
          >
            <span className="truncate">{a.filename || a.kind}</span>
            <Button type="button" variant="ghost" size="sm" onClick={() => onRemove(i)}>
              Remove
            </Button>
          </li>
        ))}
      </ul>
    );

  return (
    <div className="mx-auto max-w-lg pb-28 sm:max-w-xl">
      <PageHeader
        title="Brand Intelligence"
        description="Import LinkedIn, website, and brand assets — then analyze into Brand Memory."
        actions={
          <Button variant="outline" size="sm" asChild>
            <Link to={routes.brand}>Brand kit</Link>
          </Button>
        }
      />

      <div className="mb-6 flex gap-1">
        {STEPS.map((s, i) => (
          <div
            key={s.key}
            title={s.label}
            className={cn(
              'h-1.5 flex-1 rounded-full transition-colors',
              i <= idx ? 'bg-accent' : 'bg-muted'
            )}
          />
        ))}
      </div>
      <p className="mb-4 text-xs text-muted-foreground">
        Step {idx + 1} of {STEPS.length}: {STEPS[idx]?.label}
      </p>

      {step === 'profile' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Brand profile</h2>
          <p className="text-sm text-muted-foreground">
            Choose an existing profile or create one. Memory is stored per profile.
          </p>
          {profiles.length > 0 && (
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => setProfileMode('existing')}
                className={cn(
                  'w-full rounded-xl border px-4 py-3 text-left',
                  profileMode === 'existing'
                    ? 'border-accent bg-accent/10'
                    : 'border-[var(--color-border)]'
                )}
              >
                <p className="font-medium">Use existing</p>
                <p className="text-xs text-muted-foreground">{profiles.length} profile(s)</p>
              </button>
              {profileMode === 'existing' && (
                <select
                  className="w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-3 text-base"
                  value={profileId || ''}
                  onChange={(e) => setProfileId(e.target.value)}
                >
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.kind}){p.is_default ? ' · default' : ''}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}
          <button
            type="button"
            onClick={() => setProfileMode('new')}
            className={cn(
              'w-full rounded-xl border px-4 py-3 text-left',
              profileMode === 'new' ? 'border-accent bg-accent/10' : 'border-[var(--color-border)]'
            )}
          >
            <p className="font-medium">Create new profile</p>
            <p className="text-xs text-muted-foreground">Corporate, personal, or product</p>
          </button>
          {profileMode === 'new' && (
            <div className="space-y-3">
              <div className="grid gap-2">
                {PROFILE_KINDS.map((k) => (
                  <button
                    key={k.key}
                    type="button"
                    onClick={() => setProfileKind(k.key)}
                    className={cn(
                      'rounded-xl border px-4 py-3 text-left',
                      profileKind === k.key
                        ? 'border-accent bg-accent/10'
                        : 'border-[var(--color-border)]'
                    )}
                  >
                    <p className="font-medium">{k.label}</p>
                    <p className="text-xs text-muted-foreground">{k.hint}</p>
                  </button>
                ))}
              </div>
              <Input
                id="profile_name"
                label="Profile name"
                value={profileName}
                onChange={(e) => setProfileName(e.target.value)}
              />
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                />
                Set as default profile
              </label>
            </div>
          )}
          <Button size="lg" className="h-12 w-full" disabled={busy} onClick={() => void goNext()}>
            Continue <ChevronRight className="h-4 w-4" />
          </Button>
        </section>
      )}

      {step === 'linkedin' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">LinkedIn</h2>
          <p className="text-sm text-muted-foreground">
            Paste the founder or company LinkedIn URL. We fetch About, experience, posts,
            engagement, post quality, and images automatically — no manual paste needed.
          </p>
          <Input
            id="li_url"
            label="LinkedIn profile URL"
            value={linkedinUrl}
            onChange={(e) => setLinkedinUrl(e.target.value)}
            placeholder="https://www.linkedin.com/in/…"
          />
          <div className="rounded-lg border border-[var(--color-border)] bg-muted/20 p-3 text-xs text-muted-foreground space-y-2">
            <p className="font-medium text-foreground">One-time LinkedIn connect</p>
            <ol className="list-decimal space-y-1 pl-4">
              <li>
                Run <code className="text-[11px]">scripts/linkedin_session_login.py</code> on the
                server/dev machine and log in once.
              </li>
              <li>Save the session via Brand Intelligence session API (or ask an admin).</li>
              <li>Come back here, paste only the URL, continue the wizard, then Analyze.</li>
            </ol>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => void bootstrapLinkedInSession()}
              >
                Show session instructions
              </Button>
              <Badge variant="secondary">URL-only fetch</Badge>
            </div>
            {sessionNote && <p className="pt-1 whitespace-pre-wrap">{sessionNote}</p>}
          </div>
          <details className="rounded-lg border border-dashed border-[var(--color-border)] p-3">
            <summary className="cursor-pointer text-sm font-medium">
              Advanced — paste About / posts manually (offline / no session)
            </summary>
            <div className="mt-3 space-y-3">
              <Input
                id="li_name"
                label="Display name"
                value={linkedinDisplayName}
                onChange={(e) => setLinkedinDisplayName(e.target.value)}
              />
              <Input
                id="li_headline"
                label="Headline"
                value={linkedinHeadline}
                onChange={(e) => setLinkedinHeadline(e.target.value)}
              />
              <label className="block text-sm font-medium">
                About
                <textarea
                  className="mt-1 min-h-[100px] w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-2 text-base"
                  value={linkedinAbout}
                  onChange={(e) => setLinkedinAbout(e.target.value)}
                />
              </label>
              <label className="block text-sm font-medium">
                Sample posts
                <textarea
                  className="mt-1 min-h-[100px] w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-2 font-mono text-sm"
                  value={linkedinPostsRaw}
                  onChange={(e) => setLinkedinPostsRaw(e.target.value)}
                  placeholder="Only if you cannot connect a LinkedIn session"
                />
              </label>
            </div>
          </details>
          <NavRow onBack={goBack} onNext={() => void goNext()} busy={busy} nextDisabled={!linkedinUrl.trim()} />
        </section>
      )}

      {step === 'website' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Website</h2>
          <Input
            id="website_url"
            label="Website URL"
            value={websiteUrl}
            onChange={(e) => setWebsiteUrl(e.target.value)}
            placeholder="https://…"
          />
          <Input
            id="max_pages"
            label="Max pages to crawl"
            type="number"
            min={1}
            max={40}
            value={String(maxPages)}
            onChange={(e) => setMaxPages(Math.max(1, Math.min(40, Number(e.target.value) || 8)))}
          />
          <NavRow onBack={goBack} onNext={() => void goNext()} busy={busy} />
        </section>
      )}

      {step === 'logo' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Logo variants</h2>
          <p className="text-sm text-muted-foreground">
            Add primary, light, dark, or icon variants. Keys are registered on the profile before
            analysis.
          </p>
          {(['primary', 'light', 'dark', 'icon'] as const).map((variant) => (
            <div key={variant} className="rounded-xl border border-[var(--color-border)] p-3">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-medium capitalize">{variant}</p>
                {logos.find((l) => l.variant === variant) && (
                  <Badge variant="secondary">{logos.find((l) => l.variant === variant)?.filename}</Badge>
                )}
              </div>
              <input
                type="file"
                accept="image/*"
                className="text-sm"
                onChange={(e) => {
                  addLogoFiles(e.target.files, variant);
                  e.target.value = '';
                }}
              />
            </div>
          ))}
          <NavRow onBack={goBack} onNext={() => void goNext()} busy={busy} />
        </section>
      )}

      {step === 'guidelines' && (
        <ArtifactStep
          title="Brand guidelines"
          hint="PDF or Markdown brand guidelines (optional)."
          accept=".pdf,.md,.txt,.doc,.docx,application/pdf,text/*"
          items={guidelines}
          onAdd={(files) => void addTextArtifacts(files, 'guideline', setGuidelines)}
          onRemove={(i) => setGuidelines((prev) => prev.filter((_, idx) => idx !== i))}
          onBack={goBack}
          onNext={() => void goNext()}
          busy={busy}
          renderList={artifactList}
        />
      )}

      {step === 'images' && (
        <ArtifactStep
          title="Brand images"
          hint="Reference photography and visual examples."
          accept="image/*"
          items={images}
          onAdd={(files) => addBinaryArtifacts(files, 'image', setImages)}
          onRemove={(i) => setImages((prev) => prev.filter((_, idx) => idx !== i))}
          onBack={goBack}
          onNext={() => void goNext()}
          busy={busy}
          renderList={artifactList}
        />
      )}

      {step === 'videos' && (
        <ArtifactStep
          title="Videos"
          hint="Optional video references (metadata ingested)."
          accept="video/*"
          items={videos}
          onAdd={(files) => addBinaryArtifacts(files, 'video', setVideos)}
          onRemove={(i) => setVideos((prev) => prev.filter((_, idx) => idx !== i))}
          onBack={goBack}
          onNext={() => void goNext()}
          busy={busy}
          renderList={artifactList}
        />
      )}

      {step === 'documents' && (
        <ArtifactStep
          title="Documents"
          hint="Pitch decks, one-pagers, or other brand docs."
          accept=".pdf,.doc,.docx,.txt,.md,application/pdf,text/*"
          items={documents}
          onAdd={(files) => void addTextArtifacts(files, 'document', setDocuments)}
          onRemove={(i) => setDocuments((prev) => prev.filter((_, idx) => idx !== i))}
          onBack={goBack}
          onNext={() => void goNext()}
          busy={busy}
          renderList={artifactList}
        />
      )}

      {step === 'emails' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Emails</h2>
          <p className="text-sm text-muted-foreground">
            Paste a signature or newsletter sample, or upload .eml / text.
          </p>
          <label className="block text-sm font-medium">
            Paste email / signature
            <textarea
              className="mt-1 min-h-[120px] w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
              placeholder="Paste sample email copy…"
              onBlur={(e) => {
                const text = e.target.value.trim();
                if (!text) return;
                setEmails((prev) => [
                  ...prev,
                  {
                    kind: 'email',
                    filename: 'pasted-email.txt',
                    storage_key: artifactKey('email', 'pasted-email.txt'),
                    extracted_text: text,
                  },
                ]);
                e.target.value = '';
                toast.success('Email sample added');
              }}
            />
          </label>
          <input
            type="file"
            accept=".eml,.txt,.html,text/*,message/rfc822"
            multiple
            onChange={(e) => {
              void addTextArtifacts(e.target.files, 'email', setEmails);
              e.target.value = '';
            }}
          />
          {artifactList(emails, (i) => setEmails((prev) => prev.filter((_, idx) => idx !== i)))}
          <NavRow onBack={goBack} onNext={() => void goNext()} busy={busy} />
        </section>
      )}

      {step === 'review' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Review sources</h2>
          <p className="text-sm text-muted-foreground">
            Confirm what will be sent for analysis. You can go back to edit any step.
          </p>
          <div className="space-y-2 rounded-xl border border-[var(--color-border)] p-4 text-sm">
            <SummaryRow label="Profile" value={profiles.find((p) => p.id === profileId)?.name || profileName} />
            <SummaryRow label="LinkedIn" value={linkedinUrl || '—'} />
            <SummaryRow label="Website" value={websiteUrl || '—'} />
            <SummaryRow label="Logos" value={String(logos.length)} />
            <SummaryRow label="Guidelines" value={String(guidelines.length)} />
            <SummaryRow label="Images" value={String(images.length)} />
            <SummaryRow label="Videos" value={String(videos.length)} />
            <SummaryRow label="Documents" value={String(documents.length)} />
            <SummaryRow label="Emails" value={String(emails.length)} />
            <SummaryRow
              label="Posts"
              value={String(parseLinkedInPosts(linkedinPostsRaw).length)}
            />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" className="h-12" onClick={goBack}>
              <ChevronLeft className="h-4 w-4" /> Back
            </Button>
            <Button
              size="lg"
              className="h-12 flex-1"
              disabled={busy}
              onClick={() => void goNext()}
            >
              {busy ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Starting…
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" /> Start analysis
                </>
              )}
            </Button>
          </div>
        </section>
      )}

      {step === 'analyze' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Analyze</h2>
          <p className="text-sm text-muted-foreground">
            Live pipeline stages. When analysis finishes, validate detections before Brand Memory is
            finalized.
          </p>
          {(job?.progress_pct != null || jobId) && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{job?.message || 'Working…'}</span>
                <span className="font-medium tabular-nums">{job?.progress_pct ?? 0}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-accent transition-all duration-500"
                  style={{ width: `${Math.min(100, job?.progress_pct ?? 0)}%` }}
                />
              </div>
              {job?.eta_seconds != null && job.eta_seconds > 0 && (
                <p className="text-xs text-muted-foreground">ETA ~{job.eta_seconds}s</p>
              )}
            </div>
          )}
          <PipelineProgress steps={pipelineSteps} />
          {job?.stage === 'failed' && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
              <div className="space-y-2">
                <p>{job.message || 'Analysis failed'}</p>
                <Button size="sm" variant="outline" disabled={busy} onClick={() => void retryAnalyze()}>
                  Retry
                </Button>
              </div>
            </div>
          )}
          {review && (
            <div className="space-y-3 rounded-xl border border-[var(--color-border)] p-4">
              <h3 className="font-medium">Detected attributes</h3>
              <pre className="max-h-48 overflow-auto rounded-md bg-muted/40 p-3 text-xs">
                {JSON.stringify(review.detections || {}, null, 2)}
              </pre>
              <Input
                id="tone_edit"
                label="Tone (edit before approve)"
                value={toneEdit}
                onChange={(e) => setToneEdit(e.target.value)}
              />
              <div className="flex flex-wrap gap-2">
                <Button disabled={busy} onClick={() => void saveToneAndApprove()}>
                  Approve memory
                </Button>
                <Button variant="outline" disabled={busy} onClick={() => void rejectOpenReview()}>
                  Reject
                </Button>
              </div>
            </div>
          )}
          {!review && job?.stage !== 'failed' && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Polling job {jobId?.slice(0, 8)}…
            </div>
          )}
          <Button variant="outline" className="h-12" onClick={goBack} disabled={busy}>
            <ChevronLeft className="h-4 w-4" /> Back
          </Button>
        </section>
      )}

      {step === 'done' && (
        <section className="space-y-4 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-600" />
          <h2 className="text-lg font-semibold">Brand Intelligence ready</h2>
          <p className="text-sm text-muted-foreground">
            Open the dashboard for scores, health, writing DNA, and recommendations.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
            <Button
              size="lg"
              className="h-12"
              onClick={() =>
                navigate(
                  profileId
                    ? `${routes.brandDashboard}?profileId=${profileId}`
                    : routes.brandDashboard
                )
              }
            >
              Open dashboard
            </Button>
            <Button size="lg" variant="outline" className="h-12" asChild>
              <Link to={routes.brand}>Back to Brand kit</Link>
            </Button>
          </div>
        </section>
      )}
    </div>
  );
}

function NavRow({
  onBack,
  onNext,
  busy,
  nextDisabled,
}: {
  onBack: () => void;
  onNext: () => void;
  busy?: boolean;
  nextDisabled?: boolean;
}) {
  return (
    <div className="flex gap-2 pt-2">
      <Button variant="outline" className="h-12" onClick={onBack} disabled={busy}>
        <ChevronLeft className="h-4 w-4" /> Back
      </Button>
      <Button
        size="lg"
        className="h-12 flex-1"
        disabled={busy || nextDisabled}
        onClick={onNext}
      >
        Continue <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <p className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate font-medium text-right">{value}</span>
    </p>
  );
}

function ArtifactStep({
  title,
  hint,
  accept,
  items,
  onAdd,
  onRemove,
  onBack,
  onNext,
  busy,
  renderList,
}: {
  title: string;
  hint: string;
  accept: string;
  items: BrandImportArtifact[];
  onAdd: (files: FileList | null) => void;
  onRemove: (index: number) => void;
  onBack: () => void;
  onNext: () => void;
  busy?: boolean;
  renderList: (
    items: BrandImportArtifact[],
    onRemove: (index: number) => void
  ) => ReactNode;
}) {
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="text-sm text-muted-foreground">{hint}</p>
      <input
        type="file"
        accept={accept}
        multiple
        className="text-sm"
        onChange={(e) => {
          onAdd(e.target.files);
          e.target.value = '';
        }}
      />
      {renderList(items, onRemove)}
      <NavRow onBack={onBack} onNext={onNext} busy={busy} />
    </section>
  );
}
