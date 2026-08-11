import { driver } from 'driver.js';
import 'driver.js/dist/driver.css';

export function startOnboardingTour() {
  const d = driver({
    showProgress: true,
    animate: true,
    overlayOpacity: 0.55,
    steps: [
      {
        element: '#app-sidebar',
        popover: {
          title: 'Welcome to Content Intelligence',
          description: 'Simple flow: News → Drafts (approve + images) → Brand / Sources when you set things up.',
          side: 'right',
        },
      },
      {
        element: '[data-tour="nav-news"]',
        popover: {
          title: 'Step 1 — News',
          description: 'Pick an article and generate a LinkedIn draft from it.',
        },
      },
      {
        element: '[data-tour="nav-generation"]',
        popover: {
          title: 'Step 2 — Drafts',
          description: 'Open a draft to approve or reject, then generate images on the same page.',
        },
      },
    ],
    onDestroyed: () => {
      localStorage.setItem('onboarding-done', '1');
    },
  });
  d.drive();
}
