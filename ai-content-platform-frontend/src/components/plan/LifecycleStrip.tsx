import { cn } from '@/lib/utils';

const STAGES = [
  'discovered',
  'scored',
  'recommended',
  'generated',
  'reviewed',
  'approved',
  'published',
  'learning_updated',
] as const;

const LABELS: Record<string, string> = {
  discovered: 'Discovered',
  scored: 'Scored',
  recommended: 'Recommended',
  generated: 'Generated',
  reviewed: 'Reviewed',
  approved: 'Approved',
  published: 'Published',
  learning_updated: 'Learning',
};

export function LifecycleStrip({
  stage,
  className,
}: {
  stage: string;
  className?: string;
}) {
  const idx = Math.max(0, STAGES.indexOf(stage as (typeof STAGES)[number]));
  return (
    <ol
      className={cn('flex flex-wrap items-center gap-1', className)}
      aria-label="Opportunity lifecycle"
    >
      {STAGES.map((s, i) => {
        const active = i === idx;
        const done = i < idx;
        return (
          <li key={s} className="flex items-center gap-1">
            <span
              className={cn(
                'rounded px-1.5 py-0.5 text-[10px] font-medium',
                active && 'bg-accent/15 text-accent',
                done && !active && 'text-muted-foreground',
                !done && !active && 'text-muted-foreground/50'
              )}
            >
              {LABELS[s]}
            </span>
            {i < STAGES.length - 1 && (
              <span className="text-[10px] text-muted-foreground/40">→</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
