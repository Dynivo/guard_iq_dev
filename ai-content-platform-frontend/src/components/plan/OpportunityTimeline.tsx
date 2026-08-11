import { cn } from '@/lib/utils';
import type { ContentOpportunity } from './types';

const BUCKETS: { key: string; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: 'this_week', label: 'This week' },
  { key: 'later', label: 'Later' },
];

export function OpportunityTimeline({
  active,
  onChange,
  counts,
  className,
}: {
  active: string;
  onChange: (bucket: string) => void;
  counts: Record<string, number>;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-wrap gap-2', className)} role="tablist" aria-label="Timeline">
      {BUCKETS.map(({ key, label }) => {
        const selected = active === key;
        return (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={selected}
            className={cn(
              'rounded-lg px-3 py-1.5 text-sm transition-colors',
              selected
                ? 'bg-accent text-accent-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
            onClick={() => onChange(key)}
          >
            {label}
            <span className="ml-1.5 tabular-nums opacity-70">{counts[key] ?? 0}</span>
          </button>
        );
      })}
    </div>
  );
}

export function filterByBucket(
  items: ContentOpportunity[],
  bucket: string
): ContentOpportunity[] {
  return items.filter((o) => (o.timeline_bucket || 'later') === bucket);
}
