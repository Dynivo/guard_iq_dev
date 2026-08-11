import { Link, useNavigate } from 'react-router-dom';
import { motion, useReducedMotion } from 'motion/react';
import {
  ArrowRight,
  Moon,
  Newspaper,
  ShieldCheck,
  Sparkles,
  Sun,
  TrendingUp,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { Button } from '@/design-system/ui/button';
import { routes } from '@/lib/routes';

const FLOW = [
  {
    step: '01',
    title: 'Score the news',
    body: 'Ingest sources, surface trends, and auto-rank stories against your brand profile.',
    icon: Newspaper,
  },
  {
    step: '02',
    title: 'Draft in your voice',
    body: 'Generate LinkedIn copy with hooks, body, and CTAs tuned to how you actually write.',
    icon: Sparkles,
  },
  {
    step: '03',
    title: 'Ship with visuals',
    body: 'Approve the post, create on-brand images, preview the feed, then publish with confidence.',
    icon: ShieldCheck,
  },
] as const;

export function LandingPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const { resolved, setTheme } = useTheme();
  const navigate = useNavigate();
  const reduceMotion = useReducedMotion();

  const primaryHref = isAuthenticated ? routes.app : routes.login;
  const primaryLabel = isAuthenticated ? 'Open workspace' : 'Sign in';

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="relative z-20 border-b border-border/50 bg-background/75 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link to={routes.home} className="flex min-w-0 items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--landing-ink)] text-[11px] font-bold tracking-tight text-[var(--landing-ink-fg)]">
              CI
            </span>
            <span className="truncate font-display text-lg font-semibold tracking-tight">
              Content Intelligence
            </span>
          </Link>
          <nav className="flex items-center gap-1 sm:gap-2">
            <a
              href="#how-it-works"
              className="hidden rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground sm:inline"
            >
              How it works
            </a>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Toggle theme"
              onClick={() => setTheme(resolved === 'dark' ? 'light' : 'dark')}
            >
              {resolved === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </Button>
            {!isLoading && (
              <Button asChild size="sm">
                <Link to={primaryHref}>{primaryLabel}</Link>
              </Button>
            )}
          </nav>
        </div>
      </header>

      {/* Hero — brand first, one composition */}
      <section className="relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-0"
          aria-hidden
          style={{
            background:
              'radial-gradient(ellipse 90% 70% at 85% 15%, var(--landing-glow), transparent 50%), linear-gradient(160deg, var(--landing-hero-a) 0%, var(--landing-hero-b) 42%, var(--bg) 100%)',
          }}
        />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.28] dark:opacity-[0.2]"
          aria-hidden
          style={{
            backgroundImage:
              'url("data:image/svg+xml,%3Csvg width=\'72\' height=\'72\' viewBox=\'0 0 72 72\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cpath d=\'M36 1L71 36 36 71 1 36z\' fill=\'none\' stroke=\'%230b3d4a\' stroke-opacity=\'0.07\' stroke-width=\'1\'/%3E%3C/svg%3E")',
          }}
        />

        <div className="relative mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl items-center gap-12 px-4 py-14 sm:px-6 lg:grid-cols-[1fr_1.05fr] lg:gap-16 lg:py-10">
          <motion.div
            className="max-w-lg"
            initial={reduceMotion ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          >
            <p className="font-display text-[2.75rem] font-semibold leading-[1.05] tracking-tight text-[var(--landing-ink)] sm:text-5xl lg:text-[3.35rem]">
              Content Intelligence
            </p>
            <h1 className="mt-5 text-xl font-medium leading-snug tracking-tight text-foreground sm:text-2xl">
              LinkedIn posts from news — scored, drafted, and visualized in one workspace.
            </h1>
            <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">
              Built for security-led IT teams who need relevant stories, on-brand copy, and
              publish-ready visuals without hopping tools.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button size="lg" className="h-12 px-6 text-base" onClick={() => navigate(primaryHref)}>
                {isAuthenticated ? 'Open workspace' : 'Sign in to workspace'}
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="h-12 px-6 text-base"
                onClick={() =>
                  document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })
                }
              >
                See the flow
              </Button>
            </div>
          </motion.div>

          <motion.div
            className="relative -mx-4 sm:mx-0 lg:justify-self-stretch"
            initial={reduceMotion ? false : { opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="overflow-hidden border-y border-border/80 bg-[#f4f2ee] shadow-elevated sm:rounded-2xl sm:border dark:border-white/10 dark:bg-[#111827]">
              <div className="flex items-center justify-between border-b border-black/5 bg-white px-5 py-3.5 dark:border-white/10 dark:bg-[#0f172a]">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Feed preview
                </p>
                <span className="text-[11px] text-muted-foreground">LinkedIn · Desktop</span>
              </div>
              <div className="bg-white px-5 py-5 dark:bg-[#0f172a]">
                <div className="flex items-start gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#0a66c2] text-sm font-semibold text-white">
                    G
                  </div>
                  <div className="min-w-0 pt-0.5">
                    <p className="text-sm font-semibold text-foreground">Guard IQ</p>
                    <p className="text-xs text-muted-foreground">UK security-led IT · Just now</p>
                  </div>
                </div>
                <p className="mt-4 text-[15px] font-medium leading-snug text-foreground">
                  Could AI be your next security threat?
                </p>
                <p className="mt-2 line-clamp-3 text-[13.5px] leading-relaxed text-muted-foreground">
                  Agents are shipping faster than controls. Here is what care and professional
                  services leaders should pressure-test this quarter…
                </p>
                <motion.div
                  className="mt-4 aspect-[16/10] overflow-hidden rounded-md"
                  style={{
                    background: 'linear-gradient(145deg, #0b3d4a 0%, #0f766e 45%, #134e4a 100%)',
                  }}
                  animate={reduceMotion ? undefined : { scale: [1, 1.015, 1] }}
                  transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
                >
                  <div className="flex h-full flex-col justify-end p-6">
                    <p className="font-display text-2xl font-semibold leading-tight text-teal-50 sm:text-3xl">
                      Secure the agent era
                    </p>
                    <p className="mt-1.5 text-sm text-teal-100/75">On-brand visual · navy & teal</p>
                  </div>
                </motion.div>
                <div className="mt-4 flex gap-8 border-t border-border/60 pt-3 text-xs font-medium text-muted-foreground">
                  <span>Like</span>
                  <span>Comment</span>
                  <span>Repost</span>
                  <span>Send</span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="border-t border-border">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-24">
          <motion.div
            className="max-w-2xl"
            initial={reduceMotion ? false : { opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.45 }}
          >
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">How it works</p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              From headline to publish-ready post.
            </h2>
            <p className="mt-3 text-muted-foreground">
              One workspace for news, drafts, and visuals — so editors and brand leads stay aligned.
            </p>
          </motion.div>

          <div className="mt-14 grid gap-10 md:grid-cols-3 md:gap-8">
            {FLOW.map((item, i) => (
              <motion.div
                key={item.step}
                initial={reduceMotion ? false : { opacity: 0, y: 14 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-40px' }}
                transition={{ duration: 0.4, delay: i * 0.07 }}
              >
                <p className="font-display text-3xl font-semibold text-[var(--landing-ink)]/20">
                  {item.step}
                </p>
                <div className="mt-4 flex h-9 w-9 items-center justify-center rounded-md bg-[var(--landing-ink)]/10 text-[var(--landing-ink)]">
                  <item.icon className="h-4 w-4" />
                </div>
                <h3 className="mt-4 text-lg font-semibold tracking-tight">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{item.body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Product signal — one job: what you get */}
      <section className="border-t border-border bg-[var(--landing-hero-a)]/50 dark:bg-card/30">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-24">
          <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">
                In the workspace
              </p>
              <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
                Relevance, brand memory, and trends — not a blank prompt box.
              </h2>
              <p className="mt-3 max-w-md text-muted-foreground">
                Your brand profile steers what counts as relevant. Learning from Yes / No keeps
                scoring honest over time.
              </p>
            </div>
            <ul className="space-y-0 divide-y divide-border border-y border-border">
              {[
                {
                  title: 'Auto relevance',
                  body: 'Stories sorted against your profile — relevant or not, without a review pile.',
                  icon: ShieldCheck,
                },
                {
                  title: 'Brand profile memory',
                  body: 'Edit or paste a Claude/ChatGPT profile; thumbs on News teach it what to keep.',
                  icon: Sparkles,
                },
                {
                  title: 'Trends & sorting',
                  body: 'See hot categories and topic momentum, then sort by relevance or trending.',
                  icon: TrendingUp,
                },
              ].map((row) => (
                <li key={row.title} className="flex gap-4 py-5">
                  <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-background text-[var(--landing-ink)] shadow-soft">
                    <row.icon className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="font-semibold tracking-tight">{row.title}</p>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{row.body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="border-t border-border">
        <div
          className="relative overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, #0b3d4a 0%, #0f766e 52%, #134e4a 100%)',
          }}
        >
          <div
            className="pointer-events-none absolute inset-0 opacity-30"
            aria-hidden
            style={{
              backgroundImage:
                'radial-gradient(circle at 20% 80%, rgb(94 234 212 / 0.35), transparent 40%)',
            }}
          />
          <div className="relative mx-auto flex max-w-6xl flex-col items-start gap-8 px-4 py-20 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-xl">
              <h2 className="font-display text-3xl font-semibold tracking-tight text-teal-50 sm:text-4xl">
                Run your content workflow with clarity.
              </h2>
              <p className="mt-3 text-base text-teal-100/80">
                Sign in to score news, approve drafts, and generate LinkedIn visuals in one place.
              </p>
            </div>
            <Button
              size="lg"
              className="h-12 bg-teal-50 px-7 text-base text-[#0b3d4a] hover:bg-white"
              onClick={() => navigate(primaryHref)}
            >
              {isAuthenticated ? 'Open workspace' : 'Sign in to workspace'}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>
            <span className="font-medium text-foreground">Content Intelligence</span>
            {' · '}
            Enterprise AI content platform
          </p>
          <p>© {new Date().getFullYear()}</p>
        </div>
      </footer>
    </div>
  );
}
