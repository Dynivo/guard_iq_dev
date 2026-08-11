import { Button } from '@/design-system/ui/button';
import { cn } from '@/lib/utils';
import type { OpportunityRecommendation } from './types';

function Stars({ n }: { n: number }) {
  return (
    <span className="tracking-tight text-foreground" aria-label={`${n} of 5`}>
      {'★'.repeat(n)}
      <span className="text-muted-foreground/40">{'★'.repeat(Math.max(0, 5 - n))}</span>
    </span>
  );
}

export function DecisionPanel({
  recommendation,
  duplicate,
  busy,
  onGenerate,
  onSave,
  onIgnore,
  onExplain,
  explainOpen,
  className,
}: {
  recommendation: OpportunityRecommendation;
  duplicate?: { already_covered?: boolean; covered_at?: string | null };
  busy?: boolean;
  onGenerate: () => void;
  onSave: () => void;
  onIgnore: () => void;
  onExplain: () => void;
  explainOpen?: boolean;
  className?: string;
}) {
  return (
    <div className={cn('space-y-3', className)}>
      <div>
        <p className="text-xs font-medium">AI recommendation</p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm">
          <Stars n={recommendation.stars} />
          <span className="text-muted-foreground">
            {recommendation.should_generate ? 'Generate' : 'Consider carefully'}
          </span>
        </div>
        <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
          {recommendation.why.map((w) => (
            <li key={w}>✓ {w}</li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-muted-foreground">
          Estimated {recommendation.estimated_read_minutes ?? 3} min read ·{' '}
          {recommendation.editing_effort || 'medium'} editing
        </p>
      </div>

      {duplicate?.already_covered && (
        <p className="text-xs text-warning">
          Already covered{duplicate.covered_at ? ` · ${duplicate.covered_at}` : ''}. Generate
          anyway?
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <Button size="sm" loading={busy} onClick={onGenerate}>
          Generate LinkedIn post
        </Button>
        <Button size="sm" variant="outline" onClick={onSave}>
          Save for Later
        </Button>
        <Button size="sm" variant="ghost" onClick={onIgnore}>
          Ignore
        </Button>
        <Button size="sm" variant="ghost" onClick={onExplain}>
          {explainOpen ? 'Hide why' : 'Explain'}
        </Button>
      </div>
    </div>
  );
}
