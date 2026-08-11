import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { routes } from '@/lib/routes';

const GO_MAP: Record<string, string> = {
  d: routes.app,
  n: routes.news,
  c: routes.drafts,
  i: routes.drafts,
  r: `${routes.drafts}?status=pending_review`,
  a: routes.analytics,
  j: routes.jobs,
  g: routes.news,
  b: routes.brand,
  s: routes.sources,
};

export function useKeyboardShortcuts() {
  const navigate = useNavigate();
  const pendingG = React.useRef(false);
  const timer = React.useRef<number | null>(null);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable);

      if (typing) return;

      if (e.key === 'Escape') {
        pendingG.current = false;
        return;
      }

      if (pendingG.current) {
        const path = GO_MAP[e.key.toLowerCase()];
        pendingG.current = false;
        if (timer.current) window.clearTimeout(timer.current);
        if (path) {
          e.preventDefault();
          navigate(path);
        }
        return;
      }

      if (e.key.toLowerCase() === 'g' && !e.metaKey && !e.ctrlKey) {
        pendingG.current = true;
        timer.current = window.setTimeout(() => {
          pendingG.current = false;
        }, 800);
      }
    };

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigate]);
}
