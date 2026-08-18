import { useEffect, useState } from 'react';
import { DollarSign } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/api/client';
import type { ApiEnvelope } from '@/api/types';
import { useApiQuery } from '@/hooks/useApiQuery';
import { Button } from '@/design-system/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/design-system/ui/card';
import { Input } from '@/design-system/ui/input';
import { Skeleton } from '@/design-system/ui/skeleton';

interface ProviderBudget {
  provider: string;
  display_name: string;
  monthly_limit_usd: number;
  spent_usd: number;
  reserved_usd: number;
  remaining_usd: number | null;
  is_enabled: boolean;
  is_blocked: boolean;
  month_start: string;
}

export function ProviderBudgetsCard() {
  const { data, isLoading, refetch } = useApiQuery<ApiEnvelope<ProviderBudget[]>>(
    ['provider-budgets'],
    '/analytics/provider-budgets',
    { staleTime: 0 }
  );
  const rows = data?.data || [];
  const [limits, setLimits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    setLimits(Object.fromEntries(rows.map((row) => [row.provider, row.monthly_limit_usd.toFixed(2)])));
  }, [data]);

  const save = async (row: ProviderBudget) => {
    const rowKey = row.provider;
    const limit = Number(limits[rowKey]);
    if (!Number.isFinite(limit) || limit < 0 || limit > 10_000) {
      toast.error('Enter a monthly limit between $0 and $10,000');
      return;
    }
    setSaving(rowKey);
    try {
      await apiClient.put('/analytics/provider-budgets', {
        provider: row.provider,
        monthly_limit_usd: limit,
        is_enabled: true,
      });
      toast.success(`Monthly limit saved for ${row.display_name}`);
      await refetch();
    } catch (error: unknown) {
      const message = (error as { response?: { data?: { error?: string } } })?.response?.data?.error;
      toast.error(message || 'Could not save provider budget');
    } finally {
      setSaving(null);
    }
  };

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <DollarSign className="h-4 w-4 text-accent" />
          Monthly AI provider budgets
        </CardTitle>
        <CardDescription>
          One shared limit covers all models from each provider and resets at the start of each UTC month. Provider billing remains the authoritative total.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Providers appear here after their API keys are configured.</p>
        ) : (
          <div className="space-y-3">
            {rows.map((row) => {
              const rowKey = row.provider;
              return (
                <div key={rowKey} className="grid gap-3 rounded-lg border border-border p-3 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-end">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{row.display_name}</p>
                    <p className="text-xs text-muted-foreground">
                      ${row.spent_usd.toFixed(2)} spent
                      {row.reserved_usd > 0 ? ` · $${row.reserved_usd.toFixed(2)} in progress` : ''}
                    </p>
                  </div>
                  <div className="w-full sm:w-32">
                    <Input
                      id={`budget-${rowKey}`}
                      type="number"
                      min="0"
                      max="10000"
                      step="1"
                      label="USD / month"
                      value={limits[rowKey] ?? ''}
                      onChange={(event) => setLimits((current) => ({ ...current, [rowKey]: event.target.value }))}
                    />
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => save(row)}
                    loading={saving === rowKey}
                    disabled={saving !== null}
                  >
                    Save
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
