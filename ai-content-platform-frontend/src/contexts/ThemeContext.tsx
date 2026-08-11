import * as React from 'react';

type Theme = 'light' | 'dark' | 'system';

interface ThemeContextValue {
  theme: Theme;
  resolved: 'light' | 'dark';
  setTheme: (theme: Theme) => void;
}

const ThemeContext = React.createContext<ThemeContextValue | null>(null);

function getSystemTheme(): 'light' | 'dark' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = React.useState<Theme>(() => {
    return (localStorage.getItem('theme') as Theme) || 'system';
  });
  const [resolved, setResolved] = React.useState<'light' | 'dark'>(() => {
    if (typeof window === 'undefined') return 'light';
    const stored = (localStorage.getItem('theme') as Theme) || 'system';
    return stored === 'system' ? getSystemTheme() : stored;
  });

  const applyResolved = React.useCallback((next: 'light' | 'dark') => {
    setResolved(next);
    document.documentElement.classList.toggle('dark', next === 'dark');
    document.documentElement.style.colorScheme = next;
  }, []);

  React.useEffect(() => {
    const next = theme === 'system' ? getSystemTheme() : theme;
    applyResolved(next);
    localStorage.setItem('theme', theme);
  }, [theme, applyResolved]);

  React.useEffect(() => {
    if (theme !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => applyResolved(getSystemTheme());
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [theme, applyResolved]);

  const setTheme = React.useCallback((t: Theme) => setThemeState(t), []);

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = React.useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
