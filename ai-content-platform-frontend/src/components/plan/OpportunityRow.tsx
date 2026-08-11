import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/design-system/ui/badge';
import type { ContentOpportunity } from './types';
import { ConfidenceBreakdown } from './ConfidenceBreakdown';
import { DecisionPanel } from './DecisionPanel';
import { LifecycleStrip } from './LifecycleStrip';
import { SimilarPosts, SourceBreakdown } from './SourceBreakdown';

export function OpportunityRow({
  opportunity,
  busy,
  onGenerate,
  onSave,
  onIgnore,
  className,
}: {
  opportunity: ContentOpportunity;
  busy?: boolean;
  onGenerate: (opp: ContentOpportunity) => void;
  onSave: (opp: ContentOpportunity) => void;
  onIgnore: (opp: ContentOpportunity) => void;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [explain, setExplain] = useState(false);
  const o = opportunity;

  return (
    <article
      className={cn(
        'rounded-xl bg-[var(--color-surface)] px-4 py-4 transition-colors',
        className
      )}
    >
      <button
        type="button"
        className="flex w-full items-start justify-between gap-4 text-left"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-2xl font-semibold tabular-nums">{o.opportunity_score}</span>
            <Badge variant="secondary">{o.primary_angle}</Badge>
            {o.priority === 'high' && <Badge variant="default">High</Badge>}
            {o.sources.source_count != null && o.sources.source_count > 1 && (
              <span className="text-xs text-muted-foreground">
                {o.sources.source_count} sources
              </span>
            )}
          </div>
          <h3 className="text-base font-semibold leading-snug">{o.title}</h3>
          <p className="text-xs text-muted-foreground">
            {(o.audiences || []).join(' · ')}
            {o.timing_advice ? ` · ${o.timing_advice}` : ''}
          </p>
        </div>
        {open ? (
          <ChevronUp className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </button>

      <div className="mt-4">
        <DecisionPanel
          recommendation={o.recommendation}
          duplicate={o.duplicate}
          busy={busy}
          onGenerate={() => onGenerate(o)}
          onSave={() => onSave(o)}
          onIgnore={() => onIgnore(o)}
          onExplain={() => {
            setExplain((v) => !v);
            setOpen(true);
          }}
          explainOpen={explain}
        />
      </div>

      {open && (
        <div className="mt-5 space-y-5 border-t border-[var(--color-border)] pt-4">
          <LifecycleStrip stage={o.lifecycle_stage} />
          <ConfidenceBreakdown confidence={o.confidence} />
          <div>
            <p className="text-xs font-medium">Why this was selected</p>
            <ul className="mt-1.5 space-y-1 text-xs text-muted-foreground">
              {o.why_selected.map((w) => (
                <li key={w}>✓ {w}</li>
              ))}
            </ul>
          </div>
          {o.alt_angles?.length > 0 && (
            <div>
              <p className="text-xs font-medium">Alternative angles</p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {o.alt_angles.map((a) => (
                  <Badge key={a} variant="outline">
                    {a}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          <SourceBreakdown publishers={o.sources.by_publisher} />
          <SimilarPosts posts={o.similar_posts} note={o.similar_posts_note} />
          {o.fortnight_fit && (
            <p className="text-xs text-muted-foreground">
              Fortnight fit · {o.fortnight_fit.content_type} ·{' '}
              {o.fortnight_fit.gap_remaining ?? 0} gap remaining
            </p>
          )}
        </div>
      )}
    </article>
  );
}
