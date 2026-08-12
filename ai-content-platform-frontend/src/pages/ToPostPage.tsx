import { useNavigate } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { Button } from '@/design-system/ui/button';
import { MonthlyCalendar } from '@/components/calendar/MonthlyCalendar';
import { routes } from '@/lib/routes';
import { cn } from '@/lib/utils';

/** Shared monthly calendar — used on To Post and embedded in Plan. */
export function ToPostCalendar({
  embedded = false,
  className,
  showTopicLabels: _showTopicLabels = false,
}: {
  embedded?: boolean;
  className?: string;
  /** Kept for backward compatibility; monthly view uses mix colors. */
  showTopicLabels?: boolean;
}) {
  const navigate = useNavigate();

  if (embedded) {
    return (
      <div className={cn('scroll-mt-24', className)} id="calendar">
        <MonthlyCalendar title="Publishing calendar" />
      </div>
    );
  }

  return (
    <div className={className}>
      <PageHeader
        title="To Post"
        description="Monthly calendar of scheduled LinkedIn posts and plan slots — like Google Calendar."
        actions={
          <Button variant="outline" size="sm" onClick={() => navigate(routes.plan)}>
            Plan
          </Button>
        }
      />
      <MonthlyCalendar title="Publishing calendar" />
    </div>
  );
}

export function ToPostPage() {
  return <ToPostCalendar />;
}

/** @deprecated Use CalendarEvent from MonthlyCalendar */
export interface ToPostItem {
  id: string;
  hook?: string | null;
  content_type?: string;
  status?: string;
  scheduled_for?: string | null;
}
