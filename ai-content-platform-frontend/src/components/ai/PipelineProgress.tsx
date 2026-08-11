import { Check, Circle, Loader2, AlertTriangle } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import * as React from 'react';
import { cn } from '@/lib/utils';
import { Badge } from '@/design-system/ui/badge';

export type PipelineStepStatus = 'completed' | 'running' | 'waiting' | 'pending' | 'failed';

export interface PipelineStep {
  id: string;
  label: string;
  status: PipelineStepStatus;
  detail?: string;
  provider?: string;
  tokens?: number;
  costUsd?: number;
  latencyMs?: number;
  correlationId?: string;
  retryCount?: number;
}

const statusIcon = {
  completed: Check,
  running: Loader2,
  waiting: AlertTriangle,
  pending: Circle,
  failed: AlertTriangle,
} as const;

const statusColor: Record<PipelineStepStatus, string> = {
  completed: 'text-success',
  running: 'text-accent',
  waiting: 'text-warning',
  pending: 'text-muted-foreground',
  failed: 'text-destructive',
};

interface PipelineProgressProps {
  steps: PipelineStep[];
  className?: string;
}

export function PipelineProgress({ steps, className }: PipelineProgressProps) {
  const [openId, setOpenId] = React.useState<string | null>(
    steps.find((s) => s.status === 'running')?.id ?? null
  );

  return (
    <ol className={cn('space-y-1', className)} aria-label="AI pipeline progress">
      {steps.map((step) => {
        const Icon = statusIcon[step.status];
        const expanded = openId === step.id;
        return (
          <li key={step.id} className="rounded-[var(--radius)] border border-border bg-card">
            <button
              type="button"
              className="flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm hover:bg-hover"
              onClick={() => setOpenId(expanded ? null : step.id)}
              aria-expanded={expanded}
            >
              <Icon
                className={cn(
                  'h-4 w-4 shrink-0',
                  statusColor[step.status],
                  step.status === 'running' && 'animate-spin'
                )}
                aria-hidden
              />
              <span className="flex-1 font-medium">{step.label}</span>
              <Badge
                variant={
                  step.status === 'completed'
                    ? 'success'
                    : step.status === 'failed'
                      ? 'destructive'
                      : step.status === 'running'
                        ? 'default'
                        : 'secondary'
                }
              >
                {step.status}
              </Badge>
            </button>
            <AnimatePresence>
              {expanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.18 }}
                  className="overflow-hidden border-t border-border"
                >
                  <div className="grid gap-2 px-3 py-3 text-xs text-muted-foreground sm:grid-cols-2">
                    {step.detail && <p className="sm:col-span-2">{step.detail}</p>}
                    {step.provider && <p>Provider: {step.provider}</p>}
                    {step.tokens != null && <p>Tokens: {step.tokens}</p>}
                    {step.costUsd != null && <p>Cost: ${step.costUsd.toFixed(4)}</p>}
                    {step.latencyMs != null && <p>Latency: {step.latencyMs} ms</p>}
                    {step.retryCount != null && <p>Retries: {step.retryCount}</p>}
                    {step.correlationId && (
                      <p className="font-mono sm:col-span-2">correlation: {step.correlationId}</p>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </li>
        );
      })}
    </ol>
  );
}
