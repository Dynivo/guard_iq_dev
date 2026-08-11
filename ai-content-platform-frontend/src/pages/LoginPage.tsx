import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, useReducedMotion } from 'motion/react';
import { AlertTriangle, ArrowLeft, Moon, Sun } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { Button } from '@/design-system/ui/button';
import { Input } from '@/design-system/ui/input';
import { routes } from '@/lib/routes';

export function LoginPage() {
  const { login } = useAuth();
  const { resolved, setTheme } = useTheme();
  const navigate = useNavigate();
  const reduceMotion = useReducedMotion();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login({ email, password });
      navigate(routes.app);
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { error?: string } } })?.response?.data?.error;
      setError(message || 'Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel */}
      <aside
        className="relative hidden overflow-hidden text-teal-50 lg:flex lg:flex-col"
        style={{
          background: 'linear-gradient(155deg, #0b3d4a 0%, #0f766e 48%, #134e4a 100%)',
        }}
      >
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          aria-hidden
          style={{
            backgroundImage:
              'radial-gradient(ellipse 70% 50% at 30% 20%, rgb(94 234 212 / 0.35), transparent 55%), url("data:image/svg+xml,%3Csvg width=\'72\' height=\'72\' viewBox=\'0 0 72 72\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cpath d=\'M36 1L71 36 36 71 1 36z\' fill=\'none\' stroke=\'%23ecfdf5\' stroke-opacity=\'0.08\' stroke-width=\'1\'/%3E%3C/svg%3E")',
          }}
        />
        <div className="relative z-10 flex flex-1 flex-col justify-between p-10 xl:p-14">
          <Link to={routes.home} className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-50 text-[12px] font-bold text-[#0b3d4a]">
              CI
            </span>
            <span className="font-display text-xl font-semibold tracking-tight">
              Content Intelligence
            </span>
          </Link>

          <motion.div
            className="max-w-md"
            initial={reduceMotion ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          >
            <p className="font-display text-3xl font-semibold leading-tight tracking-tight xl:text-4xl">
              News scored. Drafts written. Visuals ready.
            </p>
            <p className="mt-4 text-base leading-relaxed text-teal-100/80">
              Sign in to your workspace — relevance, brand memory, and LinkedIn publishing in one
              professional flow.
            </p>
            <ul className="mt-8 space-y-3 text-sm text-teal-100/75">
              <li className="flex gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-200" />
                Auto-sort stories against your brand profile
              </li>
              <li className="flex gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-200" />
                Draft and approve LinkedIn posts in your voice
              </li>
              <li className="flex gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-200" />
                Generate on-brand visuals before you publish
              </li>
            </ul>
          </motion.div>

          <p className="text-xs text-teal-100/50">Enterprise AI content platform</p>
        </div>
      </aside>

      {/* Form panel */}
      <div className="relative flex min-h-screen flex-col bg-background">
        <div
          className="pointer-events-none absolute inset-0 lg:hidden"
          aria-hidden
          style={{
            background:
              'radial-gradient(ellipse 80% 45% at 50% -5%, var(--landing-glow), transparent 55%), linear-gradient(180deg, var(--landing-hero-a), var(--bg))',
          }}
        />

        <header className="relative z-10 flex h-16 items-center justify-between px-4 sm:px-8">
          <Link to={routes.home} className="flex items-center gap-2.5 lg:invisible">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--landing-ink)] text-[11px] font-bold text-[var(--landing-ink-fg)]">
              CI
            </span>
            <span className="font-display text-lg font-semibold tracking-tight">
              Content Intelligence
            </span>
          </Link>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Toggle theme"
              onClick={() => setTheme(resolved === 'dark' ? 'light' : 'dark')}
            >
              {resolved === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </Button>
          </div>
        </header>

        <div className="relative z-10 flex flex-1 items-center justify-center px-4 pb-16 sm:px-8">
          <motion.div
            className="w-full max-w-[400px]"
            initial={reduceMotion ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="mb-8">
              <h1 className="font-display text-3xl font-semibold tracking-tight">Welcome back</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Sign in to continue to your Content Intelligence workspace.
              </p>
            </div>

            <div className="rounded-2xl border border-border bg-card p-6 shadow-soft sm:p-8">
              {error && (
                <div
                  className="mb-5 flex items-start gap-2.5 rounded-lg border border-destructive/25 bg-destructive/5 px-3 py-2.5"
                  role="alert"
                >
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-destructive" />
                  <p className="text-sm text-destructive">{error}</p>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-1.5">
                  <label htmlFor="email" className="text-sm font-medium">
                    Work email
                  </label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    required
                    autoComplete="email"
                    className="h-11"
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="password" className="text-sm font-medium">
                    Password
                  </label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    required
                    autoComplete="current-password"
                    className="h-11"
                  />
                </div>
                <Button type="submit" className="h-11 w-full text-base" disabled={loading}>
                  {loading ? 'Signing in…' : 'Sign in'}
                </Button>
              </form>
            </div>

            <p className="mt-8 text-center text-sm text-muted-foreground">
              <Link
                to={routes.home}
                className="inline-flex items-center gap-1.5 text-foreground/80 transition-colors hover:text-foreground"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to home
              </Link>
            </p>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
