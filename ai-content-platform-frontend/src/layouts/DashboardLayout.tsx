import * as React from 'react';
import { Outlet, NavLink, Link, useNavigate, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import {
  LayoutDashboard,
  Newspaper,
  FileText,
  GraduationCap,
  MessageSquare,
  Palette,
  Rss,
  Cpu,
  ListTodo,
  BarChart3,
  Settings,
  LogOut,
  Menu,
  X,
  ChevronLeft,
  ChevronRight,
  Mic,
  Moon,
  Sun,
  PanelLeft,
  CalendarRange,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { cn } from '@/lib/utils';
import { routes } from '@/lib/routes';
import { Button } from '@/design-system/ui/button';
import { ScrollArea } from '@/design-system/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/design-system/ui/tooltip';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { startOnboardingTour } from '@/lib/onboarding';

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  section: string;
  tourId?: string;
}

/** Primary nav only — advanced tools live under "More". */
const navItems: NavItem[] = [
  { label: 'Dashboard', path: routes.app, icon: <LayoutDashboard size={18} />, section: 'main', tourId: 'nav-dashboard' },
  { label: 'News', path: routes.news, icon: <Newspaper size={18} />, section: 'workflow', tourId: 'nav-news' },
  { label: 'Capture', path: routes.capture, icon: <Mic size={18} />, section: 'workflow', tourId: 'nav-capture' },
  { label: 'Plan', path: routes.plan, icon: <CalendarRange size={18} />, section: 'workflow', tourId: 'nav-plan' },
  { label: 'Drafts', path: routes.drafts, icon: <FileText size={18} />, section: 'workflow', tourId: 'nav-generation' },
  { label: 'Sources', path: routes.sources, icon: <Rss size={18} />, section: 'setup' },
  { label: 'Brand', path: routes.brand, icon: <Palette size={18} />, section: 'setup' },
  { label: 'Learning', path: routes.learning, icon: <GraduationCap size={18} />, section: 'more' },
  { label: 'Prompts', path: routes.prompts, icon: <MessageSquare size={18} />, section: 'more' },
  { label: 'Jobs', path: routes.jobs, icon: <ListTodo size={18} />, section: 'more' },
  { label: 'Analytics', path: routes.analytics, icon: <BarChart3 size={18} />, section: 'more', tourId: 'nav-analytics' },
  { label: 'Providers', path: routes.providers, icon: <Cpu size={18} />, section: 'more' },
  { label: 'Settings', path: routes.settings, icon: <Settings size={18} />, section: 'more' },
];

const sections = [
  { key: 'main', label: '' },
  { key: 'workflow', label: 'Create' },
  { key: 'setup', label: 'Setup' },
  { key: 'more', label: 'More' },
];

const crumbs: Record<string, string> = {
  [routes.app]: 'Dashboard',
  [routes.news]: 'News',
  [routes.capture]: 'Capture',
  [routes.plan]: 'Plan',
  [routes.toPost]: 'To Post',
  [routes.drafts]: 'Drafts',
  [routes.generation]: 'Generate',
  [routes.images]: 'Images',
  [routes.typography]: 'Typography',
  [routes.carousels]: 'Carousel',
  [routes.review]: 'Needs review',
  [routes.learning]: 'Learning',
  [routes.prompts]: 'Prompts',
  [routes.brand]: 'Brand',
  [routes.brandOnboarding]: 'Brand onboarding',
  [routes.brandDashboard]: 'Brand Intelligence',
  [routes.sources]: 'Sources',
  [routes.providers]: 'Providers',
  [routes.jobs]: 'Jobs',
  [routes.analytics]: 'Analytics',
  [routes.settings]: 'Settings',
  [routes.ideas]: 'Ideas',
};

export function AppShell() {
  const { user, logout } = useAuth();
  const { resolved, setTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [collapsed, setCollapsed] = React.useState(() => localStorage.getItem('sidebar-collapsed') === '1');
  const [sidebarWidth, setSidebarWidth] = React.useState(() => {
    const w = Number(localStorage.getItem('sidebar-width') || 260);
    return Number.isFinite(w) ? Math.min(360, Math.max(200, w)) : 260;
  });

  useKeyboardShortcuts();

  React.useEffect(() => {
    localStorage.setItem('sidebar-collapsed', collapsed ? '1' : '0');
  }, [collapsed]);

  React.useEffect(() => {
    if (!localStorage.getItem('onboarding-done')) {
      const t = window.setTimeout(() => startOnboardingTour(), 600);
      return () => window.clearTimeout(t);
    }
  }, []);

  const onResizeStart = (e: React.MouseEvent) => {
    if (collapsed) return;
    e.preventDefault();
    const startX = e.clientX;
    const startW = sidebarWidth;
    const onMove = (ev: MouseEvent) => {
      const next = Math.min(360, Math.max(200, startW + (ev.clientX - startX)));
      setSidebarWidth(next);
      localStorage.setItem('sidebar-width', String(next));
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const width = collapsed ? 72 : sidebarWidth;

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-screen overflow-hidden bg-background">
        {mobileOpen && (
          <div className="fixed inset-0 z-[var(--z-overlay)] bg-black/50 lg:hidden" onClick={() => setMobileOpen(false)} />
        )}

        <aside
          id="app-sidebar"
          style={{ width }}
          className={cn(
            'fixed inset-y-0 left-0 z-[var(--z-sidebar)] flex flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground shadow-[inset_-1px_0_0_var(--sidebar-border)] transition-[width,transform] duration-[var(--duration-normal)] lg:relative lg:translate-x-0',
            mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
          )}
        >
          <div className="flex h-14 items-center justify-between gap-2 border-b border-sidebar-border px-3">
            {!collapsed && (
              <Link to={routes.home} className="min-w-0 px-1 hover:opacity-90">
                <p className="truncate text-sm font-semibold text-sidebar-accent-foreground">
                  Content Intelligence
                </p>
                <p className="truncate text-[11px] text-sidebar-muted">Enterprise AI Platform</p>
              </Link>
            )}
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                onClick={() => setCollapsed((c) => !c)}
                aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden text-sidebar-foreground hover:bg-sidebar-accent"
                onClick={() => setMobileOpen(false)}
              >
                <X size={16} />
              </Button>
            </div>
          </div>

          <ScrollArea className="flex-1 px-2 py-3">
            {sections.map((section) => {
              const items = navItems.filter((i) => i.section === section.key);
              if (!items.length) return null;
              return (
                <div key={section.key} className={cn(section.label && 'mt-4')}>
                  {section.label && !collapsed && (
                    <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-sidebar-muted">
                      {section.label}
                    </p>
                  )}
                  <div className="space-y-0.5">
                    {items.map((item) => {
                      const link = (
                        <NavLink
                          key={item.path}
                          to={item.path}
                          end={item.path === routes.app}
                          data-tour={item.tourId}
                          onClick={() => setMobileOpen(false)}
                          className={({ isActive }) =>
                            cn(
                              'flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors duration-[var(--duration-fast)]',
                              isActive
                                ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                                : 'text-sidebar-muted hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground',
                              collapsed && 'justify-center px-0'
                            )
                          }
                        >
                          {item.icon}
                          {!collapsed && <span className="truncate">{item.label}</span>}
                        </NavLink>
                      );
                      return collapsed ? (
                        <Tooltip key={item.path}>
                          <TooltipTrigger asChild>{link}</TooltipTrigger>
                          <TooltipContent side="right">{item.label}</TooltipContent>
                        </Tooltip>
                      ) : (
                        <React.Fragment key={item.path}>{link}</React.Fragment>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </ScrollArea>

          <div className="border-t border-sidebar-border p-2">
            <button
              className={cn(
                'flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-sm text-sidebar-muted hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                collapsed && 'justify-center'
              )}
              onClick={() => {
                logout();
                navigate(routes.login);
              }}
            >
              <LogOut size={16} />
              {!collapsed && <span>Sign out</span>}
            </button>
            {!collapsed && (
              <p className="mt-1 truncate px-2.5 text-[11px] text-sidebar-muted">{user?.email}</p>
            )}
          </div>

          {!collapsed && (
            <div
              className="absolute inset-y-0 right-0 w-1 cursor-col-resize hover:bg-accent/40"
              onMouseDown={onResizeStart}
              aria-hidden
            />
          )}
        </aside>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-4">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
            >
              <Menu size={18} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="hidden lg:inline-flex"
              onClick={() => setCollapsed((c) => !c)}
              aria-label="Toggle sidebar"
            >
              <PanelLeft size={18} />
            </Button>

            <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-sm">
              <span className="text-muted-foreground">Workspace</span>
              <span className="text-muted-foreground">/</span>
              {location.pathname.startsWith(`${routes.drafts}/`) ? (
                <Link to={routes.drafts} className="truncate font-medium hover:text-accent hover:underline">
                  Drafts
                </Link>
              ) : (
                <span className="truncate font-medium">{crumbs[location.pathname] || 'Page'}</span>
              )}
            </nav>

            <div className="ml-auto flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                aria-label="Toggle theme"
                onClick={() => setTheme(resolved === 'dark' ? 'light' : 'dark')}
              >
                {resolved === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              </Button>
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/15 text-xs font-semibold text-accent">
                {user?.name?.charAt(0)?.toUpperCase() || 'U'}
              </div>
            </div>
          </header>

          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[1400px] p-4 lg:p-6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={location.pathname}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.18 }}
                >
                  <Outlet />
                </motion.div>
              </AnimatePresence>
            </div>
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}

/** @deprecated Use AppShell */
export const DashboardLayout = AppShell;
