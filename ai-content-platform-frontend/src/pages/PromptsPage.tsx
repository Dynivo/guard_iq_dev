import { useState } from 'react';
import { ChevronDown, ChevronRight, MessageSquare } from 'lucide-react';
import { useApiQuery } from '@/hooks/useApiQuery';
import type { ApiEnvelope } from '@/api/types';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { Badge } from '@/design-system/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/design-system/ui/card';
import { Skeleton } from '@/design-system/ui/skeleton';

interface PromptSection {
  name: string;
  body: string;
  order?: number;
}

interface PromptCatalogItem {
  id: string;
  name: string;
  version: string;
  capability?: string;
  status?: string;
  approval_status?: string;
  section_count?: number;
  variable_count?: number;
  tags?: string[];
  owner?: string;
  preview?: string;
  body?: string;
  description?: string;
  sections?: PromptSection[];
}

export function PromptsPage() {
  const { data, isLoading, isError, refetch } = useApiQuery<
    ApiEnvelope<{ items?: PromptCatalogItem[]; count?: number }>
  >(['prompts-catalog'], '/prompts', { staleTime: 0 });
  const [openId, setOpenId] = useState<string | null>(null);

  const items = data?.data?.items ?? [];

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (isError) {
    return <ErrorState message="Could not load prompt catalog" onRetry={() => refetch()} />;
  }

  return (
    <div>
      <PageHeader
        title="Prompt versions"
        description="Live catalog from configs/prompts. Click a prompt to read the full text."
      />

      {!items.length ? (
        <EmptyState
          icon={<MessageSquare className="h-8 w-8" />}
          title="No prompts found"
          description="Add YAML files under configs/prompts on the backend."
        />
      ) : (
        <div className="space-y-3">
          {items.map((p) => {
            const open = openId === p.id;
            const body =
              p.body ||
              p.sections?.map((s) => `## ${s.name}\n${s.body}`).join('\n\n') ||
              p.preview ||
              '';
            return (
              <Card key={p.id}>
                <button
                  type="button"
                  className="w-full text-left"
                  onClick={() => setOpenId(open ? null : p.id)}
                >
                  <CardHeader className="space-y-2">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <CardTitle className="text-base">{p.name}</CardTitle>
                          <Badge variant="secondary">v{p.version}</Badge>
                          {p.status && <Badge variant="outline">{p.status}</Badge>}
                        </div>
                        <CardDescription>
                          {p.capability || 'general'} · {p.section_count ?? 0} sections ·{' '}
                          {p.variable_count ?? 0} variables
                          {p.owner ? ` · ${p.owner}` : ''}
                        </CardDescription>
                      </div>
                      {open ? (
                        <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
                      )}
                    </div>
                  </CardHeader>
                </button>
                <CardContent className="space-y-3">
                  {!open && (
                    <p className="line-clamp-3 whitespace-pre-wrap text-sm text-muted-foreground">
                      {body || p.description || 'No prompt body found in YAML'}
                    </p>
                  )}
                  {open && (
                    <div className="space-y-4">
                      {p.description && (
                        <p className="text-sm text-muted-foreground">{p.description}</p>
                      )}
                      {p.sections?.length ? (
                        p.sections.map((s) => (
                          <div key={s.name} className="rounded-lg border border-border bg-muted/20 p-3">
                            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                              {s.name}
                            </p>
                            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
                              {s.body}
                            </pre>
                          </div>
                        ))
                      ) : (
                        <pre className="whitespace-pre-wrap rounded-lg border border-border bg-muted/20 p-3 font-sans text-sm leading-relaxed">
                          {body || 'Empty prompt'}
                        </pre>
                      )}
                    </div>
                  )}
                  {!!p.tags?.length && (
                    <div className="flex flex-wrap gap-1">
                      {p.tags.map((t) => (
                        <Badge key={t} variant="outline">
                          {t}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
