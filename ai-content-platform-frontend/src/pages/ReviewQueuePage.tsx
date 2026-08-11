import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Spinner } from '@/components/Spinner';
import { routes } from '@/lib/routes';

/**
 * Review is no longer a separate product surface.
 * Approve/reject lives on each draft page; this route redirects to the drafts queue.
 */
export function ReviewQueuePage() {
  const navigate = useNavigate();

  useEffect(() => {
    navigate(`${routes.drafts}?status=pending_review`, { replace: true });
  }, [navigate]);

  return <Spinner />;
}
