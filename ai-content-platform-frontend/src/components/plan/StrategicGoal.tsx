import { cn } from '@/lib/utils';
import type { StrategistBriefing } from './types';

export function StrategicGoal({
  goal,
  className,
}: {
  goal: StrategistBriefing['strategic_goal'];
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, Number(goal.progress_pct || 0)));
  return (
    <section className={cn('space-y-3', className)} aria-label="Strategic goal">
      <div>
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Your goal
        </p>
        <p className="mt-1 max-w-2xl text-base font-medium leading-snug">{goal.statement}</p>
      </div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] text-muted-foreground">Progress</p>
          <p className="text-2xl font-semibold tabular-nums">{pct}%</p>
        </div>
        <div className="min-w-[12rem] flex-1">
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-[var(--duration-normal)]"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Suggested next · {goal.suggested_next_topic}
          </p>
        </div>
      </div>
    </section>
  );
}
