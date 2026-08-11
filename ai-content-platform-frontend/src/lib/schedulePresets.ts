/** Human-friendly schedule presets ↔ cron for news source polling. */

export interface SchedulePreset {
  id: string;
  label: string;
  hint: string;
  cron: string;
}

export const SCHEDULE_PRESETS: SchedulePreset[] = [
  {
    id: 'manual',
    label: 'Manual only',
    hint: 'No automatic fetch — run from Sources when you want',
    cron: '',
  },
  {
    id: 'hourly',
    label: 'Every hour',
    hint: 'On the hour',
    cron: '0 * * * *',
  },
  {
    id: 'every_2h',
    label: 'Every 2 hours',
    hint: '0:00, 2:00, 4:00…',
    cron: '0 */2 * * *',
  },
  {
    id: 'every_4h',
    label: 'Every 4 hours',
    hint: 'At :30 past — 0:30, 4:30, 8:30…',
    cron: '30 */4 * * *',
  },
  {
    id: 'every_6h',
    label: 'Every 6 hours',
    hint: 'Four times a day',
    cron: '0 */6 * * *',
  },
  {
    id: 'twice_daily',
    label: 'Twice a day',
    hint: '8:00 and 20:00',
    cron: '0 8,20 * * *',
  },
  {
    id: 'daily_morning',
    label: 'Once a day (morning)',
    hint: 'Every day at 9:00',
    cron: '0 9 * * *',
  },
  {
    id: 'weekdays',
    label: 'Weekdays morning',
    hint: 'Mon–Fri at 9:00',
    cron: '0 9 * * 1-5',
  },
  {
    id: 'custom',
    label: 'Custom…',
    hint: 'Advanced cron (for technical setups)',
    cron: '__custom__',
  },
];

function normalizeCron(cron: string): string {
  return cron.trim().replace(/\s+/g, ' ');
}

/** Map a stored cron string back to a preset id (or custom). */
export function cronToPresetId(cron: string | null | undefined): string {
  const n = normalizeCron(cron || '');
  if (!n) return 'manual';
  const match = SCHEDULE_PRESETS.find((p) => p.cron !== '__custom__' && p.cron === n);
  return match?.id ?? 'custom';
}

export function presetIdToCron(presetId: string, customCron = ''): string {
  if (presetId === 'custom') return normalizeCron(customCron);
  const preset = SCHEDULE_PRESETS.find((p) => p.id === presetId);
  if (!preset || preset.cron === '__custom__') return normalizeCron(customCron);
  return preset.cron;
}

export function describeCron(cron: string | null | undefined): string {
  const id = cronToPresetId(cron);
  if (id === 'custom') {
    const n = normalizeCron(cron || '');
    return n ? `Custom schedule (${n})` : 'Manual only';
  }
  const preset = SCHEDULE_PRESETS.find((p) => p.id === id);
  return preset ? `${preset.label} — ${preset.hint}` : 'Manual only';
}
