import * as React from 'react';
import { HelpCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/design-system/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/design-system/ui/dialog';

interface ExplainScoreProps {
  score: number | string;
  title?: string;
  reasons: string[];
  className?: string;
}

export function ExplainScore({ score, title = 'Why this score?', reasons, className }: ExplainScoreProps) {
  const display = typeof score === 'number' ? `${Math.round(score * (score <= 1 ? 100 : 1))}%` : score;
  return (
    <div className={cn('inline-flex items-center gap-1.5', className)}>
      <span className="text-sm font-semibold tabular-nums">{display}</span>
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="ghost" size="icon" className="h-6 w-6" aria-label="Explain score">
            <HelpCircle className="h-3.5 w-3.5 text-muted-foreground" />
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>Explainability from scored signals (read-only).</DialogDescription>
          </DialogHeader>
          <ul className="space-y-2">
            {reasons.map((r) => (
              <li key={r} className="flex items-start gap-2 text-sm">
                <span className="mt-1 text-success">✓</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>
    </div>
  );
}
