import { useEffect, useState } from 'react';
import { apiClient } from '@/api/client';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/design-system/ui/skeleton';

/** Turn delivery URL into a path relative to apiClient baseURL (`/api/v1`). */
export function toMediaApiPath(url: string): string {
  if (url.startsWith('/api/v1/')) return url.slice('/api/v1'.length);
  const marker = '/api/v1/';
  const idx = url.indexOf(marker);
  if (idx >= 0) return url.slice(idx + marker.length - 1); // keep leading /
  if (url.startsWith('/media/')) return url;
  return url;
}

/** Fetch authenticated media bytes and return a blob object URL. */
export async function fetchMediaBlobUrl(url: string): Promise<string> {
  const path = toMediaApiPath(url);
  const response = await apiClient.get(path, { responseType: 'blob' });
  return URL.createObjectURL(response.data as Blob);
}

interface AuthenticatedImageProps {
  src: string;
  alt?: string;
  className?: string;
}

export function AuthenticatedImage({ src, alt = '', className }: AuthenticatedImageProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let revoked: string | null = null;
    let cancelled = false;
    setFailed(false);
    setBlobUrl(null);

    fetchMediaBlobUrl(src)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        revoked = url;
        setBlobUrl(url);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [src]);

  if (failed) {
    return (
      <div
        className={cn(
          'flex items-center justify-center bg-muted text-xs text-muted-foreground',
          className
        )}
      >
        Image unavailable
      </div>
    );
  }

  if (!blobUrl) {
    return <Skeleton className={cn('w-full', className)} />;
  }

  return <img src={blobUrl} alt={alt} className={className} />;
}

export async function downloadMedia(url: string, filename: string) {
  const blobUrl = await fetchMediaBlobUrl(url);
  try {
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(blobUrl);
  }
}
