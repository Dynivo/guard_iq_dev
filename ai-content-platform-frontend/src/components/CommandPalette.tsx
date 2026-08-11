import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Command } from 'cmdk';
import {
  LayoutDashboard,
  Newspaper,
  FileText,
  CheckCircle,
  BarChart3,
  ListTodo,
  GraduationCap,
  Palette,
  Settings,
  Search,
  Rss,
  Mic,
  CalendarRange,
  Sparkles,
  Brain,
} from 'lucide-react';
import { Dialog, DialogContent } from '@/design-system/ui/dialog';
import { routes } from '@/lib/routes';

const pages = [
  { label: 'Dashboard', path: routes.app, icon: LayoutDashboard, keywords: 'home gd' },
  { label: 'News', path: routes.news, icon: Newspaper, keywords: 'articles gn' },
  { label: 'Capture', path: routes.capture, icon: Mic, keywords: 'voice success story personal' },
  {
    label: 'Publishing Plan',
    path: routes.plan,
    icon: CalendarRange,
    keywords: 'plan calendar mix fortnight to-post gp',
  },
  { label: 'Drafts', path: routes.drafts, icon: FileText, keywords: 'writing gc approve review' },
  {
    label: 'Needs review',
    path: `${routes.drafts}?status=pending_review`,
    icon: CheckCircle,
    keywords: 'approve gr queue',
  },
  { label: 'Sources', path: routes.sources, icon: Rss, keywords: 'rss newsdata' },
  { label: 'Brand', path: routes.brand, icon: Palette, keywords: 'kit' },
  {
    label: 'Brand Intelligence onboarding',
    path: routes.brandOnboarding,
    icon: Sparkles,
    keywords: 'brand memory wizard linkedin website dna',
  },
  {
    label: 'Brand Intelligence dashboard',
    path: routes.brandDashboard,
    icon: Brain,
    keywords: 'brand score health topics writing visual',
  },
  { label: 'Learning', path: routes.learning, icon: GraduationCap, keywords: 'knowledge' },
  { label: 'Analytics', path: routes.analytics, icon: BarChart3, keywords: 'cost metrics' },
  { label: 'Jobs', path: routes.jobs, icon: ListTodo, keywords: 'queue' },
  { label: 'Settings', path: routes.settings, icon: Settings, keywords: 'org' },
];

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate();
  const [query, setQuery] = React.useState('');

  React.useEffect(() => {
    if (!open) setQuery('');
  }, [open]);

  const go = (path: string) => {
    onOpenChange(false);
    navigate(path);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0 max-w-xl gap-0 [&>button]:hidden">
        <Command className="rounded-[var(--radius)]" shouldFilter>
          <div className="flex items-center border-b border-border px-3">
            <Search className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
            <Command.Input
              value={query}
              onValueChange={setQuery}
              placeholder="Search pages, actions…"
              className="flex h-12 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
              No results found.
            </Command.Empty>
            <Command.Group
              heading="Pages"
              className="text-xs text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
            >
              {pages.map((p) => (
                <Command.Item
                  key={p.path}
                  value={`${p.label} ${p.keywords}`}
                  onSelect={() => go(p.path)}
                  className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm text-foreground aria-selected:bg-hover"
                >
                  <p.icon className="h-4 w-4 text-muted-foreground" />
                  {p.label}
                </Command.Item>
              ))}
            </Command.Group>
            <Command.Group
              heading="Actions"
              className="mt-2 text-xs text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
            >
              <Command.Item
                value="generate draft news"
                onSelect={() => go(routes.news)}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm aria-selected:bg-hover"
              >
                <Newspaper className="h-4 w-4 text-muted-foreground" />
                New draft from News
              </Command.Item>
              <Command.Item
                value="open review queue"
                onSelect={() => go(`${routes.drafts}?status=pending_review`)}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm aria-selected:bg-hover"
              >
                <CheckCircle className="h-4 w-4 text-muted-foreground" />
                Drafts needing review
              </Command.Item>
            </Command.Group>
          </Command.List>
          <div className="flex items-center gap-3 border-t border-border px-3 py-2 text-[11px] text-muted-foreground">
            <span>↵ Open</span>
            <span>esc Close</span>
            <span>⌘K Toggle</span>
          </div>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
