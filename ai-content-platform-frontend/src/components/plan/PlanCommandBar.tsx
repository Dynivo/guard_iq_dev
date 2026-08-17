import { CalendarX, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/design-system/ui/button';
import { cn } from '@/lib/utils';

export function PlanCommandBar({
  windowMode,
  windowStart,
  windowEnd,
  daysLeft,
  counts,
  target,
  gaps,
  inReviewCount,
  generating,
  seedingCalendar,
  clearingCalendar,
  onAutoGenerate,
  onSeedCalendar,
  onClearCalendar,
  className,
}: {
  windowMode?: string;
  windowStart?: string;
  windowEnd?: string;
  daysLeft?: number;
  counts?: Record<string, number>;
  target?: Record<string, number>;
  gaps?: Record<string, number>;
  inReviewCount?: number;
  generating?: boolean;
  seedingCalendar?: boolean;
  clearingCalendar?: boolean;
  onAutoGenerate: () => void;
  onSeedCalendar?: () => void;
  onClearCalendar?: () => void;
  className?: string;
}) {
  const totalT = Number(target?.total ?? 0) || 1;
  const totalC = ['educational', 'success_story', 'personal_achievement'].reduce(
    (sum, k) => sum + Number(counts?.[k] ?? 0),
    0
  );
  const pct = Math.min(100, Math.round((100 * totalC) / totalT));
  const openSlots = ['educational', 'success_story', 'personal_achievement'].reduce(
    (sum, k) => sum + Number(gaps?.[k] ?? 0),
    0
  );
  const modeLabel = windowMode === 'weekly' ? 'Weekly' : 'Fortnight';

  return (
    <section
      className={cn(
        'overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)]',
        className
      )}
      aria-label="Plan command bar"
    >
      <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
        <div className="flex min-w-0 items-center gap-4">
          <div
            className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full"
            style={{
              background: `conic-gradient(var(--color-accent) ${pct}%, var(--color-border) 0)`,
            }}
            aria-hidden
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[var(--color-surface)] text-sm font-semibold tabular-nums">
              {pct}%
            </div>
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              {modeLabel} plan
            </p>
            <p className="truncate text-base font-semibold tracking-tight">
              {totalC}/{totalT} scheduled
              {Number(inReviewCount ?? 0) > 0 && (
                <span className="ml-2 font-normal text-muted-foreground">
                  · {inReviewCount} awaiting review or date
                </span>
              )}
              {Number(inReviewCount ?? 0) === 0 &&
                (openSlots > 0 ? (
                  <span className="ml-2 font-normal text-muted-foreground">
                    · {openSlots} open
                  </span>
                ) : (
                  <span className="ml-2 font-normal text-muted-foreground">· mix filled</span>
                ))}
            </p>
            <p className="truncate text-xs text-muted-foreground">
              {windowStart && windowEnd
                ? `${windowStart} → ${windowEnd}`
                : 'Brand publishing window'}
              {daysLeft != null ? ` · ${daysLeft} workdays left` : ''}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {onClearCalendar && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="text-muted-foreground"
              onClick={onClearCalendar}
              disabled={clearingCalendar || seedingCalendar || generating}
              title="Unschedule every post from the calendar. Drafts stay in Drafts — nothing is deleted."
            >
              {clearingCalendar ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <CalendarX className="mr-1.5 h-3.5 w-3.5" />
              )}
              {clearingCalendar ? 'Clearing…' : 'Clear calendar'}
            </Button>
          )}
          {onSeedCalendar && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onSeedCalendar}
              disabled={seedingCalendar || generating || clearingCalendar}
            >
              {seedingCalendar ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : null}
              {seedingCalendar ? 'Seeding…' : 'Seed calendar'}
            </Button>
          )}
          <Button
            type="button"
            onClick={onAutoGenerate}
            disabled={generating || seedingCalendar || clearingCalendar}
            title="Generates educational posts only, from your scored news. New posts land in Drafts — approve them there to schedule."
          >
            {generating ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            {generating ? 'Generating…' : 'Auto Generate posts'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 divide-x divide-[var(--color-border)] border-t border-[var(--color-border)]">
        {(
          [
            { key: 'educational', label: 'Educational' },
            { key: 'success_story', label: 'Success' },
            { key: 'personal_achievement', label: 'Personal' },
          ] as const
        ).map(({ key, label }) => {
          const c = Number(counts?.[key] ?? 0);
          const t = Number(target?.[key] ?? 0);
          const g = Number(gaps?.[key] ?? 0);
          return (
            <div key={key} className="px-3 py-2.5 sm:px-4">
              <p className="text-[11px] text-muted-foreground">{label}</p>
              <p className="text-sm font-semibold tabular-nums">
                {c}/{t}
                {g > 0 && (
                  <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                    need {g}
                  </span>
                )}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
