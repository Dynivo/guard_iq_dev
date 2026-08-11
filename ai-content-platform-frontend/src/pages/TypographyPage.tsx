import { useNavigate } from 'react-router-dom';
import { Type } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/EmptyState';
import { WorkflowStageRail } from '@/components/ai/WorkflowStageRail';
import { Button } from '@/design-system/ui/button';
import { routes } from '@/lib/routes';

export function TypographyPage() {
  const navigate = useNavigate();
  return (
    <div>
      <PageHeader
        title="Typography"
        description="Optional. Open any draft → Show optional extras → Typography."
        actions={<Button onClick={() => navigate(routes.drafts)}>Go to Drafts</Button>}
      />
      <div className="mb-4">
        <WorkflowStageRail current="Visuals" />
      </div>
      <EmptyState
        icon={<Type className="h-8 w-8" />}
        title="Typography lives on the draft page"
        description="Pick a draft, expand optional extras, and generate typography there."
        actionLabel="Open Drafts"
        onAction={() => navigate(routes.drafts)}
      />
    </div>
  );
}
