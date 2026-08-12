import { Link } from 'react-router-dom';
import {
  CheckCircle2,
  ExternalLink,
  Loader2,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react';
import { LinkedInPreview } from '@/components/LinkedInPreview';
import { Badge } from '@/design-system/ui/badge';
import { Button } from '@/design-system/ui/button';
import { routes } from '@/lib/routes';
import { cn } from '@/lib/utils';
import type { ReviewQueueItem } from './types';

const TYPE_LABEL: Record<string, string> = {
  educational: 'Educational',
  success_story: 'Success story',
  personal_achievement: 'Personal',
};

export function LinkedInReadyCard({
  draft,
  authorName,
  authorHeadline,
  busy,
  onApprove,
  onReject,
  onRegenerate,
  className,
}: {
  draft: ReviewQueueItem;
  authorName?: string;
  authorHeadline?: string;
  busy?: 'approve' | 'reject' | 'regenerate' | null;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onRegenerate?: (id: string) => void;
  className?: string;
}) {
  const typeLabel = draft.content_type
    ? TYPE_LABEL[draft.content_type] || draft.content_type
    : null;
  const blocked = Boolean(busy);

  return (
    <article
      className={cn(
        'overflow-hidden rounded-2xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(0,0,0,0.04)]',
        className
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">Review</Badge>
          {typeLabel && <Badge variant="outline">{typeLabel}</Badge>}
          {draft.image_generating && (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> Image generating...
            </span>
          )}
        </div>
        <Link
          to={routes.draft(draft.id)}
          className="inline-flex items-center gap-1 text-xs font-medium text-[#0a66c2] hover:underline"
        >
          Edit <ExternalLink className="h-3 w-3" />
        </Link>
      </div>

      <div className="border-y border-[var(--color-border)] bg-[#f3f2ef]">
        <LinkedInPreview
          authorName={authorName}
          authorHeadline={authorHeadline}
          hook={draft.hook || undefined}
          body={draft.body || undefined}
          hashtags={draft.hashtags || []}
          imageUrl={draft.image_url}
          className="rounded-none border-0 shadow-none"
        />
      </div>

      {!draft.image_url && !draft.image_generating && (
        <p className="px-4 py-2 text-xs text-muted-foreground">
          Image pending - approve copy now, or regenerate the post from the backend.
        </p>
      )}

      <div className="flex flex-wrap gap-2 px-4 py-3">
        <Button size="sm" disabled={blocked} onClick={() => onApprove(draft.id)}>
          {busy === 'approve' ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <ThumbsUp className="h-3.5 w-3.5" />
          )}
          Approve
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={blocked}
          onClick={() => onReject(draft.id)}
        >
          {busy === 'reject' ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <ThumbsDown className="h-3.5 w-3.5" />
          )}
          Reject
        </Button>
        {onRegenerate && (
          <Button
            size="sm"
            variant="ghost"
            disabled={blocked}
            onClick={() => onRegenerate(draft.id)}
          >
            {busy === 'regenerate' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Regenerate
          </Button>
        )}
      </div>
    </article>
  );
}

export function ReviewQueueEmpty({
  onRegenerate,
  regenerating,
}: {
  onRegenerate?: () => void;
  regenerating?: boolean;
} = {}) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)]/50 px-6 py-10 text-center">
      <CheckCircle2 className="mx-auto h-9 w-9 text-muted-foreground/40" />
      <p className="mt-3 text-base font-semibold tracking-tight">No LinkedIn-ready posts yet</p>
      <p className="mx-auto mt-1.5 max-w-md text-sm text-muted-foreground">
        Regenerate the plan from the backend to fill your brand mix with copy + one image per post.
      </p>
      {onRegenerate && (
        <Button className="mt-5" onClick={onRegenerate} disabled={regenerating}>
          {regenerating ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          {regenerating ? 'Regenerating...' : 'Regenerate plan'}
        </Button>
      )}
    </div>
  );
}
