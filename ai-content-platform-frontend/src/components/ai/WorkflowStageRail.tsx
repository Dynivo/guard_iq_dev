import { cn } from '@/lib/utils';

/** Simple user-facing stages — hide internal pipeline jargon. */
export const WORKFLOW_STAGES = ['News', 'Draft', 'Visuals', 'Done'] as const;

export type WorkflowStage = (typeof WORKFLOW_STAGES)[number];

/** Map legacy stage names used around the app onto the simplified rail. */
const LEGACY_MAP: Record<string, WorkflowStage> = {
  News: 'News',
  Knowledge: 'News',
  Planning: 'Draft',
  Prompt: 'Draft',
  Generation: 'Draft',
  Image: 'Visuals',
  Typography: 'Visuals',
  Carousel: 'Visuals',
  Review: 'Done',
  Draft: 'Draft',
  Visuals: 'Visuals',
  Done: 'Done',
};

interface WorkflowStageRailProps {
  current: WorkflowStage | string;
  className?: string;
}

export function WorkflowStageRail({ current, className }: WorkflowStageRailProps) {
  const resolved = LEGACY_MAP[current] || 'Draft';
  const idx = WORKFLOW_STAGES.indexOf(resolved as WorkflowStage);
  return (
    <ol
      className={cn('flex flex-wrap items-center gap-1 text-xs', className)}
      aria-label="Simple workflow"
    >
      {WORKFLOW_STAGES.map((stage, i) => {
        const active = i === idx;
        const done = i < idx;
        return (
          <li key={stage} className="flex items-center gap-1">
            <span
              className={cn(
                'rounded-lg px-2 py-1 font-medium',
                active && 'bg-accent text-accent-foreground',
                done && !active && 'bg-success/10 text-success',
                !done && !active && 'bg-muted text-muted-foreground'
              )}
            >
              {stage}
            </span>
            {i < WORKFLOW_STAGES.length - 1 && (
              <span className="text-muted-foreground" aria-hidden>
                →
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
