import { useState } from 'react';
import { ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { AuthenticatedImage, downloadMedia } from '@/components/AuthenticatedImage';
import { Button } from '@/design-system/ui/button';
import { toast } from 'sonner';

export interface DraftImageItem {
  id: string;
  url: string;
  object_key?: string;
  width?: number | null;
  height?: number | null;
  source?: 'upload' | 'ai' | string;
}

interface DraftImageGalleryProps {
  images: DraftImageItem[];
  onIndexChange?: (index: number) => void;
}

export function DraftImageGallery({ images, onIndexChange }: DraftImageGalleryProps) {
  const [index, setIndex] = useState(0);
  const safeIndex = images.length ? Math.min(index, images.length - 1) : 0;
  const current = images[safeIndex];

  const go = (i: number) => {
    setIndex(i);
    onIndexChange?.(i);
  };

  if (!images.length || !current) return null;

  const prev = () => go((safeIndex - 1 + images.length) % images.length);
  const next = () => go((safeIndex + 1) % images.length);

  const onDownload = async () => {
    try {
      await downloadMedia(current.url, `linkedin-image-${safeIndex + 1}.png`);
      toast.success('Download started');
    } catch {
      toast.error('Download failed');
    }
  };

  return (
    <div className="space-y-3">
      <div className="relative overflow-hidden rounded-lg border border-border bg-muted/40">
        {/* LinkedIn single-image frame: 1:1 — contain so we never crop the creative */}
        <div className="relative mx-auto aspect-square w-full max-w-full bg-[#f3f2ef]">
          <AuthenticatedImage
            src={current.url}
            alt={`Generated image ${safeIndex + 1}`}
            className="absolute inset-0 h-full w-full object-contain"
          />
        </div>
        {images.length > 1 && (
          <>
            <button
              type="button"
              onClick={prev}
              className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-background/90 p-1.5 shadow"
              aria-label="Previous image"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={next}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-background/90 p-1.5 shadow"
              aria-label="Next image"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            <div className="absolute bottom-2 left-1/2 flex -translate-x-1/2 gap-1.5">
              {images.map((img, i) => (
                <button
                  key={img.id}
                  type="button"
                  onClick={() => go(i)}
                  className={`h-2 w-2 rounded-full ${
                    i === safeIndex ? 'bg-accent' : 'bg-background/70'
                  }`}
                  aria-label={`Go to image ${i + 1}`}
                />
              ))}
            </div>
          </>
        )}
      </div>

      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {images.length > 1 ? `${safeIndex + 1} of ${images.length}` : '1 image'}
          {' · '}
          {current.source === 'upload' ? 'Uploaded photo' : 'LinkedIn 1:1'}
          {current.width && current.height
            ? ` · ${current.width}×${current.height}`
            : current.source === 'upload'
              ? ''
              : ' · 1080×1080 target'}
        </p>
        <Button size="sm" variant="outline" onClick={onDownload}>
          <Download className="h-3.5 w-3.5" />
          Download
        </Button>
      </div>

      {images.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {images.map((img, i) => (
            <button
              key={img.id}
              type="button"
              onClick={() => go(i)}
              className={`h-14 w-14 shrink-0 overflow-hidden rounded-md border-2 ${
                i === safeIndex ? 'border-accent' : 'border-transparent opacity-70'
              }`}
            >
              <AuthenticatedImage
                src={img.url}
                alt={`Thumb ${i + 1}`}
                className="h-full w-full object-cover"
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
