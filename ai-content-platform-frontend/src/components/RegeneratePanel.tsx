import { useState } from 'react';
import { Image as ImageIcon, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/design-system/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/design-system/ui/card';
import { Textarea } from '@/design-system/ui/textarea';

export interface PostSnapshot {
  version?: number;
  hook?: string;
  body?: string;
  cta?: string;
  hashtags?: string[];
}

interface RegeneratePanelProps {
  regeneratingContent: boolean;
  regeneratingImage: boolean;
  onRegenerateContent: (guidance: string) => void;
  onRegenerateImage: (guidance: string) => void;
}

/** Simple regenerate controls — optional guidance, clear labels for clients. */
export function RegeneratePanel({
  regeneratingContent,
  regeneratingImage,
  onRegenerateContent,
  onRegenerateImage,
}: RegeneratePanelProps) {
  const [contentNote, setContentNote] = useState('');
  const [imageNote, setImageNote] = useState('');
  const busy = regeneratingContent || regeneratingImage;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <RefreshCw className="h-4 w-4" />
          Improve this draft
        </CardTitle>
        <CardDescription>
          Regenerate the post text or the image. Optionally tell us what to change.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-2">
          <p className="text-sm font-medium">Post text</p>
          <Textarea
            placeholder='Optional — e.g. "shorter hook", "more about CQC", "less corporate"'
            value={contentNote}
            onChange={(e) => setContentNote(e.target.value)}
            rows={2}
            disabled={busy}
          />
          <Button
            className="w-full"
            variant="outline"
            disabled={busy}
            onClick={() => onRegenerateContent(contentNote.trim())}
          >
            {regeneratingContent ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {regeneratingContent ? 'Rewriting post…' : 'Regenerate post'}
          </Button>
        </div>

        <div className="border-t border-border pt-4 space-y-2">
          <p className="text-sm font-medium">Image</p>
          <Textarea
            placeholder='Optional — e.g. "care home manager with growth chart", "no padlocks"'
            value={imageNote}
            onChange={(e) => setImageNote(e.target.value)}
            rows={2}
            disabled={busy}
          />
          <Button
            className="w-full"
            variant="outline"
            disabled={busy}
            onClick={() => onRegenerateImage(imageNote.trim())}
          >
            {regeneratingImage ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ImageIcon className="h-4 w-4" />
            )}
            {regeneratingImage ? 'Generating image…' : 'Regenerate image'}
          </Button>
          <p className="text-xs text-muted-foreground">
            Image runs in the background — you can leave the page.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

interface BeforeAfterCompareProps {
  previous: PostSnapshot | null;
  current: PostSnapshot | null;
}

function formatPost(s: PostSnapshot | null): string {
  if (!s) return '—';
  const tags = (s.hashtags || []).map((t) => (t.startsWith('#') ? t : `#${t}`)).join(' ');
  return [s.hook, s.body, s.cta, tags].filter(Boolean).join('\n\n') || '—';
}

/** Side-by-side previous vs new after regenerate — for review. */
export function BeforeAfterCompare({ previous, current }: BeforeAfterCompareProps) {
  if (!previous || !current) return null;

  return (
    <Card className="border-accent/30">
      <CardHeader>
        <CardTitle className="text-base">Compare versions</CardTitle>
        <CardDescription>
          Previous (v{previous.version ?? '—'}) vs new (v{current.version ?? '—'}). Approve the new
          post when it looks right.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Previous
            </p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
              {formatPost(previous)}
            </p>
          </div>
          <div className="rounded-lg border border-accent/40 bg-accent/5 p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-accent">
              New — review this
            </p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{formatPost(current)}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
