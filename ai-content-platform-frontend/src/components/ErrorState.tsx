import { AlertCircle } from 'lucide-react';
import { Button } from '@/design-system/ui/button';
import { cn } from '@/lib/utils';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = 'Something went wrong',
  message = 'We could not load this view. Try again.',
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-[var(--radius)] border border-destructive/20 bg-destructive/5 px-6 py-12 text-center',
        className
      )}
      role="alert"
    >
      <AlertCircle className="mb-3 h-8 w-8 text-destructive" />
      <h3 className="font-semibold">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <Button variant="outline" className="mt-4" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
