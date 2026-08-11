import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { useApiQuery } from '@/hooks/useApiQuery';
import { apiClient } from '@/api/client';
import type { ApiEnvelope } from '@/api/types';
import { Button } from '@/design-system/ui/button';
import { Skeleton } from '@/design-system/ui/skeleton';
import { ErrorState } from '@/components/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { toast } from 'sonner';
import { routes } from '@/lib/routes';
import { cn } from '@/lib/utils';

export interface CalendarEvent {
  id: string;
  draft_id?: string | null;
  kind: 'post' | 'plan_slot' | string;
  title: string;
  content_type?: string | null;
  mix_type?: string | null;
  status?: string | null;
  date?: string | null;
  suggested?: boolean;
}

export interface CalendarDayCell {
  date: string;
  day: number;
  in_month: boolean;
  is_today: boolean;
  is_weekend: boolean;
  events: CalendarEvent[];
}

export interface CalendarMonthView {
  year: number;
  month: number;
  month_label: string;
  weeks: CalendarDayCell[][];
  unscheduled?: CalendarEvent[];
  quota_hint?: string;
}

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const;

const MIX_COLORS: Record<string, string> = {
  educational: 'bg-[#d3e3fd] text-[#0842a0] border-[#a8c7fa]',
  success_story: 'bg-[#ceead6] text-[#0d652d] border-[#a8dab5]',
  personal_achievement: 'bg-[#fde293] text-[#895304] border-[#fdd663]',
  plan_slot: 'bg-white text-[#5f6368] border-dashed border-[#dadce0]',
};

function eventClass(ev: CalendarEvent): string {
  if (ev.kind === 'plan_slot' || ev.suggested) {
    return MIX_COLORS.plan_slot;
  }
  const key = ev.mix_type || ev.content_type || '';
  return MIX_COLORS[key] || 'bg-[#e8f0fe] text-[#1967d2] border-[#aecbfa]';
}

export function MonthlyCalendar({
  className,
  title = 'Publishing calendar',
  compact = false,
}: {
  className?: string;
  title?: string;
  compact?: boolean;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [assigning, setAssigning] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useApiQuery<ApiEnvelope<CalendarMonthView>>(
    ['publishing-calendar', String(year), String(month)],
    `/publishing-plan/calendar?year=${year}&month=${month}`
  );

  const view = data?.data;
  const unscheduled = view?.unscheduled ?? [];

  const selectedEvents = useMemo(() => {
    if (!view || !selectedDate) return [];
    for (const week of view.weeks || []) {
      for (const day of week) {
        if (day.date === selectedDate) return day.events || [];
      }
    }
    return [];
  }, [view, selectedDate]);

  const shiftMonth = (delta: number) => {
    let m = month + delta;
    let y = year;
    if (m < 1) {
      m = 12;
      y -= 1;
    } else if (m > 12) {
      m = 1;
      y += 1;
    }
    setMonth(m);
    setYear(y);
    setSelectedDate(null);
  };

  const goToday = () => {
    const t = new Date();
    setYear(t.getFullYear());
    setMonth(t.getMonth() + 1);
    setSelectedDate(t.toISOString().slice(0, 10));
  };

  const assign = async (draftId: string, date: string) => {
    setAssigning(draftId);
    try {
      await apiClient.patch(`/drafts/${draftId}/schedule`, { scheduled_for: date });
      toast.success(`Scheduled for ${date}`);
      queryClient.invalidateQueries({ queryKey: ['publishing-calendar'] });
      queryClient.invalidateQueries({ queryKey: ['to-post'] });
      queryClient.invalidateQueries({ queryKey: ['strategist-briefing'] });
      queryClient.invalidateQueries({ queryKey: ['publishing-plan'] });
    } catch {
      toast.error('Could not schedule');
    } finally {
      setAssigning(null);
    }
  };

  const onEventClick = (ev: CalendarEvent) => {
    if (ev.draft_id) {
      navigate(routes.draft(ev.draft_id));
      return;
    }
    if (ev.kind === 'plan_slot') {
      toast.message('Open slot — regenerate the plan or capture a story to fill it');
    }
  };

  if (isLoading) {
    return (
      <div className={cn('space-y-3', className)}>
        <Skeleton className="h-10 w-64" />
        <Skeleton className={cn('w-full', compact ? 'h-80' : 'h-[32rem]')} />
      </div>
    );
  }

  if (isError || !view) {
    return <ErrorState message="Unable to load calendar." onRetry={refetch} />;
  }

  return (
    <section className={cn('space-y-4', className)} aria-label={title}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
          <p className="text-xs text-muted-foreground">
            {view.quota_hint || 'Brand publishing mix'} · AI plan posts only (manual News drafts excluded)
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Button type="button" variant="outline" size="sm" onClick={goToday}>
            Today
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-8 w-8"
            onClick={() => shiftMonth(-1)}
            aria-label="Previous month"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-8 w-8"
            onClick={() => shiftMonth(1)}
            aria-label="Next month"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <p className="min-w-[9rem] px-2 text-center text-sm font-semibold tabular-nums">
            {view.month_label}
          </p>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-[#dadce0] bg-white shadow-[0_1px_2px_rgba(60,64,67,0.15)]">
        <div className="grid grid-cols-7 border-b border-[#dadce0] bg-[#f8f9fa]">
          {WEEKDAYS.map((d) => (
            <div
              key={d}
              className="px-2 py-2 text-center text-[11px] font-semibold uppercase tracking-wide text-[#70757a]"
            >
              {d}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7">
          {(view.weeks || []).flat().map((day) => {
            const selected = selectedDate === day.date;
            const maxShow = compact ? 3 : 4;
            const extra = Math.max(0, (day.events?.length || 0) - maxShow);
            return (
              <button
                key={day.date}
                type="button"
                onClick={() => setSelectedDate(day.date)}
                className={cn(
                  'flex min-h-[6.5rem] flex-col border-b border-r border-[#dadce0] p-1.5 text-left transition-colors sm:min-h-[7.5rem]',
                  !day.in_month && 'bg-[#f8f9fa]',
                  day.is_weekend && day.in_month && 'bg-[#fafafa]',
                  selected && 'bg-[#e8f0fe] ring-2 ring-inset ring-[#1a73e8]',
                  compact && 'min-h-[5.5rem] sm:min-h-[6.25rem]'
                )}
              >
                <span
                  className={cn(
                    'mb-1 inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium',
                    day.is_today && 'bg-[#1a73e8] text-white',
                    !day.is_today && day.in_month && 'text-[#3c4043]',
                    !day.in_month && 'text-[#70757a]'
                  )}
                >
                  {day.day}
                </span>
                <div className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-hidden">
                  {(day.events || []).slice(0, maxShow).map((ev) => (
                    <span
                      key={ev.id}
                      role="link"
                      tabIndex={0}
                      onClick={(e) => {
                        e.stopPropagation();
                        onEventClick(ev);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.stopPropagation();
                          onEventClick(ev);
                        }
                      }}
                      className={cn(
                        'truncate rounded border px-1 py-0.5 text-[10px] font-medium leading-tight sm:text-[11px]',
                        eventClass(ev)
                      )}
                      title={ev.title}
                    >
                      {ev.title}
                    </span>
                  ))}
                  {extra > 0 && (
                    <span className="px-1 text-[10px] font-medium text-[#1967d2]">
                      +{extra} more
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {selectedDate ? `Selected · ${selectedDate}` : 'Select a day'}
          </p>
          {!selectedDate && (
            <p className="mt-2 text-sm text-muted-foreground">
              Click any day to see posts and plan slots, then schedule from Unscheduled.
            </p>
          )}
          {selectedDate && selectedEvents.length === 0 && (
            <p className="mt-2 text-sm text-muted-foreground">No posts on this day yet.</p>
          )}
          {selectedDate && selectedEvents.length > 0 && (
            <ul className="mt-3 space-y-2">
              {selectedEvents.map((ev) => (
                <li key={ev.id}>
                  <button
                    type="button"
                    className={cn(
                      'w-full rounded-lg border px-3 py-2 text-left text-sm',
                      eventClass(ev)
                    )}
                    onClick={() => onEventClick(ev)}
                  >
                    <p className="font-medium">{ev.title}</p>
                    <p className="mt-0.5 text-xs opacity-80">
                      {(ev.content_type || ev.kind || '').replace(/_/g, ' ')}
                      {ev.status ? ` · ${String(ev.status).replace(/_/g, ' ')}` : ''}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Unscheduled
          </p>
          {unscheduled.length === 0 ? (
            <EmptyState
              className="mt-2 border-0 p-0"
              title="None waiting"
              description="Approve drafts to schedule them on the calendar."
              actionLabel="Drafts"
              onAction={() => navigate(routes.drafts)}
            />
          ) : (
            <ul className="mt-3 max-h-64 space-y-2 overflow-y-auto">
              {unscheduled.map((item) => (
                <li
                  key={item.id}
                  className="rounded-lg border border-[var(--color-border)] bg-white px-3 py-2"
                >
                  <p className="line-clamp-2 text-sm font-medium">{item.title}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {(item.content_type || 'post').replace(/_/g, ' ')}
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="mt-2 w-full"
                    disabled={!selectedDate || assigning === item.draft_id}
                    onClick={() => {
                      if (!selectedDate || !item.draft_id) return;
                      void assign(item.draft_id, selectedDate);
                    }}
                  >
                    {assigning === item.draft_id ? (
                      <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                    ) : null}
                    {selectedDate ? `Schedule ${selectedDate.slice(5)}` : 'Select a day first'}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-[#d3e3fd]" /> Educational
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-[#ceead6]" /> Success
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-[#fde293]" /> Personal
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded border border-dashed border-[#dadce0] bg-white" />{' '}
          Plan slot
        </span>
      </div>
    </section>
  );
}
