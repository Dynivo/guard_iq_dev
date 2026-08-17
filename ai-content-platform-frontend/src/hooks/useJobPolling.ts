import { useApiQuery } from '@/hooks/useApiQuery';
import type { ApiEnvelope } from '@/api/types';

export interface JobStatus {
  id: string;
  type: string;
  status: string;
  progress: number;
  error_message?: string | null;
  attempts?: number;
  payload?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
}

const TERMINAL_STATUSES = new Set(['complete', 'completed', 'failed']);

function isTerminal(status: string | undefined): boolean {
  return !status || TERMINAL_STATUSES.has(status);
}

/**
 * Polls GET /jobs/{jobId} every 2.5s while the job is pending/running, same
 * cadence as the image-generation gallery's polling. Used by the
 * generic Job-table flows (draft generate/regenerate, Plan auto-generate) —
 * image generation keeps its own bespoke polling against /drafts/{id}/images.
 */
export function useJobPolling(jobId: string | null | undefined) {
  const { data, isFetching } = useApiQuery<ApiEnvelope<JobStatus>>(
    ['jobs', jobId || ''],
    `/jobs/${jobId}`,
    {
      enabled: Boolean(jobId),
      staleTime: 0,
      refetchInterval: (query) => (isTerminal(query.state.data?.data?.status) ? false : 2500),
    }
  );

  const job = data?.data;
  const isPolling = Boolean(jobId) && !isTerminal(job?.status);
  const isComplete = job?.status === 'complete' || job?.status === 'completed';
  const isFailed = job?.status === 'failed';

  return { job, isPolling, isComplete, isFailed, isFetching };
}
