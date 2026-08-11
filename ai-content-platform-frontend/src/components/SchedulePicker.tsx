import { useState } from 'react';
import { SCHEDULE_PRESETS, cronToPresetId, describeCron, presetIdToCron } from '@/lib/schedulePresets';
import { Input } from '@/design-system/ui/input';
import { cn } from '@/lib/utils';

interface SchedulePickerProps {
  value: string;
  onChange: (cron: string) => void;
  className?: string;
}

/** Default when opening Custom from an empty/manual schedule (must not match a preset). */
const CUSTOM_SEED = '15 */3 * * *';

export function SchedulePicker({ value, onChange, className }: SchedulePickerProps) {
  const matchedId = cronToPresetId(value);
  // Stay on Custom even if the cron still matches a preset (e.g. user just opened Custom).
  const [forceCustom, setForceCustom] = useState(matchedId === 'custom');

  const isCustom = forceCustom || matchedId === 'custom';
  const selectValue = isCustom ? 'custom' : matchedId;

  return (
    <div className={cn('space-y-2', className)}>
      <label className="block space-y-1 text-sm">
        <span className="text-muted-foreground">How often should we fetch?</span>
        <select
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          value={selectValue}
          onChange={(e) => {
            const id = e.target.value;
            if (id === 'custom') {
              setForceCustom(true);
              if (!value?.trim()) onChange(CUSTOM_SEED);
              return;
            }
            setForceCustom(false);
            onChange(presetIdToCron(id));
          }}
        >
          {SCHEDULE_PRESETS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      <p className="text-xs text-muted-foreground">
        {isCustom && matchedId !== 'custom'
          ? 'Enter a custom cron below, or pick a preset above.'
          : describeCron(value)}
      </p>
      {isCustom && (
        <label className="block space-y-1 text-sm">
          <span className="text-muted-foreground">Custom cron (minute hour day month weekday)</span>
          <Input
            placeholder="30 */4 * * *"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            autoFocus
          />
          <span className="text-xs text-muted-foreground">
            Example: <code className="rounded bg-muted px-1">0 */3 * * *</code> every 3 hours
          </span>
        </label>
      )}
    </div>
  );
}
