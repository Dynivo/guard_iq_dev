import { cn } from '@/lib/utils';
import type { ConfidenceFactors } from './types';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/design-system/ui/tooltip';

const FACTORS: { key: keyof ConfidenceFactors; label: string }[] = [
  { key: 'trend', label: 'Trend' },
  { key: 'audience_fit', label: 'Audience fit' },
  { key: 'authority', label: 'Authority' },
  { key: 'timing', label: 'Timing' },
  { key: 'competition', label: 'Competition' },
  { key: 'freshness', label: 'Freshness' },
];

export function ConfidenceBreakdown({
  confidence,
  className,
}: {
  confidence: ConfidenceFactors;
  className?: string;
}) {
  return (
    <TooltipProvider>
      <div className={cn('space-y-2', className)}>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-semibold tabular-nums">{confidence.composite}</span>
          <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
            Estimated
          </span>
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
          {FACTORS.map(({ key, label }) => (
            <div key={key} className="flex items-center justify-between gap-2 text-xs">
              <Tooltip>
                <TooltipTrigger asChild>
                  <dt className="cursor-help text-muted-foreground underline-offset-2 hover:underline">
                    {label}
                  </dt>
                </TooltipTrigger>
                <TooltipContent>Estimated from relevance, trends, and brand fit</TooltipContent>
              </Tooltip>
              <dd className="tabular-nums font-medium">{confidence[key]}</dd>
            </div>
          ))}
        </dl>
      </div>
    </TooltipProvider>
  );
}
