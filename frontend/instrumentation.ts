// Server-side Sentry initialization. Next.js 13+ pattern: `register()`
// runs once at process boot. Gated on NEXT_PUBLIC_SENTRY_DSN being set
// so dev/test environments without a DSN are silent no-ops.
//
// Source-map upload + tunnel route are NOT configured here — run
// `npx @sentry/wizard@latest -i nextjs` post-merge to wire next.config
// for production builds.

import * as Sentry from "@sentry/nextjs";

export async function register() {
  if (!process.env.NEXT_PUBLIC_SENTRY_DSN) return;

  if (process.env.NEXT_RUNTIME === "nodejs") {
    Sentry.init({
      dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
      tracesSampleRate: 0.1,
      environment: process.env.VERCEL_ENV ?? "development",
      release: process.env.VERCEL_GIT_COMMIT_SHA,
      sendDefaultPii: false,
    });
  }
  // Edge runtime init can be added here when we deploy any edge routes;
  // omitted in v1 since the frontend is all SSR/RSC node runtime.
}

export const onRequestError = Sentry.captureRequestError;
