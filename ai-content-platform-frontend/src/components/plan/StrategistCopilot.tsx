import { Check, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/design-system/ui/button';
import { cn } from '@/lib/utils';
import type { StrategistBriefing } from './types';

export function StrategistCopilot({
  data,
  onRecommend,
  onRegenerate,
  regenerating,
  className,
}: {
  data: StrategistBriefing;
  onRecommend?: (opportunityId: string, articleId?: string) => void;
  onRegenerate?: () => void;
  regenerating?: boolean;
  className?: string;
}) {
  const action = data.recommended_action;
  const isRegen = action?.action === 'regenerate_plan';

  return (
    <aside
      className={cn(
        'sticky top-6 space-y-5 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5',
        className
      )}
      aria-label="AI Strategist"
    >
      <div>
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Strategist
        </p>
        <p className="mt-1 text-base font-semibold tracking-tight">{data.greeting}</p>
      </div>

      <div className="space-y-2 text-sm leading-relaxed text-muted-foreground">
        {data.narrative.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>

      {(isRegen ? onRegenerate : action) && (
        <div className="space-y-2 border-t border-[var(--color-border)] pt-4">
          <p className="text-xs font-medium text-foreground">Recommended action</p>
          <Button
            className="w-full justify-start"
            disabled={isRegen && regenerating}
            onClick={() => {
              if (isRegen && onRegenerate) {
                onRegenerate();
                return;
              }
              if (action) onRecommend?.(action.opportunity_id, action.primary_article_id);
            }}
          >
            {isRegen && regenerating ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : isRegen ? (
              <RefreshCw className="mr-2 h-4 w-4" />
            ) : (
              <Check className="mr-2 h-4 w-4" />
            )}
            {action?.label || 'Regenerate plan'}
          </Button>
        </div>
      )}

      {(data.memory?.length ?? 0) > 0 && (
        <div className="space-y-2 border-t border-[var(--color-border)] pt-4">
          <p className="text-xs font-medium text-foreground">Memory</p>
          <ul className="space-y-1.5 text-xs text-muted-foreground">
            {data.memory!.map((m) => (
              <li key={m}>· {m}</li>
            ))}
          </ul>
        </div>
      )}

      {data.spacing_hint && (
        <p className="text-xs text-muted-foreground">{data.spacing_hint}</p>
      )}

      {(data.generate_first?.length ?? 0) > 0 && (
        <div className="space-y-2 border-t border-[var(--color-border)] pt-4">
          <p className="text-xs font-medium">Top opportunities</p>
          <ul className="space-y-2">
            {data.generate_first!.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="flex w-full items-baseline justify-between gap-2 text-left text-sm hover:text-accent"
                  onClick={() => onRecommend?.(item.id, item.primary_article_id)}
                >
                  <span className="line-clamp-2">{item.title}</span>
                  <span className="shrink-0 tabular-nums text-muted-foreground">{item.score}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
