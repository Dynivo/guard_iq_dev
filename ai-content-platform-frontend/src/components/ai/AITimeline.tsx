import { motion } from 'motion/react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

export interface TimelineEvent {
  id: string;
  at: string | Date;
  label: string;
  detail?: string;
}

interface AITimelineProps {
  events: TimelineEvent[];
  className?: string;
}

export function AITimeline({ events, className }: AITimelineProps) {
  return (
    <ol className={cn('relative space-y-0', className)} aria-label="AI timeline">
      {events.map((ev, i) => {
        const at = typeof ev.at === 'string' ? new Date(ev.at) : ev.at;
        return (
          <motion.li
            key={ev.id}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.18, delay: i * 0.04 }}
            className="relative flex gap-4 pb-6 last:pb-0"
          >
            <div className="flex flex-col items-center">
              <span className="mt-1 h-2.5 w-2.5 rounded-full bg-accent" />
              {i < events.length - 1 && <span className="mt-1 w-px flex-1 bg-border" />}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs tabular-nums text-muted-foreground">
                {Number.isNaN(at.getTime()) ? '—' : format(at, 'HH:mm:ss')}
              </p>
              <p className="text-sm font-medium">{ev.label}</p>
              {ev.detail && <p className="text-xs text-muted-foreground">{ev.detail}</p>}
            </div>
          </motion.li>
        );
      })}
    </ol>
  );
}
