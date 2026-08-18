import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Building2,
  Cpu,
  FileDown,
  KeyRound,
  Loader2,
  Mic,
  Moon,
  Palette,
  Rss,
  Sun,
  UserRound,
  Monitor,
} from 'lucide-react';
import { toast } from 'sonner';
import { useApiQuery } from '@/hooks/useApiQuery';
import { apiClient } from '@/api/client';
import type { ApiEnvelope } from '@/api/types';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/design-system/ui/card';
import { Skeleton } from '@/design-system/ui/skeleton';
import { Badge } from '@/design-system/ui/badge';
import { Button } from '@/design-system/ui/button';
import { Input } from '@/design-system/ui/input';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';
import { startOnboardingTour } from '@/lib/onboarding';
import { routes } from '@/lib/routes';
import { cn } from '@/lib/utils';
import { ProviderBudgetsCard } from '@/components/ProviderBudgetsCard';

interface OrgCurrent {
  id?: string;
  name?: string;
  slug?: string;
  is_active?: boolean;
}

const SHORTCUTS = [
  {
    title: 'Brand voice',
    description: 'Profile, colors, and LinkedIn house style',
    to: routes.brand,
    icon: Palette,
  },
  {
    title: 'News sources',
    description: 'RSS / NewsData feeds and fetch schedule',
    to: routes.sources,
    icon: Rss,
  },
  {
    title: 'AI providers',
    description: 'Which models are configured and in use',
    to: routes.providers,
    icon: Cpu,
  },
];

export function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();
  const { data, isLoading } = useApiQuery<ApiEnvelope<OrgCurrent>>(
    ['org-current'],
    '/organizations/current'
  );
  const org = data?.data;
  const [exporting, setExporting] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

  const changePassword = async () => {
    if (newPassword.length < 12) {
      toast.error('New password must be at least 12 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match');
      return;
    }
    setChangingPassword(true);
    try {
      await apiClient.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success('Password changed. Sign in again with the new password.');
      logout();
      window.location.href = routes.login;
    } catch (error: unknown) {
      const message = (error as { response?: { data?: { error?: string } } })?.response?.data?.error;
      toast.error(message || 'Could not change password');
    } finally {
      setChangingPassword(false);
    }
  };

  const exportDiagnostics = async () => {
    setExporting(true);
    try {
      const res = await apiClient.get('/diagnostics/export', {
        responseType: 'blob',
        timeout: 30_000,
      });
      const disposition = res.headers['content-disposition'] as string | undefined;
      const filename = disposition?.match(/filename="?([^"]+)"?/)?.[1] || 'diagnostics.zip';
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success('Diagnostics exported — send the file to your agency');
    } catch {
      toast.error('Could not export diagnostics');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Workspace preferences, your account, and quick links to brand, sources, and AI setup."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <ProviderBudgetsCard />
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <UserRound className="h-4 w-4 text-accent" />
              Your account
            </CardTitle>
            <CardDescription>Signed-in profile for this workspace.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Name</span>
              <span className="font-medium">{user?.name || '—'}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Email</span>
              <span className="font-medium break-all text-right">{user?.email || '—'}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Role</span>
              <Badge variant="secondary" className="capitalize">
                {user?.role || 'editor'}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <KeyRound className="h-4 w-4 text-accent" />
              Change password
            </CardTitle>
            <CardDescription>
              Replace the temporary handover password after first sign-in.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              placeholder="Current password"
              autoComplete="current-password"
            />
            <Input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              placeholder="New password (12+ characters)"
              autoComplete="new-password"
              maxLength={72}
            />
            <Input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Confirm new password"
              autoComplete="new-password"
              maxLength={72}
            />
            <Button
              size="sm"
              disabled={
                changingPassword || !currentPassword || !newPassword || !confirmPassword
              }
              onClick={changePassword}
            >
              {changingPassword && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Change password
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Building2 className="h-4 w-4 text-accent" />
              Organization
            </CardTitle>
            <CardDescription>Workspace this membership belongs to.</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">Name</span>
                  <span className="font-medium">{org?.name || '—'}</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">Slug</span>
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{org?.slug || '—'}</code>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">Status</span>
                  <Badge variant={org?.is_active === false ? 'outline' : 'secondary'}>
                    {org?.is_active === false ? 'Inactive' : 'Active'}
                  </Badge>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              {theme === 'dark' ? (
                <Moon className="h-4 w-4 text-accent" />
              ) : theme === 'light' ? (
                <Sun className="h-4 w-4 text-accent" />
              ) : (
                <Monitor className="h-4 w-4 text-accent" />
              )}
              Appearance
            </CardTitle>
            <CardDescription>Theme for this browser. Does not change other devices.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {(
                [
                  { id: 'light' as const, label: 'Light', icon: Sun },
                  { id: 'dark' as const, label: 'Dark', icon: Moon },
                  { id: 'system' as const, label: 'System', icon: Monitor },
                ] as const
              ).map((t) => (
                <Button
                  key={t.id}
                  variant={theme === t.id ? 'default' : 'outline'}
                  size="sm"
                  className="gap-1.5"
                  onClick={() => setTheme(t.id)}
                >
                  <t.icon className="h-3.5 w-3.5" />
                  {t.label}
                </Button>
              ))}
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                localStorage.removeItem('onboarding-done');
                startOnboardingTour();
              }}
            >
              Replay onboarding tour
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Mic className="h-4 w-4 text-accent" />
              Capture & speech
            </CardTitle>
            <CardDescription>
              Voice notes and “Hear draft” use Azure Speech on the server when keys are set.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              Success stories and personal achievements live under{' '}
              <Link to={routes.capture} className="text-accent underline">
                Capture
              </Link>
              . Educational posts usually come from News.
            </p>
            <Button asChild variant="outline" size="sm">
              <Link to={routes.capture}>Open Capture</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileDown className="h-4 w-4 text-accent" />
              Diagnostics
            </CardTitle>
            <CardDescription>
              If something looks wrong, export a bundle to send to your agency.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              Includes recent job history and server logs — never passwords or API keys.
            </p>
            <Button variant="outline" size="sm" disabled={exporting} onClick={exportDiagnostics}>
              {exporting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <FileDown className="h-3.5 w-3.5" />
              )}
              Export diagnostics
            </Button>
            <p className="text-xs">
              If the app won't even start, these logs are also saved on the server in the{' '}
              <code className="rounded bg-muted px-1 py-0.5">logs/</code> folder — zip that
              and send it instead.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Workspace setup</CardTitle>
          <CardDescription>Jump to the places clients change most often.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2">
            {SHORTCUTS.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  'flex gap-3 rounded-xl border border-border p-4 transition',
                  'hover:border-accent/40 hover:bg-accent/5'
                )}
              >
                <item.icon className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
                <span>
                  <span className="block font-medium text-foreground">{item.title}</span>
                  <span className="mt-0.5 block text-sm text-muted-foreground">{item.description}</span>
                </span>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
