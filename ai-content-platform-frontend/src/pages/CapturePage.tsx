import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Mic,
  Camera,
  FileText,
  Square,
  Upload,
  Loader2,
  ChevronRight,
  ChevronLeft,
  ImageIcon,
  Newspaper,
} from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Button } from '@/design-system/ui/button';
import { Badge } from '@/design-system/ui/badge';
import { AuthenticatedImage } from '@/components/AuthenticatedImage';
import { apiClient } from '@/api/client';
import type { ApiEnvelope } from '@/api/types';
import { toast } from 'sonner';
import { routes } from '@/lib/routes';
import { cn } from '@/lib/utils';
import { audioBlobToWav16k } from '@/lib/audioWav';

type ContentTab = 'educational' | 'success_story' | 'personal_achievement';
type PhotoMode = 'none' | 'has_photos' | 'take_now' | 'job_planned';
type Step = 'type' | 'story' | 'questions' | 'photos' | 'generate';

const STEPS: Step[] = ['type', 'story', 'questions', 'photos', 'generate'];

const TABS: { key: ContentTab; label: string; hint: string }[] = [
  {
    key: 'success_story',
    label: 'Success story',
    hint: 'Client outcome — believed problem → real problem → result',
  },
  {
    key: 'personal_achievement',
    label: 'Personal achievement',
    hint: 'Your win, lesson, or milestone in first person',
  },
  {
    key: 'educational',
    label: 'Educational',
    hint: 'Rare manual note — most educational posts come from News',
  },
];

const PHOTO_MODES: { key: PhotoMode; label: string; hint: string }[] = [
  { key: 'none', label: 'No photos', hint: 'AI images later if you want' },
  { key: 'has_photos', label: 'Has photos', hint: 'Upload from camera roll' },
  { key: 'take_now', label: 'Take now', hint: 'Use the phone camera' },
  { key: 'job_planned', label: 'Job planned', hint: 'Get a shot list for later' },
];

interface FollowUpQ {
  id: string;
  prompt: string;
}

interface CaptureSession {
  id: string;
  content_type: string;
  photo_mode: string;
  status: string;
  title?: string | null;
  raw_text?: string;
  follow_up_questions?: FollowUpQ[];
  follow_up_answers?: Record<string, string>;
  shot_list?: Array<{ id: string; label: string }>;
  photos?: Array<{ id: string; url: string }>;
  draft_id?: string | null;
  transcript?: string;
  original_transcript?: string;
  translated?: boolean;
  source_language?: string;
  transcription_provider?: string;
  translation_provider?: string;
}

function stepIndex(s: Step) {
  return STEPS.indexOf(s);
}

function initialContentTab(raw: string | null): ContentTab {
  if (raw === 'personal_achievement' || raw === 'educational' || raw === 'success_story') {
    return raw;
  }
  return 'success_story';
}

export function CapturePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [step, setStep] = useState<Step>('type');
  const [tab, setTab] = useState<ContentTab>(() =>
    initialContentTab(searchParams.get('content_type'))
  );
  const [photoMode, setPhotoMode] = useState<PhotoMode>('none');
  const [text, setText] = useState('');
  const [title, setTitle] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<FollowUpQ[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [shotList, setShotList] = useState<Array<{ id: string; label: string }>>([]);
  const [photos, setPhotos] = useState<Array<{ id: string; url: string }>>([]);
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recSeconds, setRecSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const raw = searchParams.get('content_type');
    if (raw) setTab(initialContentTab(raw));
  }, [searchParams]);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      mediaRecorderRef.current?.stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const ensureSession = useCallback(async (): Promise<string> => {
    if (sessionId) return sessionId;
    const res = await apiClient.post<ApiEnvelope<CaptureSession>>('/capture/sessions', {
      content_type: tab,
      photo_mode: photoMode,
      title: title.trim() || undefined,
    });
    const id = res.data.data?.id;
    if (!id) throw new Error('No session id');
    setSessionId(id);
    return id;
  }, [sessionId, tab, photoMode, title]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : '';
      const recorder = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (timerRef.current) {
          window.clearInterval(timerRef.current);
          timerRef.current = null;
        }
        setRecording(false);
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        await uploadVoice(blob);
      };
      mediaRecorderRef.current = recorder;
      // timeslice keeps a valid container; tiny single-chunk webm often fails STT
      recorder.start(250);
      setRecording(true);
      setRecSeconds(0);
      timerRef.current = window.setInterval(() => setRecSeconds((s) => s + 1), 1000);
    } catch {
      toast.error('Microphone permission needed — or type your story instead');
    }
  };

  const stopRecording = () => {
    const rec = mediaRecorderRef.current;
    if (rec && rec.state !== 'inactive') rec.stop();
  };

  const uploadVoice = async (blob: Blob) => {
    if (blob.size < 500) {
      toast.error('Recording too short — hold for at least 1–2 seconds');
      return;
    }
    setBusy(true);
    try {
      const id = await ensureSession();
      let uploadBlob = blob;
      let filename = 'voice-note.webm';
      try {
        uploadBlob = await audioBlobToWav16k(blob);
        filename = 'voice-note.wav';
      } catch {
        toast.message('Sending original audio — WAV convert failed');
      }
      const form = new FormData();
      const file = new File([uploadBlob], filename, {
        type: filename.endsWith('.wav') ? 'audio/wav' : blob.type || 'audio/webm',
      });
      form.append('audio', file);
      form.append('append', text.trim() ? 'true' : 'false');
      const res = await apiClient.post<ApiEnvelope<CaptureSession>>(
        `/capture/sessions/${id}/voice`,
        form,
        {
          transformRequest: [
            (data, headers) => {
              if (typeof FormData !== 'undefined' && data instanceof FormData) {
                delete (headers as Record<string, unknown>)['Content-Type'];
              }
              return data;
            },
          ],
        }
      );
      const data = res.data.data;
      const transcript = data?.transcript || data?.raw_text || '';
      if (transcript) {
        setText(transcript);
        if (data?.translated && data?.source_language) {
          toast.success(
            `Transcribed (${data.transcription_provider || 'azure'}) and translated from ${data.source_language} → English`
          );
        } else if (data?.transcription_provider === 'mock') {
          toast.message('Mock transcript — restart API after setting STT_PROVIDER=azure');
        } else {
          toast.success(`Transcript ready (${data?.transcription_provider || 'azure'}) — edit if needed`);
        }
      }
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: string | { message?: string } } } })?.response
          ?.data?.error;
      const detail =
        typeof msg === 'string' ? msg : msg?.message || 'Voice upload failed — type your story instead';
      toast.error(detail);
    } finally {
      setBusy(false);
    }
  };

  const goToStory = async () => {
    if (tab === 'educational') {
      // Soft nudge — still allow
    }
    setBusy(true);
    try {
      await ensureSession();
      setStep('story');
    } catch {
      toast.error('Could not start capture session');
    } finally {
      setBusy(false);
    }
  };

  const saveStoryAndContinue = async () => {
    if (!text.trim()) {
      toast.error('Add your story (type or record)');
      return;
    }
    setBusy(true);
    try {
      const id = await ensureSession();
      await apiClient.post(`/capture/sessions/${id}/text`, {
        text: text.trim(),
        title: title.trim() || undefined,
        photo_mode: photoMode,
      });
      const res = await apiClient.get<
        ApiEnvelope<{ questions?: FollowUpQ[]; needed?: boolean; reason?: string }>
      >(`/capture/sessions/${id}/follow-ups`);
      const qs = res.data.data?.questions || [];
      const needed = Boolean(res.data.data?.needed) && qs.length > 0;
      setQuestions(qs);
      setAnswers({});
      if (needed) {
        setStep('questions');
      } else {
        toast.message('Story looks clear — skipping follow-ups');
        setStep('photos');
      }
    } catch {
      toast.error('Could not save story');
    } finally {
      setBusy(false);
    }
  };

  const saveAnswersAndContinue = async () => {
    setBusy(true);
    try {
      const id = await ensureSession();
      const res = await apiClient.patch<ApiEnvelope<CaptureSession>>(
        `/capture/sessions/${id}/follow-ups`,
        { answers }
      );
      setShotList(res.data.data?.shot_list || []);
      setStep('photos');
    } catch {
      toast.error('Could not save answers');
    } finally {
      setBusy(false);
    }
  };

  const applyPhotoMode = async (mode: PhotoMode) => {
    setPhotoMode(mode);
    if (!sessionId) return;
    try {
      const res = await apiClient.patch<ApiEnvelope<CaptureSession>>(
        `/capture/sessions/${sessionId}/photo-mode`,
        { photo_mode: mode }
      );
      setShotList(res.data.data?.shot_list || []);
      if (res.data.data?.photos) setPhotos(res.data.data.photos);
    } catch {
      /* non-blocking */
    }
  };

  const uploadPhotos = async (fileList: FileList | null) => {
    if (!fileList?.length) return;
    setBusy(true);
    try {
      const id = await ensureSession();
      const form = new FormData();
      Array.from(fileList).forEach((f) => form.append('files', f));
      const res = await apiClient.post<ApiEnvelope<CaptureSession>>(
        `/capture/sessions/${id}/photos`,
        form,
        {
          transformRequest: [
            (data, headers) => {
              if (typeof FormData !== 'undefined' && data instanceof FormData) {
                delete (headers as Record<string, unknown>)['Content-Type'];
              }
              return data;
            },
          ],
        }
      );
      setPhotos(res.data.data?.photos || []);
      if (photoMode === 'none') setPhotoMode('has_photos');
      toast.success('Photos uploaded');
    } catch {
      toast.error('Photo upload failed');
    } finally {
      setBusy(false);
    }
  };

  const generateDraft = async () => {
    setBusy(true);
    try {
      const id = await ensureSession();
      await apiClient.patch(`/capture/sessions/${id}/photo-mode`, { photo_mode: photoMode });
      if (text.trim()) {
        await apiClient.post(`/capture/sessions/${id}/text`, {
          text: text.trim(),
          title: title.trim() || undefined,
          photo_mode: photoMode,
        });
      }
      const res = await apiClient.post<ApiEnvelope<{ id?: string }>>(
        `/capture/sessions/${id}/generate`
      );
      const draftId = res.data.data?.id;
      toast.success('LinkedIn draft ready');
      if (draftId) navigate(routes.draft(draftId));
      else navigate(routes.drafts);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string }; message?: string } } })
          ?.response?.data?.error?.message ||
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'Draft generation failed';
      toast.error(String(msg));
    } finally {
      setBusy(false);
    }
  };

  const idx = stepIndex(step);

  return (
    <div className="mx-auto max-w-lg pb-28 sm:max-w-xl">
      <PageHeader
        title="Capture"
        description="Tell a success story or personal win — voice or text — then get a branded LinkedIn draft."
      />

      {/* Progress */}
      <div className="mb-6 flex gap-1">
        {STEPS.map((s, i) => (
          <div
            key={s}
            className={cn(
              'h-1.5 flex-1 rounded-full transition-colors',
              i <= idx ? 'bg-accent' : 'bg-muted'
            )}
          />
        ))}
      </div>

      {step === 'type' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">What are you capturing?</h2>
          <div className="space-y-3">
            {TABS.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setTab(t.key)}
                className={cn(
                  'w-full rounded-xl border px-4 py-4 text-left transition',
                  tab === t.key
                    ? 'border-accent bg-accent/10'
                    : 'border-[var(--color-border)] hover:bg-muted/40'
                )}
              >
                <p className="font-medium">{t.label}</p>
                <p className="mt-1 text-sm text-muted-foreground">{t.hint}</p>
              </button>
            ))}
          </div>
          {tab === 'educational' && (
            <div className="rounded-lg border border-dashed border-[var(--color-border)] p-3 text-sm text-muted-foreground">
              Most educational posts come from{' '}
              <Link to={routes.news} className="text-accent underline inline-flex items-center gap-1">
                <Newspaper className="h-3.5 w-3.5" /> News
              </Link>
              . Use this only for a rare manual note.
            </div>
          )}
          <Button size="lg" className="h-12 w-full" disabled={busy} onClick={goToStory}>
            Continue <ChevronRight className="h-4 w-4" />
          </Button>
        </section>
      )}

      {step === 'story' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Tell the story</h2>
          <label className="block text-sm font-medium">
            Title (optional)
            <input
              className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-3 text-base"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Short headline"
            />
          </label>
          <label className="block text-sm font-medium">
            Story
            <textarea
              className="mt-1 min-h-[180px] w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-3 text-base leading-relaxed"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="What happened? Who benefited? What should peers take away?"
            />
          </label>

          <div className="flex flex-wrap items-center gap-3">
            {!recording ? (
              <Button
                type="button"
                size="lg"
                variant="outline"
                className="h-12 flex-1"
                disabled={busy}
                onClick={startRecording}
              >
                <Mic className="h-5 w-5" />
                Hold-free: record voice
              </Button>
            ) : (
              <Button
                type="button"
                size="lg"
                variant="destructive"
                className="h-12 flex-1"
                onClick={stopRecording}
              >
                <Square className="h-4 w-4" />
                Stop · {recSeconds}s
              </Button>
            )}
            {busy && <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />}
          </div>
          <p className="text-xs text-muted-foreground">
            Voice notes use Azure Speech (or mock). Non-English speech is translated to English
            automatically. You can edit the text before continuing.
          </p>

          <div className="flex gap-2 pt-2">
            <Button variant="outline" className="h-12" onClick={() => setStep('type')}>
              <ChevronLeft className="h-4 w-4" /> Back
            </Button>
            <Button
              size="lg"
              className="h-12 flex-1"
              disabled={busy || !text.trim()}
              onClick={saveStoryAndContinue}
            >
              Continue <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </section>
      )}

      {step === 'questions' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Quick clarity check</h2>
          <p className="text-sm text-muted-foreground">
            We only ask when the story needs a bit more detail to write a strong post.
            Answer what you can — skip the rest.
          </p>
          {questions.map((q) => (
            <label key={q.id} className="block text-sm font-medium">
              {q.prompt}
              <textarea
                className="mt-1 min-h-[72px] w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-2 text-base"
                value={answers[q.id] || ''}
                onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                placeholder="Your answer (optional)"
              />
            </label>
          ))}
          <div className="flex gap-2 pt-2">
            <Button variant="outline" className="h-12" onClick={() => setStep('story')}>
              <ChevronLeft className="h-4 w-4" /> Back
            </Button>
            <Button
              size="lg"
              className="h-12 flex-1"
              disabled={busy}
              onClick={saveAnswersAndContinue}
            >
              Continue <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </section>
      )}

      {step === 'photos' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Camera className="h-5 w-5" /> Photos
          </h2>
          <div className="grid gap-2">
            {PHOTO_MODES.map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => applyPhotoMode(m.key)}
                className={cn(
                  'rounded-xl border px-4 py-3 text-left',
                  photoMode === m.key
                    ? 'border-accent bg-accent/10'
                    : 'border-[var(--color-border)]'
                )}
              >
                <p className="font-medium">{m.label}</p>
                <p className="text-xs text-muted-foreground">{m.hint}</p>
              </button>
            ))}
          </div>

          {(photoMode === 'has_photos' || photoMode === 'take_now') && (
            <div className="space-y-3">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => uploadPhotos(e.target.files)}
              />
              <input
                ref={cameraInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(e) => uploadPhotos(e.target.files)}
              />
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="h-12 flex-1"
                  disabled={busy}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="h-4 w-4" /> Upload
                </Button>
                {photoMode === 'take_now' && (
                  <Button
                    variant="outline"
                    className="h-12 flex-1"
                    disabled={busy}
                    onClick={() => cameraInputRef.current?.click()}
                  >
                    <Camera className="h-4 w-4" /> Camera
                  </Button>
                )}
              </div>
              {photos.length > 0 && (
                <div className="grid grid-cols-3 gap-2">
                  {photos.map((p) => (
                    <div
                      key={p.id}
                      className="aspect-square overflow-hidden rounded-lg border border-[var(--color-border)] bg-muted"
                    >
                      <AuthenticatedImage
                        src={p.url}
                        alt=""
                        className="h-full w-full object-cover"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {photoMode === 'job_planned' && shotList.length > 0 && (
            <div className="rounded-xl border border-[var(--color-border)] p-4">
              <p className="mb-2 text-sm font-medium flex items-center gap-2">
                <ImageIcon className="h-4 w-4" /> Shot list for later
              </p>
              <ol className="list-decimal space-y-2 pl-5 text-sm">
                {shotList.map((s) => (
                  <li key={s.id}>{s.label}</li>
                ))}
              </ol>
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <Button
              variant="outline"
              className="h-12"
              onClick={() => setStep(questions.length ? 'questions' : 'story')}
            >
              <ChevronLeft className="h-4 w-4" /> Back
            </Button>
            <Button
              size="lg"
              className="h-12 flex-1"
              disabled={busy}
              onClick={() => setStep('generate')}
            >
              Continue <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </section>
      )}

      {step === 'generate' && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Write LinkedIn draft</h2>
          <p className="text-sm text-muted-foreground">
            We will use your brand profile and story answers to draft a post in house style.
          </p>
          <div className="rounded-xl border border-[var(--color-border)] p-4 text-sm space-y-2">
            <p>
              <span className="text-muted-foreground">Type:</span>{' '}
              {TABS.find((t) => t.key === tab)?.label}
            </p>
            <p>
              <span className="text-muted-foreground">Photos:</span>{' '}
              {PHOTO_MODES.find((m) => m.key === photoMode)?.label}
              {photos.length ? ` · ${photos.length} uploaded` : ''}
            </p>
            <p className="line-clamp-4 text-muted-foreground">{text.slice(0, 280)}</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" className="h-12" onClick={() => setStep('photos')}>
              <ChevronLeft className="h-4 w-4" /> Back
            </Button>
            <Button size="lg" className="h-12 flex-1" disabled={busy} onClick={generateDraft}>
              {busy ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Writing…
                </>
              ) : (
                <>
                  <FileText className="h-4 w-4" /> Write LinkedIn draft
                </>
              )}
            </Button>
          </div>
        </section>
      )}

      {/* Sticky CTA hint on mobile for mid-flow */}
      {step !== 'type' && step !== 'generate' && (
        <div className="pointer-events-none fixed bottom-0 left-0 right-0 z-10 p-3 sm:hidden">
          <Badge variant="secondary" className="pointer-events-auto mx-auto flex w-fit gap-1 shadow">
            <Mic className="h-3 w-3" /> Step {idx + 1} of {STEPS.length}
          </Badge>
        </div>
      )}
    </div>
  );
}
