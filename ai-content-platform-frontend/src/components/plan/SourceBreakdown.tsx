import { cn } from '@/lib/utils';
import type { PublisherCount, SimilarPost } from './types';

export function SourceBreakdown({
  publishers,
  className,
}: {
  publishers: PublisherCount[];
  className?: string;
}) {
  if (!publishers.length) return null;
  return (
    <div className={cn('space-y-1.5', className)}>
      <p className="text-xs font-medium">Built from</p>
      <ul className="space-y-1 text-xs text-muted-foreground">
        {publishers.map((p) => (
          <li key={p.name} className="flex justify-between gap-4">
            <span>{p.name}</span>
            <span className="tabular-nums">{p.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SimilarPosts({
  posts,
  note,
  className,
}: {
  posts: SimilarPost[];
  note?: string | null;
  className?: string;
}) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <p className="text-xs font-medium">Similar previous posts</p>
      {posts.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          {note || 'No historical posts yet — estimates only'}
        </p>
      ) : (
        <ul className="space-y-1 text-xs text-muted-foreground">
          {posts.map((p) => (
            <li key={p.id} className="flex justify-between gap-3">
              <span className="line-clamp-1">{p.title}</span>
              <span className="shrink-0">
                {p.impressions != null ? `${p.impressions} impressions` : 'No metrics yet'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
