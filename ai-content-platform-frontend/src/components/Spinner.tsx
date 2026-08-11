import { Skeleton } from '@/design-system/ui/skeleton';

/** Prefer Skeleton; Spinner kept for legacy call sites. */
export function Spinner({ className }: { className?: string }) {
  return (
    <div className={className || 'space-y-3 py-8'} aria-label="Loading" role="status">
      <Skeleton className="h-6 w-40" />
      <Skeleton className="h-4 w-64 max-w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}
