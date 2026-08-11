import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useApiQuery } from '@/hooks/useApiQuery';
import { Card, CardContent, CardHeader } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';
import { Badge } from '@/components/Badge';
import { Spinner } from '@/components/Spinner';
import { ErrorState } from '@/components/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { Button } from '@/design-system/ui/button';
import { apiClient } from '@/api/client';
import type { ApiEnvelope } from '@/api/types';
import { GraduationCap } from 'lucide-react';
import { toast } from 'sonner';

interface ExampleRow {
  id: string;
  text: string;
  hook?: string;
  content_type?: string;
  weight?: number;
  lifecycle?: string;
}

interface RuleRow {
  id: string;
  category: string;
  text: string;
  priority?: number;
  lifecycle?: string;
}

interface PreferenceRow {
  id: string;
  category: string;
  preference: string;
  confidence?: number;
  lifecycle?: string;
}

export function LearningPage() {
  const queryClient = useQueryClient();
  const examples = useApiQuery<ApiEnvelope<ExampleRow[]>>(
    ['learning', 'examples'],
    '/learning/examples'
  );
  const rules = useApiQuery<ApiEnvelope<RuleRow[]>>(
    ['learning', 'rules'],
    '/learning/rules'
  );
  const preferences = useApiQuery<ApiEnvelope<PreferenceRow[]>>(
    ['learning', 'preferences'],
    '/learning/preferences'
  );
  const [editingExample, setEditingExample] = useState<string | null>(null);
  const [editingRule, setEditingRule] = useState<string | null>(null);
  const [draftText, setDraftText] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  const isLoading = examples.isLoading || rules.isLoading || preferences.isLoading;
  const isError = examples.isError && rules.isError;

  if (isLoading) return <Spinner />;
  if (isError) {
    return (
      <ErrorState
        message="Unable to load learning data."
        onRetry={() => {
          examples.refetch();
          rules.refetch();
          preferences.refetch();
        }}
      />
    );
  }

  const examplesList = examples.data?.data ?? [];
  const rulesList = rules.data?.data ?? [];
  const prefsList = preferences.data?.data ?? [];

  const saveExample = async (id: string) => {
    setBusy(id);
    try {
      await apiClient.patch(`/learning/examples/${id}`, { text: draftText });
      toast.success('Example updated');
      setEditingExample(null);
      queryClient.invalidateQueries({ queryKey: ['learning', 'examples'] });
    } catch {
      toast.error('Update failed');
    } finally {
      setBusy(null);
    }
  };

  const saveRule = async (id: string) => {
    setBusy(id);
    try {
      await apiClient.patch(`/learning/rules/${id}`, { text: draftText });
      toast.success('Rule updated');
      setEditingRule(null);
      queryClient.invalidateQueries({ queryKey: ['learning', 'rules'] });
    } catch {
      toast.error('Update failed');
    } finally {
      setBusy(null);
    }
  };

  if (examplesList.length === 0 && rulesList.length === 0 && prefsList.length === 0) {
    return (
      <div>
        <PageHeader title="Learning Center" description="Examples and rules for AI improvement" />
        <EmptyState
          icon={<GraduationCap className="w-8 h-8 text-navy-400" />}
          title="No learning data yet"
          description="Approve drafts to build examples. Reject with reasons to create rules."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Learning Center"
        description="Edit examples and rules that improve AI output"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <h3 className="font-semibold">Examples ({examplesList.length})</h3>
          </CardHeader>
          <CardContent className="space-y-3">
            {examplesList.map((example) => (
              <div key={example.id} className="p-3 rounded-lg border border-[var(--color-border)]">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium text-sm">{example.hook || 'Approved post'}</p>
                  {example.lifecycle && <Badge>{example.lifecycle}</Badge>}
                </div>
                {editingExample === example.id ? (
                  <div className="mt-2 space-y-2">
                    <textarea
                      className="w-full min-h-[100px] rounded-md border border-[var(--color-border)] bg-transparent p-2 text-sm"
                      value={draftText}
                      onChange={(e) => setDraftText(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        disabled={busy === example.id}
                        onClick={() => saveExample(example.id)}
                      >
                        Save
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setEditingExample(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-[var(--color-text-secondary)] line-clamp-3 mt-1">
                      {example.text}
                    </p>
                    {example.content_type && <Badge className="mt-2">{example.content_type}</Badge>}
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2"
                      onClick={() => {
                        setEditingExample(example.id);
                        setEditingRule(null);
                        setDraftText(example.text);
                      }}
                    >
                      Edit
                    </Button>
                  </>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="font-semibold">Rules ({rulesList.length})</h3>
          </CardHeader>
          <CardContent className="space-y-3">
            {rulesList.map((rule) => (
              <div key={rule.id} className="p-3 rounded-lg border border-[var(--color-border)]">
                <div className="mb-2 flex flex-wrap gap-2">
                  <Badge>{rule.category}</Badge>
                  {rule.lifecycle && <Badge>{rule.lifecycle}</Badge>}
                </div>
                {editingRule === rule.id ? (
                  <div className="space-y-2">
                    <textarea
                      className="w-full min-h-[80px] rounded-md border border-[var(--color-border)] bg-transparent p-2 text-sm"
                      value={draftText}
                      onChange={(e) => setDraftText(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        disabled={busy === rule.id}
                        onClick={() => saveRule(rule.id)}
                      >
                        Save
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setEditingRule(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-[var(--color-text-secondary)]">{rule.text}</p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2"
                      onClick={() => {
                        setEditingRule(rule.id);
                        setEditingExample(null);
                        setDraftText(rule.text);
                      }}
                    >
                      Edit
                    </Button>
                  </>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="font-semibold">Preferences ({prefsList.length})</h3>
          </CardHeader>
          <CardContent className="space-y-3">
            {prefsList.map((pref) => (
              <div key={pref.id} className="p-3 rounded-lg border border-[var(--color-border)]">
                <Badge className="mb-2">{pref.category}</Badge>
                <p className="text-sm text-[var(--color-text-secondary)]">{pref.preference}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
