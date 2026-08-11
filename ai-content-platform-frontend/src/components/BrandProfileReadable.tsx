import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';

interface BrandProfileReadableProps {
  markdown: string;
  className?: string;
  emptyMessage?: string;
}

/** Client-friendly rendering of brand profile Markdown (not raw code). */
export function BrandProfileReadable({
  markdown,
  className,
  emptyMessage = 'No brand profile yet. Generate one with Claude or ChatGPT, then paste it here.',
}: BrandProfileReadableProps) {
  const text = markdown.trim();
  if (!text) {
    return (
      <div
        className={cn(
          'rounded-lg border border-dashed border-border bg-muted/30 px-4 py-10 text-center text-sm text-muted-foreground',
          className
        )}
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div
      className={cn(
        'max-h-[32rem] overflow-auto rounded-lg border border-border bg-card px-5 py-5 sm:px-6 sm:py-6',
        className
      )}
    >
      <article className="max-w-3xl text-[15px] leading-relaxed text-foreground">
        <ReactMarkdown
          components={{
            h1: ({ children }) => (
              <h1 className="mb-3 text-xl font-semibold tracking-tight text-foreground">{children}</h1>
            ),
            h2: ({ children }) => (
              <h2 className="mb-2 mt-7 border-b border-border pb-2 text-base font-semibold tracking-tight text-foreground first:mt-0">
                {children}
              </h2>
            ),
            h3: ({ children }) => (
              <h3 className="mb-1.5 mt-5 text-sm font-semibold text-foreground">{children}</h3>
            ),
            p: ({ children }) => (
              <p className="my-2.5 text-sm leading-relaxed text-muted-foreground">{children}</p>
            ),
            ul: ({ children }) => (
              <ul className="my-3 list-disc space-y-1.5 pl-5 text-sm text-muted-foreground">
                {children}
              </ul>
            ),
            ol: ({ children }) => (
              <ol className="my-3 list-decimal space-y-1.5 pl-5 text-sm text-muted-foreground">
                {children}
              </ol>
            ),
            li: ({ children }) => <li className="leading-relaxed">{children}</li>,
            strong: ({ children }) => (
              <strong className="font-semibold text-foreground">{children}</strong>
            ),
            em: ({ children }) => <em className="italic">{children}</em>,
            a: ({ href, children }) => (
              <a
                href={href}
                className="font-medium text-accent underline-offset-2 hover:underline"
                target="_blank"
                rel="noreferrer"
              >
                {children}
              </a>
            ),
            hr: () => <hr className="my-6 border-border" />,
            blockquote: ({ children }) => (
              <blockquote className="my-3 border-l-2 border-accent/40 pl-3 text-sm text-muted-foreground">
                {children}
              </blockquote>
            ),
            code: ({ children }) => (
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground">
                {children}
              </code>
            ),
            table: ({ children }) => (
              <div className="my-4 overflow-x-auto">
                <table className="w-full border-collapse text-left text-sm">{children}</table>
              </div>
            ),
            th: ({ children }) => (
              <th className="border-b border-border px-2 py-2 font-semibold text-foreground">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="border-b border-border/70 px-2 py-2 text-muted-foreground">{children}</td>
            ),
          }}
        >
          {text}
        </ReactMarkdown>
      </article>
    </div>
  );
}
