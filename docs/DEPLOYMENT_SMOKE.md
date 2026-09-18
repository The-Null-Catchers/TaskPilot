# Post-deployment smoke test

TaskPilot reuses the real Playwright collaboration suite for post-deployment validation. This is intentionally the same multi-user/browser coverage used in CI rather than a second, weaker smoke implementation.

## Safety

Run this only against a resettable demo/staging environment. The suite creates temporary users, workspaces, projects, tasks, comments, API tokens, webhooks, notifications, and attachments.

Do **not** point it at a customer production database unless the environment is explicitly designed for synthetic smoke traffic.

## Run from GitHub Actions

TaskPilot also provides the manual **TaskPilot deployment smoke** workflow in `.github/workflows/deployment-smoke.yml`.

Use **Actions → TaskPilot deployment smoke → Run workflow** and provide:

- `web_url` — the public HTTPS web origin, for example `https://demo.taskpilot.example.com`
- `api_url` — the public HTTPS API origin without `/api/v1`
- `confirm_resettable` — must be explicitly enabled

The workflow intentionally refuses localhost, private/reserved IP targets, non-HTTPS URLs, credential-bearing URLs, and origins with paths/query strings/fragments. It resolves the supplied hostnames and rejects non-public addresses before any smoke traffic is sent.

It checks `/health/live` and `/health/ready`, installs Chromium, runs the same deployed Playwright smoke suite described below, and uploads `taskpilot-deployment-smoke-report` with Playwright reports/traces on every run.

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

## Release evidence

For a release candidate, record the deployed commit/image version, API and web origins, workflow run URL, smoke result, and any failed environment-specific provider checks. A successful remote smoke run validates application behavior against the target deployment; it does not prove DNS ownership, backup restoration, mobile push delivery, or external alert routing.

## Remaining environment-specific checks

These cannot be proven by a generic remote browser runner and stay explicit release checks:

- real Android/iOS push delivery and notification taps
- APNs/FCM token refresh on physical devices
- TestFlight / Play internal installation
- backup restore drill
- TLS/DNS/reverse-proxy correctness outside the application
- production collector/alert routing to the chosen monitoring provider
