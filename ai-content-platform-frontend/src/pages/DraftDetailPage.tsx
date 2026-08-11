import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  ExternalLink,
  Image as ImageIcon,
  Layers,
  Loader2,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
  Type,
  Volume2,
  VolumeX,
  XCircle,
} from 'lucide-react';
import { useApiQuery } from '@/hooks/useApiQuery';
import { apiClient } from '@/api/client';
import type { ApiEnvelope, Draft } from '@/api/types';
import { PageHeader } from '@/components/PageHeader';
import { ErrorState } from '@/components/ErrorState';
import { WorkflowStageRail } from '@/components/ai/WorkflowStageRail';
import { StatusChip } from '@/components/ai/StatusChip';
import { DraftImageGallery, type DraftImageItem } from '@/components/DraftImageGallery';
import { LinkedInPreview } from '@/components/LinkedInPreview';
import { BeforeAfterCompare, type PostSnapshot } from '@/components/RegeneratePanel';
import { useAuth } from '@/contexts/AuthContext';
import { Badge } from '@/design-system/ui/badge';
import { Button } from '@/design-system/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/design-system/ui/card';
import { Input } from '@/design-system/ui/input';
import { Skeleton } from '@/design-system/ui/skeleton';
import { Textarea } from '@/design-system/ui/textarea';
import { toast } from 'sonner';
import { routes } from '@/lib/routes';

const GEN_MESSAGES = [
  'Planning the visual…',
  'Writing the image prompt…',
  'Generating with AI (this can take ~30–70s)…',
  'Optimizing the image…',
  'Almost done…',
];

const IMAGE_GEN_TTL_MS = 20 * 60_000;

function imageGenStorageKey(draftId: string) {
  return `ci:draft-image-gen:${draftId}`;
}

function readImageGenFlag(draftId: string | undefined): boolean {
  if (!draftId || typeof window === 'undefined') return false;
  try {
    const raw = localStorage.getItem(imageGenStorageKey(draftId));
    if (!raw) return false;
    const started = Number(raw);
    if (!Number.isFinite(started) || Date.now() - started > IMAGE_GEN_TTL_MS) {
      localStorage.removeItem(imageGenStorageKey(draftId));
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

function writeImageGenFlag(draftId: string) {
  try {
    localStorage.setItem(imageGenStorageKey(draftId), String(Date.now()));
  } catch {
    /* ignore */
  }
}

function clearImageGenFlag(draftId: string | undefined) {
  if (!draftId) return;
  try {
    localStorage.removeItem(imageGenStorageKey(draftId));
  } catch {
    /* ignore */
  }
}

function mapStatus(s?: string) {
  if (s === 'approved' || s === 'published') return 'approved' as const;
  if (s === 'rejected') return 'rejected' as const;
  if (s === 'pending_review') return 'waiting' as const;
  return 'pending' as const;
}

type FlowStep = 1 | 2 | 3;

function resolveFlow(draft: Draft | undefined, hasImages: boolean, generating: boolean) {
  const status = draft?.status || 'draft';
  if (status === 'rejected') {
    return {
      step: 1 as FlowStep,
      stage: 'Draft',
      title: 'Draft was rejected',
      detail: 'Rewrite the post below, or create a new draft from News.',
      primary: 'rejected' as const,
    };
  }
  if (status === 'pending_review' || status === 'draft' || !status) {
    return {
      step: 1 as FlowStep,
      stage: 'Draft',
      title: 'Step 1 — Approve this post',
      detail: 'Read the LinkedIn preview. If the copy looks good, approve. Then you can add an image.',
      primary: 'approve' as const,
    };
  }
  if (generating) {
    return {
      step: 2 as FlowStep,
      stage: 'Visuals',
      title: 'Step 2 — Creating your image…',
      detail: 'This usually takes 30–70 seconds. You can leave and come back — the loader will still be here.',
      primary: 'generating' as const,
    };
  }
  if (!hasImages) {
    return {
      step: 2 as FlowStep,
      stage: 'Visuals',
      title: 'Step 2 — Generate an image',
      detail: 'One click creates a LinkedIn visual that matches this post’s topic.',
      primary: 'generate' as const,
    };
  }
  return {
    step: 3 as FlowStep,
    stage: 'Done',
    title: 'Step 3 — Ready to post',
    detail: 'Copy the text, download the image from the gallery, or regenerate if you want a different visual.',
    primary: 'done' as const,
  };
}

function fullPostText(draft: Draft, body: string): string {
  const tags = (draft.hashtags || [])
    .map((t) => (t.startsWith('#') ? t : `#${t}`))
    .join(' ');
  return [draft.hook, body, draft.cta, tags].filter(Boolean).join('\n\n');
}

export function DraftDetailPage() {
  const { draftId } = useParams<{ draftId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { data, isLoading, isError, refetch } = useApiQuery<ApiEnvelope<Draft>>(
    ['drafts', draftId || ''],
    `/drafts/${draftId}`,
    { enabled: Boolean(draftId) }
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [imageCount, setImageCount] = useState(1);
  const [rejectReason, setRejectReason] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showImageOptions, setShowImageOptions] = useState(false);
  const [showSource, setShowSource] = useState(false);
  const [showRewrite, setShowRewrite] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [contentNote, setContentNote] = useState('');
  const [regenSection, setRegenSection] = useState<'full' | 'hook' | 'body' | 'cta'>('full');
  const [imageNote, setImageNote] = useState('');
  const [includeLogo, setIncludeLogo] = useState(false);
  const [logoPosition, setLogoPosition] = useState('brand_default');
  const [logoSize, setLogoSize] = useState<'s' | 'm' | 'l'>('m');
  const [genMessageIdx, setGenMessageIdx] = useState(0);
  const [localImages, setLocalImages] = useState<DraftImageItem[]>([]);
  const [previewImageIndex, setPreviewImageIndex] = useState(0);
  const [awaitingImages, setAwaitingImages] = useState(() => readImageGenFlag(draftId));
  const [sawImageJobRunning, setSawImageJobRunning] = useState(() => readImageGenFlag(draftId));
  const [comparePrevious, setComparePrevious] = useState<PostSnapshot | null>(null);
  const [compareCurrent, setCompareCurrent] = useState<PostSnapshot | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const [speakLoading, setSpeakLoading] = useState(false);
  const speakAudioRef = useRef<HTMLAudioElement | null>(null);
  const speakUrlRef = useRef<string | null>(null);
  const speakAbortRef = useRef<AbortController | null>(null);

  const stopHearDraft = () => {
    speakAbortRef.current?.abort();
    speakAbortRef.current = null;
    const audio = speakAudioRef.current;
    if (audio) {
      audio.onended = null;
      audio.onerror = null;
      audio.pause();
      audio.src = '';
      speakAudioRef.current = null;
    }
    if (speakUrlRef.current) {
      URL.revokeObjectURL(speakUrlRef.current);
      speakUrlRef.current = null;
    }
    setSpeaking(false);
    setSpeakLoading(false);
  };

  useEffect(() => {
    return () => {
      stopHearDraft();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- cleanup on unmount only
  }, []);

  const {
    data: imagesData,
    refetch: refetchImages,
    isFetching: imagesFetching,
  } = useApiQuery<
    ApiEnvelope<{
      items?: DraftImageItem[];
      count?: number;
      generating?: boolean;
      active_jobs?: number;
      jobs?: Array<{
        job_id: string;
        status: string;
        error?: string;
        metadata?: { reason_codes?: string[]; [key: string]: unknown };
      }>;
    }>
  >(['drafts', draftId || '', 'images'], `/drafts/${draftId}/images`, {
    enabled: Boolean(draftId),
    staleTime: 0,
    refetchOnMount: 'always',
    refetchInterval: (query) => {
      const gen = query.state.data?.data?.generating;
      if (gen || readImageGenFlag(draftId)) return 2500;
      return false;
    },
  });

  useEffect(() => {
    if (!draftId || !readImageGenFlag(draftId)) return;
    setAwaitingImages(true);
    setSawImageJobRunning(true);
    setBusy('images');
  }, [draftId]);

  const { data: brandData } = useApiQuery<
    ApiEnvelope<{ default_image_count?: number; auto_generate_image_with_draft?: boolean }>
  >(['brand-kit'], '/brand-kit');

  const { data: biProfilesData } = useApiQuery<
    ApiEnvelope<Array<{ id: string; is_default?: boolean; name?: string }>>
  >(['brand-intelligence', 'profiles'], '/brand-intelligence/profiles');

  const biProfileId = useMemo(() => {
    const list = biProfilesData?.data || [];
    return list.find((p) => p.is_default)?.id || list[0]?.id || null;
  }, [biProfilesData]);

  const { data: logoPlacementEnv } = useApiQuery<
    ApiEnvelope<{
      include_logo?: boolean;
      position?: string;
      learned_position?: string | null;
      has_logo_asset?: boolean;
      position_source?: string;
    }>
  >(
    ['brand-intelligence', 'logo-placement', biProfileId || ''],
    `/brand-intelligence/profiles/${biProfileId}/logo-placement`,
    { enabled: Boolean(biProfileId) }
  );

  useEffect(() => {
    const n = brandData?.data?.default_image_count;
    if (n && n >= 1 && n <= 4) setImageCount(n);
  }, [brandData]);

  useEffect(() => {
    const lp = logoPlacementEnv?.data;
    if (!lp) return;
    if (lp.learned_position) setLogoPosition('brand_default');
    else if (lp.position && lp.position !== 'brand_default') setLogoPosition(lp.position);
    // keep includeLogo false by default (optional)
  }, [logoPlacementEnv]);

  useEffect(() => {
    if (imagesData?.data?.generating) {
      setAwaitingImages(true);
      setSawImageJobRunning(true);
      setBusy('images');
    }
  }, [imagesData?.data?.generating]);

  useEffect(() => {
    if (!awaitingImages || !sawImageJobRunning) return;
    if (imagesData === undefined) return;
    if (imagesData?.data?.generating) {
      if (draftId) writeImageGenFlag(draftId);
      return;
    }
    const items = imagesData?.data?.items ?? [];
    const jobs = imagesData?.data?.jobs ?? [];
    const failedJob = jobs.find((j) =>
      ['failed', 'policy_rejected', 'validation_failed'].includes(String(j.status || ''))
    );
    clearImageGenFlag(draftId);
    setBusy((b) => (b === 'images' ? null : b));
    setAwaitingImages(false);
    setSawImageJobRunning(false);
    if (items.length) {
      setLocalImages([]);
      toast.success(`Image ready — ${items.length} generated`);
    } else if (failedJob) {
      const codes = (failedJob.metadata?.reason_codes as string[] | undefined) || [];
      const detail =
        codes.length > 0
          ? codes.join(', ')
          : failedJob.error || 'generation failed';
      toast.error(
        String(failedJob.status) === 'policy_rejected'
          ? `Image blocked by visual policy: ${detail}`
          : `Image generation failed: ${detail}`
      );
    } else {
      toast.error('Image generation finished with no images');
    }
  }, [awaitingImages, sawImageJobRunning, imagesData, draftId]);

  useEffect(() => {
    if (busy !== 'images') return;
    setGenMessageIdx(0);
    const t = window.setInterval(() => {
      setGenMessageIdx((i) => (i + 1) % GEN_MESSAGES.length);
    }, 8000);
    return () => window.clearInterval(t);
  }, [busy]);

  const draft = data?.data;
  const body = draft?.edited_text || draft?.generated_text || draft?.content || '';

  useEffect(() => {
    const meta = draft?.metadata as Record<string, unknown> | undefined;
    const prev = meta?.previous_version as PostSnapshot | undefined;
    if (prev && draft) {
      setComparePrevious(prev);
      setCompareCurrent({
        version: draft.version,
        hook: draft.hook,
        body: draft.edited_text || draft.generated_text || draft.content,
        cta: draft.cta,
        hashtags: draft.hashtags,
      });
    }
  }, [draft]);

  const generating =
    busy === 'images' || Boolean(imagesData?.data?.generating) || awaitingImages;
  const storedImages = useMemo(() => imagesData?.data?.items ?? [], [imagesData]);
  const images = useMemo(() => {
    if (generating && localImages.length) return localImages;
    if (storedImages.length) return storedImages;
    return localImages;
  }, [generating, localImages, storedImages]);

  const flow = useMemo(
    () => resolveFlow(draft, images.length > 0, generating),
    [draft, images.length, generating]
  );

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['drafts'] });
    queryClient.invalidateQueries({ queryKey: ['drafts', draftId || ''] });
    queryClient.invalidateQueries({ queryKey: ['drafts', draftId || '', 'images'] });
    queryClient.invalidateQueries({ queryKey: ['learning'] });
    refetch();
    refetchImages();
  };

  const copyPost = async () => {
    if (!draft) return;
    try {
      await navigator.clipboard.writeText(fullPostText(draft, body));
      toast.success('Post copied to clipboard');
    } catch {
      toast.error('Could not copy');
    }
  };

  const hearDraft = async () => {
    if (!draftId) return;
    // Toggle off while loading or playing
    if (speaking || speakLoading) {
      stopHearDraft();
      return;
    }
    setSpeakLoading(true);
    setSpeaking(true);
    const abort = new AbortController();
    speakAbortRef.current = abort;
    try {
      const res = await apiClient.post(`/drafts/${draftId}/speak`, null, {
        responseType: 'blob',
        timeout: 60_000,
        signal: abort.signal,
      });
      if (abort.signal.aborted) return;
      const blob = res.data as Blob;
      const url = URL.createObjectURL(blob);
      speakUrlRef.current = url;
      const audio = new Audio(url);
      speakAudioRef.current = audio;
      audio.onended = () => {
        stopHearDraft();
      };
      audio.onerror = () => {
        stopHearDraft();
        toast.error('Could not play audio');
      };
      setSpeakLoading(false);
      await audio.play();
    } catch (err: unknown) {
      if (
        abort.signal.aborted ||
        (err as { code?: string; name?: string })?.code === 'ERR_CANCELED' ||
        (err as { name?: string })?.name === 'CanceledError'
      ) {
        return;
      }
      stopHearDraft();
      toast.error('Hear draft unavailable — check Azure Speech config');
    }
  };

  const generateImages = async (guidance = '') => {
    if (!draftId || !draft) return;
    writeImageGenFlag(draftId);
    setBusy('images');
    setAwaitingImages(true);
    setSawImageJobRunning(true);
    queryClient.setQueryData(
      ['drafts', draftId, 'images'],
      (prev: ApiEnvelope<{ generating?: boolean; items?: DraftImageItem[] }> | undefined) =>
        prev
          ? { ...prev, data: { ...prev.data, generating: true } }
          : {
              data: { generating: true, items: [], count: 0, jobs: [] },
              error: null,
              meta: { request_id: '' },
            }
    );
    try {
      await apiClient.post<ApiEnvelope<Record<string, unknown>>>(
        `/drafts/${draft.id}/images/generate`,
        { count: imageCount, guidance: guidance || undefined },
        { timeout: 30_000 }
      );
      toast.success('Image generation started — leave anytime and return');
      invalidate();
    } catch {
      clearImageGenFlag(draftId);
      setAwaitingImages(false);
      setSawImageJobRunning(false);
      setBusy(null);
      toast.error('Could not start image generation — check provider config');
    }
  };

  const regenerateContent = async (guidance: string, section: 'full' | 'hook' | 'body' | 'cta' = 'full') => {
    if (!draftId) return;
    setBusy('regen-content');
    try {
      const res = await apiClient.post<
        ApiEnvelope<{
          previous?: PostSnapshot;
          current?: PostSnapshot;
          message?: string;
          section?: string;
        }>
      >(
        `/drafts/${draftId}/regenerate`,
        { section, guidance: guidance || undefined },
        { timeout: 120_000 }
      );
      const prev = res.data?.data?.previous ?? null;
      const curr = res.data?.data?.current ?? null;
      if (prev && curr) {
        setComparePrevious(prev);
        setCompareCurrent(curr);
      }
      const changed = res.data?.data?.section || section;
      const label =
        changed === 'hook'
          ? 'Hook updated — body kept as-is'
          : changed === 'body'
            ? 'Body rewritten — hook & CTA kept'
            : changed === 'cta'
              ? 'CTA updated'
              : 'Post rewritten — review and approve';
      toast.success(res.data?.data?.message || label);
      setShowRewrite(false);
      invalidate();
    } catch {
      toast.error('Could not regenerate post');
    } finally {
      setBusy(null);
    }
  };

  const runExtra = async (
    key: 'typography' | 'carousel',
    path: string,
    successMsg: string,
    body: Record<string, unknown> = {}
  ) => {
    setBusy(key);
    try {
      await apiClient.post(path, body, { timeout: 180_000 });
      toast.success(successMsg);
      invalidate();
    } catch {
      toast.error(
        key === 'typography'
          ? includeLogo && !logoPlacementEnv?.data?.has_logo_asset
            ? 'Upload a brand logo first (Brand kit), or turn logo off'
            : 'Text overlay failed — generate an image first'
          : 'Carousel failed — try again'
      );
    } finally {
      setBusy(null);
    }
  };

  const handleApprove = async () => {
    if (!draftId) return;
    setBusy('approve');
    try {
      await apiClient.post(`/drafts/${draftId}/approve`, {});
      toast.success('Approved — next: generate an image');
      invalidate();
    } catch {
      toast.error('Approve failed');
    } finally {
      setBusy(null);
    }
  };

  const handleReject = async () => {
    if (!draftId) return;
    setBusy('reject');
    try {
      await apiClient.post(`/drafts/${draftId}/reject`, {
        reason: rejectReason || 'Does not match voice',
        category: 'tone',
      });
      toast.success('Draft rejected');
      invalidate();
    } catch {
      toast.error('Reject failed');
    } finally {
      setBusy(null);
    }
  };

  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (isError || !draft) {
    return <ErrorState message="Unable to load this draft." onRetry={refetch} />;
  }

  const previewImage = images[Math.min(previewImageIndex, Math.max(images.length - 1, 0))]?.url;
  const needsApprove = flow.primary === 'approve';

  return (
    <div className="space-y-5">
      <PageHeader
        title={draft.title || draft.hook || 'Draft'}
        description="Left: your post. Right: image. Approve when the copy looks right, then generate a visual."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => navigate(routes.drafts)}>
              <ArrowLeft className="h-4 w-4" />
              All drafts
            </Button>
            <Button variant="outline" onClick={copyPost}>
              <Copy className="h-4 w-4" />
              Copy post
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <WorkflowStageRail current={flow.stage} />
        <StatusChip status={mapStatus(draft.status)} label={draft.status} />
      </div>

      {comparePrevious && compareCurrent && (
        <BeforeAfterCompare previous={comparePrevious} current={compareCurrent} />
      )}

      {/* Client-friendly layout: post content left, image + actions right */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
        {/* LEFT — generated content first */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">Post text</CardTitle>
                  <CardDescription>
                    {draft.content_type || 'educational'} · {draft.word_count ?? 0} words · v
                    {draft.version ?? 1}
                  </CardDescription>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button size="sm" variant="outline" onClick={hearDraft}>
                    {speakLoading ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : speaking ? (
                      <VolumeX className="h-3.5 w-3.5" />
                    ) : (
                      <Volume2 className="h-3.5 w-3.5" />
                    )}
                    {speaking || speakLoading ? 'Stop' : 'Hear'}
                  </Button>
                  <Button size="sm" variant="outline" onClick={copyPost}>
                    <Copy className="h-3.5 w-3.5" />
                    Copy
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {draft.hook && (
                <div>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Hook
                  </p>
                  <p className="text-base font-medium leading-snug">{draft.hook}</p>
                </div>
              )}
              <div>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Body
                </p>
                <p className="whitespace-pre-wrap leading-relaxed text-foreground/90">
                  {body || '—'}
                </p>
              </div>
              {draft.cta && (
                <div>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Call to action
                  </p>
                  <p>{draft.cta}</p>
                </div>
              )}
              {!!draft.hashtags?.length && (
                <div className="flex flex-wrap gap-1.5">
                  {draft.hashtags.map((tag) => (
                    <Badge key={tag} variant="outline">
                      {tag.startsWith('#') ? tag : `#${tag}`}
                    </Badge>
                  ))}
                </div>
              )}

              {needsApprove && (
                <div className="flex flex-wrap gap-2 border-t border-border pt-4">
                  <Button
                    size="lg"
                    disabled={busy === 'approve'}
                    onClick={handleApprove}
                  >
                    {busy === 'approve' ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <ThumbsUp className="h-4 w-4" />
                    )}
                    Approve post
                  </Button>
                  <Button
                    size="lg"
                    variant="outline"
                    onClick={() => setShowReject((v) => !v)}
                  >
                    <ThumbsDown className="h-4 w-4" />
                    Reject
                  </Button>
                </div>
              )}
              {showReject && needsApprove && (
                <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3">
                  <Input
                    placeholder="Why reject? (optional)"
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                  />
                  <Button
                    variant="destructive"
                    disabled={busy === 'reject'}
                    onClick={handleReject}
                  >
                    Confirm reject
                  </Button>
                </div>
              )}

              {!needsApprove && draft.status !== 'rejected' && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    Post approved
                  </div>
                  {!images.length && !generating && (
                    <Button
                      size="lg"
                      className="h-11 w-full"
                      disabled={generating}
                      onClick={() => generateImages()}
                    >
                      <ImageIcon className="h-4 w-4" />
                      Generate image
                    </Button>
                  )}
                </div>
              )}
              {draft.status === 'rejected' && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  <XCircle className="h-4 w-4 shrink-0" />
                  Rejected — rewrite below or start from News
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">LinkedIn preview</CardTitle>
              <CardDescription>How the post will look in the feed</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <LinkedInPreview
                authorName={user?.name || user?.email || 'You'}
                authorHeadline="Content Intelligence"
                hook={draft.hook}
                body={body}
                cta={draft.cta}
                hashtags={draft.hashtags}
                imageUrl={previewImage}
              />
            </CardContent>
          </Card>

          <div className="rounded-xl border border-border">
            <button
              type="button"
              className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-medium"
              onClick={() => setShowRewrite((v) => !v)}
            >
              <span className="flex items-center gap-2">
                <RefreshCw className="h-4 w-4" />
                Rewrite post text
              </span>
              {showRewrite ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
            {showRewrite && (
              <div className="space-y-3 border-t border-border px-4 py-3">
                <div>
                  <p className="mb-1.5 text-xs font-medium text-muted-foreground">What to change</p>
                  <div className="flex flex-wrap gap-1.5">
                    {(
                      [
                        { id: 'full', label: 'Whole post' },
                        { id: 'hook', label: 'Hook only' },
                        { id: 'body', label: 'Body only' },
                        { id: 'cta', label: 'CTA only' },
                      ] as const
                    ).map((opt) => (
                      <Button
                        key={opt.id}
                        type="button"
                        size="sm"
                        variant={regenSection === opt.id ? 'default' : 'outline'}
                        disabled={busy === 'regen-content' || generating}
                        onClick={() => setRegenSection(opt.id)}
                      >
                        {opt.label}
                      </Button>
                    ))}
                  </div>
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    {regenSection === 'hook'
                      ? 'Only the opening line changes — body stays the same.'
                      : regenSection === 'body'
                        ? 'Only the middle paragraphs change — hook & CTA stay.'
                        : regenSection === 'cta'
                          ? 'Only the closing question changes.'
                          : 'Rewrites hook, body, and CTA together.'}
                  </p>
                </div>
                <Textarea
                  placeholder={
                    regenSection === 'hook'
                      ? 'Optional — e.g. “shorter”, “more urgent”, “less clickbait”'
                      : regenSection === 'body'
                        ? 'Optional — e.g. “more about CQC”, “shorter paragraphs”'
                        : regenSection === 'cta'
                          ? 'Optional — e.g. “ask about compliance”'
                          : 'Optional — e.g. “shorter overall”, “more practical”'
                  }
                  value={contentNote}
                  onChange={(e) => setContentNote(e.target.value)}
                  rows={2}
                  disabled={busy === 'regen-content' || generating}
                />
                <Button
                  variant="outline"
                  className="w-full"
                  disabled={busy === 'regen-content' || generating}
                  onClick={() => regenerateContent(contentNote.trim(), regenSection)}
                >
                  {busy === 'regen-content' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                  {busy === 'regen-content'
                    ? 'Rewriting…'
                    : regenSection === 'full'
                      ? 'Regenerate post'
                      : `Regenerate ${regenSection}`}
                </Button>
              </div>
            )}
          </div>

          {draft.article && (
            <div className="rounded-xl border border-border">
              <button
                type="button"
                className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-medium"
                onClick={() => setShowSource((v) => !v)}
              >
                <span>Source article</span>
                {showSource ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              {showSource && (
                <div className="space-y-2 border-t border-border px-4 py-3">
                  <div className="flex flex-wrap gap-2">
                    {draft.article.source_name && (
                      <Badge variant="secondary">{draft.article.source_name}</Badge>
                    )}
                    {draft.article.category && (
                      <Badge variant="outline">{draft.article.category}</Badge>
                    )}
                  </div>
                  <p className="font-medium">{draft.article.title}</p>
                  {draft.article.summary && (
                    <p className="text-sm text-muted-foreground">{draft.article.summary}</p>
                  )}
                  {draft.article.url && (
                    <a
                      href={draft.article.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-sm text-accent underline"
                    >
                      Open source <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* RIGHT — image + generate */}
        <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          <Card className="border-accent/25">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <ImageIcon className="h-4 w-4 text-accent" />
                Image
              </CardTitle>
              <CardDescription>
                {generating
                  ? 'Working in the background — you can leave this page'
                  : images.length
                    ? 'Ready to download or regenerate'
                    : 'One click creates a LinkedIn visual for this post'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {generating && (
                <div className="flex aspect-square max-h-72 w-full flex-col items-center justify-center rounded-lg border border-dashed border-accent/40 bg-accent/5 p-4 text-center">
                  <Loader2 className="h-10 w-10 animate-spin text-accent" />
                  <p className="mt-3 text-sm font-medium">{GEN_MESSAGES[genMessageIdx]}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Usually 30–70 seconds</p>
                </div>
              )}

              {!generating && !images.length && imagesFetching && (
                <Skeleton className="aspect-square w-full max-h-72 rounded-lg" />
              )}

              {!generating && images.length > 0 && (
                <DraftImageGallery images={images} onIndexChange={setPreviewImageIndex} />
              )}

              {!generating && !images.length && !imagesFetching && (
                <div className="flex aspect-square max-h-56 w-full items-center justify-center rounded-lg border border-dashed border-border bg-muted/30 text-center text-sm text-muted-foreground">
                  No image yet
                </div>
              )}

              <Button
                size="lg"
                className="h-12 w-full text-base"
                disabled={generating}
                onClick={() => generateImages(showImageOptions ? imageNote.trim() : '')}
              >
                {generating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating…
                  </>
                ) : (
                  <>
                    <ImageIcon className="h-4 w-4" />
                    {images.length ? 'Regenerate image' : 'Generate image'}
                  </>
                )}
              </Button>

              <button
                type="button"
                className="flex w-full items-center justify-between text-xs font-medium text-muted-foreground"
                onClick={() => setShowImageOptions((v) => !v)}
              >
                <span>Options</span>
                {showImageOptions ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
              </button>
              {showImageOptions && (
                <div className="space-y-3 rounded-lg border border-border/80 bg-muted/15 p-3">
                  <label className="block space-y-1 text-sm">
                    <span className="text-muted-foreground">How many? (1–4)</span>
                    <Input
                      type="number"
                      min={1}
                      max={4}
                      disabled={generating}
                      value={imageCount}
                      onChange={(e) =>
                        setImageCount(Math.max(1, Math.min(4, Number(e.target.value) || 1)))
                      }
                    />
                  </label>
                  <Textarea
                    placeholder='Optional tip — e.g. "senior living", "no padlocks"'
                    value={imageNote}
                    onChange={(e) => setImageNote(e.target.value)}
                    rows={2}
                    disabled={generating}
                  />
                  {brandData?.data?.auto_generate_image_with_draft && (
                    <p className="text-[11px] text-muted-foreground">
                      Brand setting: images also start automatically when a draft is created.
                    </p>
                  )}
                </div>
              )}

              {flow.primary === 'done' && (
                <Button size="lg" variant="outline" className="w-full" onClick={copyPost}>
                  <Copy className="h-4 w-4" />
                  Copy post text
                </Button>
              )}
            </CardContent>
          </Card>

          <div className="rounded-xl border border-border">
            <button
              type="button"
              className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-medium text-muted-foreground"
              onClick={() => setShowAdvanced((v) => !v)}
            >
              <span>Optional extras</span>
              {showAdvanced ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
            {showAdvanced && (
              <div className="space-y-3 border-t border-border px-4 py-3">
                <p className="text-xs text-muted-foreground">
                  Most posts only need one image. Logo overlay is optional.
                </p>

                <div className="space-y-2 rounded-lg border border-border/80 bg-muted/15 p-3">
                  <label className="flex items-center justify-between gap-3 text-sm font-medium">
                    <span>Add brand logo</span>
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-[var(--color-accent)]"
                      checked={includeLogo}
                      disabled={!logoPlacementEnv?.data?.has_logo_asset && !includeLogo}
                      onChange={(e) => setIncludeLogo(e.target.checked)}
                    />
                  </label>
                  {!logoPlacementEnv?.data?.has_logo_asset && (
                    <p className="text-xs text-muted-foreground">
                      No logo on Brand kit yet — upload one under Brand to enable this.
                    </p>
                  )}
                  {includeLogo && (
                    <div className="space-y-2 pt-1">
                      <label className="block text-xs text-muted-foreground">
                        Position
                        <select
                          className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground"
                          value={logoPosition}
                          onChange={(e) => setLogoPosition(e.target.value)}
                        >
                          <option value="brand_default">
                            Brand default
                            {logoPlacementEnv?.data?.learned_position
                              ? ` (learned: ${logoPlacementEnv.data.learned_position.replace(/_/g, ' ')})`
                              : ' (bottom right)'}
                          </option>
                          <option value="bottom_right">Bottom right</option>
                          <option value="bottom_left">Bottom left</option>
                          <option value="top_right">Top right</option>
                          <option value="top_left">Top left</option>
                          <option value="center">Center</option>
                        </select>
                      </label>
                      <label className="block text-xs text-muted-foreground">
                        Size
                        <select
                          className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground"
                          value={logoSize}
                          onChange={(e) => setLogoSize(e.target.value as 's' | 'm' | 'l')}
                        >
                          <option value="s">Small</option>
                          <option value="m">Medium</option>
                          <option value="l">Large</option>
                        </select>
                      </label>
                      {logoPlacementEnv?.data?.learned_position && (
                        <p className="text-[11px] text-muted-foreground">
                          Learned from your brand posts’ images where the logo usually sits.
                        </p>
                      )}
                    </div>
                  )}
                </div>

                <Button
                  variant="outline"
                  className="w-full"
                  disabled={busy === 'typography' || generating || !images.length}
                  onClick={() =>
                    runExtra(
                      'typography',
                      `/drafts/${draft.id}/typography/generate`,
                      includeLogo ? 'Overlay + logo applied' : 'Text overlay created',
                      {
                        logo: {
                          include_logo: includeLogo,
                          position: logoPosition,
                          size: logoSize,
                          opacity: 1,
                          margin: 0.04,
                          safe_area: true,
                        },
                      }
                    )
                  }
                >
                  {busy === 'typography' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Type className="h-4 w-4" />
                  )}
                  {includeLogo ? 'Text overlay + logo' : 'Text overlay'}
                </Button>
                <Button
                  variant="outline"
                  className="w-full"
                  disabled={busy === 'carousel' || generating}
                  onClick={() =>
                    runExtra(
                      'carousel',
                      `/drafts/${draft.id}/carousels/generate`,
                      'Carousel ready'
                    )
                  }
                >
                  {busy === 'carousel' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Layers className="h-4 w-4" />
                  )}
                  Multi-slide carousel
                </Button>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
