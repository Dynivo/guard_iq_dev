import { useMemo, useState, type ReactNode } from 'react';
import { AuthenticatedImage } from '@/components/AuthenticatedImage';
import { cn } from '@/lib/utils';

interface LinkedInPreviewProps {
  authorName?: string;
  authorHeadline?: string;
  hook?: string;
  body?: string;
  cta?: string;
  hashtags?: string[];
  imageUrl?: string | null;
  className?: string;
}

/** Real LinkedIn feed post chrome (light feed card — how posts look when published). */
export function LinkedInPreview({
  authorName = 'You',
  authorHeadline = 'Content Intelligence · AI Content Platform',
  hook,
  body,
  cta,
  hashtags = [],
  imageUrl,
  className,
}: LinkedInPreviewProps) {
  const [expanded, setExpanded] = useState(false);

  const text = useMemo(() => {
    const tags = hashtags.map((t) => (t.startsWith('#') ? t : `#${t}`)).join(' ');
    return [hook, body, cta, tags].filter(Boolean).join('\n\n');
  }, [hook, body, cta, hashtags]);

  const initial = authorName.charAt(0).toUpperCase() || 'U';
  const needsSeeMore = text.length > 220;
  const displayText =
    !expanded && needsSeeMore ? `${text.slice(0, 220).trimEnd()}…` : text || 'Your post will appear here.';

  return (
    <div className={cn('overflow-hidden rounded-lg', className)}>
      {/* LinkedIn canvas + feed column */}
      <div className="bg-[#f3f2ef] px-3 py-3 sm:px-4">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-[#666666]">
          LinkedIn feed preview
        </p>

        <article className="overflow-hidden rounded-lg border border-[#e0e0e0] bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          {/* Author */}
          <header className="flex items-start gap-2 px-3 pb-1 pt-3 sm:px-4">
            <div
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-[18px] font-semibold text-white"
              style={{ background: 'linear-gradient(135deg, #0a66c2 0%, #004182 100%)' }}
              aria-hidden
            >
              {initial}
            </div>
            <div className="min-w-0 flex-1 leading-snug">
              <div className="flex items-baseline gap-1">
                <span className="truncate text-[14px] font-semibold text-[rgba(0,0,0,0.9)] hover:text-[#0a66c2] hover:underline">
                  {authorName}
                </span>
                <span className="shrink-0 text-[12px] text-[rgba(0,0,0,0.6)]">· 1st</span>
              </div>
              <p className="truncate text-[12px] text-[rgba(0,0,0,0.6)]">{authorHeadline}</p>
              <p className="flex items-center gap-1 text-[12px] text-[rgba(0,0,0,0.6)]">
                <span>Just now</span>
                <span aria-hidden>·</span>
                <GlobeIcon className="h-3 w-3" />
              </p>
            </div>
            <button
              type="button"
              className="rounded-full p-1.5 text-[rgba(0,0,0,0.6)] hover:bg-[rgba(0,0,0,0.08)]"
              aria-label="More"
            >
              <MoreIcon className="h-5 w-5" />
            </button>
          </header>

          {/* Copy */}
          <div className="px-3 pb-2 pt-1 sm:px-4">
            <p className="whitespace-pre-wrap text-[14px] leading-[1.4] text-[rgba(0,0,0,0.9)]">
              {displayText}
              {needsSeeMore && (
                <>
                  {' '}
                  <button
                    type="button"
                    className="inline font-semibold text-[rgba(0,0,0,0.6)] hover:text-[#0a66c2] hover:underline"
                    onClick={() => setExpanded((v) => !v)}
                  >
                    {expanded ? 'see less' : 'see more'}
                  </button>
                </>
              )}
            </p>
          </div>

          {/* Native image — LinkedIn shows full width, preserves aspect (no crop) */}
          {imageUrl && (
            <div className="w-full bg-[#f3f2ef]">
              <AuthenticatedImage
                src={imageUrl}
                alt="LinkedIn post image"
                className="block h-auto w-full object-contain"
              />
            </div>
          )}
          {imageUrl && (
            <p className="px-3 pb-1 pt-1 text-[11px] text-[rgba(0,0,0,0.45)] sm:px-4">
              Preview uses LinkedIn feed behaviour: full-width image, no cropping.
            </p>
          )}

          {/* Social proof */}
          <div className="flex items-center justify-between gap-2 px-3 py-2 sm:px-4">
            <div className="flex items-center gap-1.5">
              <div className="flex -space-x-1">
                <ReactionBubble className="bg-[#378fe9]" title="Like">
                  <ThumbIcon className="h-2.5 w-2.5 text-white" />
                </ReactionBubble>
                <ReactionBubble className="bg-[#5f9b41]" title="Celebrate">
                  <ClapIcon className="h-2.5 w-2.5 text-white" />
                </ReactionBubble>
                <ReactionBubble className="bg-[#a243b3]" title="Love">
                  <HeartIcon className="h-2.5 w-2.5 text-white" />
                </ReactionBubble>
              </div>
              <span className="text-[12px] text-[rgba(0,0,0,0.6)] hover:text-[#0a66c2] hover:underline">
                24
              </span>
            </div>
            <div className="flex gap-1 text-[12px] text-[rgba(0,0,0,0.6)]">
              <span className="hover:text-[#0a66c2] hover:underline">3 comments</span>
              <span>·</span>
              <span className="hover:text-[#0a66c2] hover:underline">1 repost</span>
            </div>
          </div>

          <div className="mx-3 border-t border-[#e0e0e0] sm:mx-4" />

          {/* Actions */}
          <div className="grid grid-cols-4 px-1 py-1 sm:px-2">
            <Action label="Like" icon={<LikeOutline className="h-5 w-5" />} />
            <Action label="Comment" icon={<CommentOutline className="h-5 w-5" />} />
            <Action label="Repost" icon={<RepostOutline className="h-5 w-5" />} />
            <Action label="Send" icon={<SendOutline className="h-5 w-5" />} />
          </div>
        </article>
      </div>
    </div>
  );
}

function ReactionBubble({
  className,
  children,
  title,
}: {
  className?: string;
  children: ReactNode;
  title: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex h-4 w-4 items-center justify-center rounded-full ring-2 ring-white',
        className
      )}
    >
      {children}
    </span>
  );
}

function Action({ label, icon }: { label: string; icon: ReactNode }) {
  return (
    <div className="flex cursor-default items-center justify-center gap-1.5 rounded-md py-2.5 text-[13px] font-semibold text-[rgba(0,0,0,0.6)] hover:bg-[rgba(0,0,0,0.08)]">
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </div>
  );
}

function GlobeIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" className={className} aria-hidden>
      <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1ZM2.05 7.5h2.23c.07-1.3.36-2.52.84-3.54A5.52 5.52 0 0 0 2.05 7.5Zm3.73 0h4.44c-.08-1.4-.42-2.7-1-3.65C8.75 2.98 8.3 2.5 8 2.5s-.75.48-1.22 1.35c-.58.95-.92 2.25-1 3.65Zm4.44 1H5.78c.08 1.4.42 2.7 1 3.65.47.87.92 1.35 1.22 1.35s.75-.48 1.22-1.35c.58-.95.92-2.25 1-3.65Zm1.5 0h2.23a5.52 5.52 0 0 1-3.07 3.54c.48-1.02.77-2.24.84-3.54Zm0-1A9.7 9.7 0 0 0 10.88 4a5.52 5.52 0 0 1 3.07 3.5H11.72ZM5.12 4A9.7 9.7 0 0 0 4.28 7.5H2.05A5.52 5.52 0 0 1 5.12 4Zm0 8a5.52 5.52 0 0 1-3.07-3.5h2.23c.07 1.3.36 2.52.84 3.5Zm5.76 0c.48-.98.77-2.2.84-3.5h2.23A5.52 5.52 0 0 1 10.88 12Z" />
    </svg>
  );
}

function MoreIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <circle cx="12" cy="5" r="2" />
      <circle cx="12" cy="12" r="2" />
      <circle cx="12" cy="19" r="2" />
    </svg>
  );
}

function ThumbIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M19.46 11l-3.91-3.91a7 7 0 0 1-1.69-4.51V2a1 1 0 0 0-1-1 5 5 0 0 0-5 5v.5H3.5A1.5 1.5 0 0 0 2 8v10.5A1.5 1.5 0 0 0 3.5 20h12.05a3 3 0 0 0 2.8-1.95l2.26-5.66A2.5 2.5 0 0 0 19.46 11Z" />
    </svg>
  );
}

function ClapIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M12.7 2.3a1 1 0 0 0-1.4 0L9.3 4.3a1 1 0 0 0 1.4 1.4l1.3-1.3 1.3 1.3a1 1 0 1 0 1.4-1.4l-2-2ZM5.8 8.5 4.5 9.8a1 1 0 0 0 1.4 1.4l1.3-1.3 1.3 1.3a1 1 0 0 0 1.4-1.4L8.6 8.5a1 1 0 0 0-1.4 0L5.8 8.5Zm12.4 0-1.3 1.3a1 1 0 1 0 1.4 1.4l1.3-1.3 1.3 1.3a1 1 0 0 0 1.4-1.4L19.6 8.5a1 1 0 0 0-1.4 0ZM8.5 12.2l-1.5 1.5a4 4 0 0 0 0 5.6l.7.7a4 4 0 0 0 5.6 0l4.2-4.2a2 2 0 0 0-2.8-2.8l-2.1 2.1-.7-.7 2.8-2.8a2 2 0 1 0-2.8-2.8l-2.1 2.1-.7-.7 1.4-1.4a2 2 0 0 0-2.8-2.8l-2.2 2.2Z" />
    </svg>
  );
}

function HeartIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M12 21s-7.2-4.35-9.6-8.4C.6 9.3 2.1 5.5 5.7 5.5c2 0 3.4 1.1 4.3 2.3.9-1.2 2.3-2.3 4.3-2.3 3.6 0 5.1 3.8 3.3 7.1C19.2 16.65 12 21 12 21Z" />
    </svg>
  );
}

function LikeOutline({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden>
      <path d="M7 11v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1h3Zm0 0 4.2-7.1A2 2 0 0 1 13 3a2.5 2.5 0 0 1 2.5 2.5V9H20a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 18.8 20H9" />
    </svg>
  );
}

function CommentOutline({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden>
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8A2.5 2.5 0 0 1 17.5 16H10l-4.5 4v-4H6.5A2.5 2.5 0 0 1 4 13.5v-8Z" />
    </svg>
  );
}

function RepostOutline({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden>
      <path d="M7 7h9a3 3 0 0 1 3 3v2M17 17H8a3 3 0 0 1-3-3v-2" />
      <path d="m14 4 3 3-3 3M10 20l-3-3 3-3" />
    </svg>
  );
}

function SendOutline({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden>
      <path d="M21 4 10.5 14.5M21 4l-7 17-3.5-6.5L4 11l17-7Z" />
    </svg>
  );
}
