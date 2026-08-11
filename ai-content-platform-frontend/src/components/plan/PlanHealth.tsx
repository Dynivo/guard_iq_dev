import { cn } from '@/lib/utils';

export function PlanHealth({
  counts,
  target,
  gaps,
  windowMode,
  className,
}: {
  counts?: Record<string, number>;
  target?: Record<string, number>;
  gaps?: Record<string, number>;
  windowMode?: string;
  className?: string;
}) {
  const rows = [
    { key: 'educational', label: 'Educational' },
    { key: 'success_story', label: 'Success' },
    { key: 'personal_achievement', label: 'Personal' },
  ];
  const modeLabel = windowMode === 'weekly' ? 'Weekly mix' : 'Fortnight mix';
  return (
    <section className={cn('space-y-2', className)} aria-label="Plan health">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        Plan health · {modeLabel}
      </p>
      <div className="flex flex-wrap gap-6">
        {rows.map(({ key, label }) => {
          const c = Number(counts?.[key] ?? 0);
          const t = Number(target?.[key] ?? 0);
          const g = Number(gaps?.[key] ?? 0);
          return (
            <div key={key}>
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="text-sm font-medium tabular-nums">
                {c}/{t}
                {g > 0 && (
                  <span className="ml-1.5 font-normal text-muted-foreground">
                    · {g} needed
                  </span>
                )}
                {g <= 0 && t > 0 && (
                  <span className="ml-1.5 font-normal text-muted-foreground">· ahead</span>
                )}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
