import { Navigate } from 'react-router-dom';
import { routes } from '@/lib/routes';

/** Legacy hub — generation starts from News; visuals live on each draft. */
export function GenerationPage() {
  return <Navigate to={routes.news} replace />;
}
