import { cn } from '@/lib/utils';
import type { PlanSlot } from './types';

const TYPE_LABEL: Record<string, string> = {
  educational: 'Edu',
  success_story: 'Success',
  personal_achievement: 'Personal',
};

export function PlanSlots({
  slots,
  className,
}: {
  slots?: PlanSlot[];
  className?: string;
}) {
  if (!slots?.length) return null;

  return (
    <section className={cn('space-y-2', className)} aria-label="Plan slots">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold tracking-tight">Calendar slots</h2>
        <p className="text-xs text-muted-foreground">Suggested mix for open days</p>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {slots.map((slot) => {
          const assigned = slot.items[0];
          const typeKey = assigned?.content_type || slot.suggested_content_type || '';
          const typeLabel = TYPE_LABEL[typeKey] || (slot.open ? 'Open' : 'Set');
          return (
            <div
              key={slot.date}
              className={cn(
                'min-w-[4.75rem] flex-1 rounded-xl border px-2.5 py-2',
                slot.open
                  ? 'border-dashed border-[var(--color-border)] bg-transparent'
                  : 'border-[var(--color-border)] bg-[var(--color-surface)]'
              )}
            >
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {slot.label}
              </p>
              <p className="mt-1 text-xs font-medium text-foreground">{typeLabel}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
