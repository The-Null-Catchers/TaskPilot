# Post-deployment smoke test

TaskPilot reuses the real Playwright collaboration suite for post-deployment validation. This is intentionally the same multi-user/browser coverage used in CI rather than a second, weaker smoke implementation.

## Safety

Run this only against a resettable demo/staging environment. The suite creates temporary users, workspaces, projects, tasks, comments, API tokens, webhooks, notifications, and attachments.

Do **not** point it at a customer production database unless the environment is explicitly designed for synthetic smoke traffic.

## Run against a deployed environment

From `web/`:

```bash
npm install
npx playwright install chromium

E2E_BASE_URL=https://demo.taskpilot.example.com \
E2E_API_URL=https://api.demo.taskpilot.example.com/api/v1 \
npm run smoke:deployment
```

The web origin must be allowed by API CORS/WebSocket-origin configuration and the API must be reachable from the runner.

## Automated coverage

The smoke suite verifies:

- browser registration/login and onboarding
- workspace creation and access
- project/board access
- task creation and editing
- second-user invitation and assignment
- comments and mentions
- notification creation
- realtime WebSocket updates between sessions
- optimistic conflict handling
- task movement/completion
- archive and restore
- saved views
- session creation/revocation and refresh-token rejection after revocation
- scoped API tokens and revocation
- outbound webhook lifecycle
- real attachment upload through the browser
- attachment metadata backed by S3-compatible storage
- signed attachment download
- unauthorized attachment-download denial
- attachment deletion

## Operations checks before the browser suite

Verify dependency-aware health independently so infrastructure failures are immediately obvious:

```bash
curl -fsS https://api.demo.taskpilot.example.com/health/live
curl -fsS https://api.demo.taskpilot.example.com/health/ready
```

Also confirm the Celery worker and Beat process are running. When SMTP/push/webhook delivery is enabled, inspect worker delivery state after the suite rather than treating a successful synchronous API response as proof that every external provider accepted the message.

## Remaining environment-specific checks

These cannot be proven by a generic remote browser runner and stay explicit release checks:

- real Android/iOS push delivery and notification taps
- APNs/FCM token refresh on physical devices
- TestFlight / Play internal installation
- backup restore drill
- TLS/DNS/reverse-proxy correctness outside the application
- production collector/alert routing to the chosen monitoring provider
