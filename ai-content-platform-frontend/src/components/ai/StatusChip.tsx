import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const statusChipVariants = cva(
  'inline-flex items-center gap-1.5 rounded-lg border px-2 py-0.5 text-xs font-medium',
  {
    variants: {
      status: {
        queued: 'border-border bg-muted text-muted-foreground',
        waiting: 'border-warning/30 bg-warning/10 text-warning',
        running: 'border-accent/30 bg-accent/10 text-accent',
        completed: 'border-success/30 bg-success/10 text-success',
        success: 'border-success/30 bg-success/10 text-success',
        failed: 'border-destructive/30 bg-destructive/10 text-destructive',
        cancelled: 'border-border bg-muted text-muted-foreground',
        retrying: 'border-warning/30 bg-warning/10 text-warning',
        pending: 'border-border bg-muted text-muted-foreground',
        approved: 'border-success/30 bg-success/10 text-success',
        rejected: 'border-destructive/30 bg-destructive/10 text-destructive',
      },
    },
    defaultVariants: { status: 'pending' },
  }
);

const dots: Record<string, string> = {
  queued: '○',
  waiting: '⚠',
  running: '●',
  completed: '✓',
  success: '✓',
  failed: '✕',
  cancelled: '○',
  retrying: '↻',
  pending: '○',
  approved: '✓',
  rejected: '✕',
};

export interface StatusChipProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof statusChipVariants> {
  label?: string;
}

export function StatusChip({ status = 'pending', label, className, ...props }: StatusChipProps) {
  const key = status || 'pending';
  return (
    <span className={cn(statusChipVariants({ status }), className)} {...props}>
      <span aria-hidden>{dots[key] || '○'}</span>
      {label || key}
    </span>
  );
}
