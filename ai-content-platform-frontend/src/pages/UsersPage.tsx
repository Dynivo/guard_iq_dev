import { useMemo } from 'react';
import type { ColumnDef } from '@tanstack/react-table';
import { useApiQuery } from '@/hooks/useApiQuery';
import type { ApiEnvelope } from '@/api/types';
import { PageHeader } from '@/components/PageHeader';
import { DataTable } from '@/components/DataTable';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { Skeleton } from '@/design-system/ui/skeleton';
import { Users } from 'lucide-react';

interface Member {
  id?: string;
  user_id?: string;
  email?: string;
  display_name?: string;
  role?: string;
}

export function UsersPage() {
  const { data, isLoading, isError, refetch } = useApiQuery<
    ApiEnvelope<Member[] | { items?: Member[]; members?: Member[] }>
  >(['org-members'], '/organizations/current/members');

  const members = useMemo(() => {
    const p = data?.data;
    if (Array.isArray(p)) return p;
    return p?.items ?? p?.members ?? [];
  }, [data]);

  const columns = useMemo<ColumnDef<Member>[]>(
    () => [
      {
        id: 'name',
        header: 'Name',
        accessorFn: (r) => r.display_name || r.email || r.user_id || r.id,
      },
      { accessorKey: 'email', header: 'Email' },
      { accessorKey: 'role', header: 'Role' },
    ],
    []
  );

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError) return <ErrorState onRetry={refetch} />;

  return (
    <div>
      <PageHeader title="Users" description="Organization members from /organizations/current/members." />
      {members.length === 0 ? (
        <EmptyState
          icon={<Users className="h-8 w-8" />}
          title="No members returned"
          description="Membership data will appear when the organization endpoint returns users."
        />
      ) : (
        <DataTable columns={columns} data={members} searchPlaceholder="Filter members…" />
      )}
    </div>
  );
}
