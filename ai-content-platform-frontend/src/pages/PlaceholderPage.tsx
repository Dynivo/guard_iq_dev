import { EmptyState } from '@/components/EmptyState';
import { PageHeader } from '@/components/PageHeader';
import { Construction } from 'lucide-react';

interface PlaceholderPageProps {
  title: string;
  description?: string;
}

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div>
      <PageHeader title={title} description={description} />
      <EmptyState
        icon={<Construction className="w-8 h-8 text-navy-400" />}
        title="Coming Soon"
        description={`The ${title} feature is under development and will be available soon.`}
      />
    </div>
  );
}
