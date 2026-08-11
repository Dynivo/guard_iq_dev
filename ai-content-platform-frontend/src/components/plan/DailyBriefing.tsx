import { cn } from '@/lib/utils';
import type { StrategistBriefing } from './types';

const METRICS: { key: keyof StrategistBriefing['briefing']; label: string }[] = [
  { key: 'articles_analysed', label: 'Analysed' },
  { key: 'opportunities', label: 'Opportunities' },
  { key: 'trends', label: 'Trends' },
  { key: 'high_priority', label: 'High priority' },
  { key: 'recommended_today', label: 'Recommended today' },
  { key: 'already_scheduled', label: 'Scheduled' },
  { key: 'needs_review', label: 'Needs review' },
];

export function DailyBriefing({
  briefing,
  className,
}: {
  briefing: StrategistBriefing['briefing'];
  className?: string;
}) {
  return (
    <section className={cn('space-y-3', className)} aria-label="Today's briefing">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-lg font-semibold tracking-tight">Today&apos;s Briefing</h2>
        <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
          {briefing.label || 'estimated'}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4 lg:grid-cols-7">
        {METRICS.map(({ key, label }) => (
          <div key={key} className="min-w-0">
            <p className="text-[11px] text-muted-foreground">{label}</p>
            <p className="text-2xl font-semibold tabular-nums tracking-tight">
              {Number(briefing[key] ?? 0)}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
