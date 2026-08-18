import { createBrowserRouter, Navigate, useParams } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { AppShell } from '@/layouts/DashboardLayout';
import { AuthGuard } from './AuthGuard';
import { Skeleton } from '@/design-system/ui/skeleton';
import { routes } from '@/lib/routes';

const LoginPage = lazy(() => import('@/pages/LoginPage').then((m) => ({ default: m.LoginPage })));
const DashboardPage = lazy(() =>
  import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage }))
);
const NewsFeedPage = lazy(() =>
  import('@/pages/NewsFeedPage').then((m) => ({ default: m.NewsFeedPage }))
);
const CapturePage = lazy(() =>
  import('@/pages/CapturePage').then((m) => ({ default: m.CapturePage }))
);
const DraftsPage = lazy(() => import('@/pages/DraftsPage').then((m) => ({ default: m.DraftsPage })));
const DraftDetailPage = lazy(() =>
  import('@/pages/DraftDetailPage').then((m) => ({ default: m.DraftDetailPage }))
);
const GenerationPage = lazy(() =>
  import('@/pages/GenerationPage').then((m) => ({ default: m.GenerationPage }))
);
const ReviewQueuePage = lazy(() =>
  import('@/pages/ReviewQueuePage').then((m) => ({ default: m.ReviewQueuePage }))
);
const CarouselPage = lazy(() =>
  import('@/pages/CarouselPage').then((m) => ({ default: m.CarouselPage }))
);
const BrandKitPage = lazy(() =>
  import('@/pages/BrandKitPage').then((m) => ({ default: m.BrandKitPage }))
);
const NewsSourcesPage = lazy(() =>
  import('@/pages/NewsSourcesPage').then((m) => ({ default: m.NewsSourcesPage }))
);
const JobsPage = lazy(() => import('@/pages/JobsPage').then((m) => ({ default: m.JobsPage })));
const LearningPage = lazy(() =>
  import('@/pages/LearningPage').then((m) => ({ default: m.LearningPage }))
);
const AnalyticsPage = lazy(() =>
  import('@/pages/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage }))
);
const ImagesPage = lazy(() => import('@/pages/ImagesPage').then((m) => ({ default: m.ImagesPage })));
const TypographyPage = lazy(() =>
  import('@/pages/TypographyPage').then((m) => ({ default: m.TypographyPage }))
);
const ProvidersPage = lazy(() =>
  import('@/pages/ProvidersPage').then((m) => ({ default: m.ProvidersPage }))
);
const SettingsPage = lazy(() =>
  import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage }))
);
const PromptsPage = lazy(() =>
  import('@/pages/PromptsPage').then((m) => ({ default: m.PromptsPage }))
);
const PublishingPlanPage = lazy(() =>
  import('@/pages/PublishingPlanPage').then((m) => ({ default: m.PublishingPlanPage }))
);
const ToPostPage = lazy(() =>
  import('@/pages/ToPostPage').then((m) => ({ default: m.ToPostPage }))
);

function PageFallback() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function L({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<PageFallback />}>{children}</Suspense>;
}

function LegacyDraftRedirect() {
  const { draftId } = useParams();
  return <Navigate to={draftId ? routes.draft(draftId) : routes.drafts} replace />;
}

export const router = createBrowserRouter([
  {
    path: routes.home,
    element: <Navigate to={routes.app} replace />,
  },
  {
    path: routes.login,
    element: (
      <L>
        <LoginPage />
      </L>
    ),
  },
  {
    path: routes.app,
    element: (
      <AuthGuard>
        <AppShell />
      </AuthGuard>
    ),
    children: [
      { index: true, element: <L><DashboardPage /></L> },
      { path: 'news', element: <L><NewsFeedPage /></L> },
      { path: 'capture', element: <L><CapturePage /></L> },
      { path: 'plan', element: <L><PublishingPlanPage /></L> },
      { path: 'to-post', element: <L><ToPostPage /></L> },
      { path: 'ideas', element: <Navigate to={routes.plan} replace /> },
      { path: 'drafts', element: <L><DraftsPage /></L> },
      { path: 'drafts/:draftId', element: <L><DraftDetailPage /></L> },
      { path: 'generation', element: <L><GenerationPage /></L> },
      { path: 'carousels', element: <L><CarouselPage /></L> },
      { path: 'images', element: <L><ImagesPage /></L> },
      { path: 'typography', element: <L><TypographyPage /></L> },
      { path: 'review', element: <L><ReviewQueuePage /></L> },
      { path: 'learning', element: <L><LearningPage /></L> },
      { path: 'prompts', element: <L><PromptsPage /></L> },
      { path: 'brand', element: <L><BrandKitPage /></L> },
      { path: 'brand/onboarding', element: <Navigate to={routes.brand} replace /> },
      { path: 'brand/intelligence', element: <Navigate to={routes.brand} replace /> },
      { path: 'sources', element: <L><NewsSourcesPage /></L> },
      { path: 'providers', element: <L><ProvidersPage /></L> },
      { path: 'jobs', element: <L><JobsPage /></L> },
      { path: 'analytics', element: <L><AnalyticsPage /></L> },
      { path: 'settings', element: <L><SettingsPage /></L> },
    ],
  },
  // Legacy bookmarks → workspace
  { path: '/news', element: <Navigate to={routes.news} replace /> },
  { path: '/drafts', element: <Navigate to={routes.drafts} replace /> },
  { path: '/drafts/:draftId', element: <LegacyDraftRedirect /> },
  { path: '/sources', element: <Navigate to={routes.sources} replace /> },
  { path: '/brand', element: <Navigate to={routes.brand} replace /> },
  { path: '/brand/onboarding', element: <Navigate to={routes.brand} replace /> },
  { path: '/brand/intelligence', element: <Navigate to={routes.brand} replace /> },
  { path: '/analytics', element: <Navigate to={routes.analytics} replace /> },
  { path: '/settings', element: <Navigate to={routes.settings} replace /> },
  { path: '*', element: <Navigate to={routes.home} replace /> },
]);
