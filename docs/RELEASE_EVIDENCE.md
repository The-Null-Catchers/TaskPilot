# Release validation evidence

This document records factual evidence for the current TaskPilot release candidate without treating implementation or CI coverage as proof of external provider/device validation.

## Release candidate

- Application release commit reviewed: `ef62b239c3676c5f577c0b026ff02656e25f3b72`
- Branch: `main`
- Review date: 2026-10-04 UTC
- Last validated hosted environment recorded by the project:
  - Web: https://taskpilot-web-test.onrender.com
  - API: https://taskpilot-api-test.onrender.com

The release-evidence document is documentation and can be updated after the application release commit. External checks below are only marked complete when direct evidence exists.

## Repository and branch state

Repository cleanup is complete for the temporary Android build branch:

- `build/render-test-apk` is no longer present.
- Current branches at this review were `main` and the short-lived feature branch `feat/mobile-milestone-management` for open PR #122.
- The feature PR is not part of this release-validation scope until intentionally merged and revalidated.

The former temporary branch had contained only the build-only workflow and no unique product code, as recorded by the earlier release review.

## Current-main CI

The latest exact application release commit passed the full repository gate:

- Workflow: **TaskPilot CI**
- Run: https://github.com/The-Null-Catchers/TaskPilot/actions/runs/37164377506
- Commit: `ef62b239c3676c5f577c0b026ff02656e25f3b72`
- Result: success
- Date: 2026-10-04 UTC

Jobs verified green:

- backend lint, Alembic empty-database migration validation, and backend tests
- web production dependency audit, lint, tests, TypeScript typecheck, and Next.js build
- Playwright Chromium E2E against FastAPI/PostgreSQL/Redis/S3-compatible storage
- Flutter analyze/tests plus release APK and AAB builds
- Flutter analyze/tests plus unsigned iOS release build
- production Compose validation
- observability configuration validation
- backend production Docker image build
- web production Docker image build

The regular Android CI build still uses a placeholder API target and is a contributor/test artifact. It is not evidence of the production-signed Android release.

## Hosted deployment smoke

The most recent recorded guarded hosted-environment smoke remains:

- Workflow: **TaskPilot deployment smoke**
- Run: https://github.com/The-Null-Catchers/TaskPilot/actions/runs/35390223028
- Commit: `5cfd228fc59de5987bbe5e70b6f16630e5d5d939`
- Result: success
- Hosted web origin: https://taskpilot-web-test.onrender.com
- Hosted API origin: https://taskpilot-api-test.onrender.com
- Recorded `/health/live`: `{"api":"ok"}`
- Recorded `/health/ready`: `{"api":"ok","database":"ok","redis":"ok"}`

That run exercised registration/onboarding, project/task creation, invitations, permissions, collaboration, notifications, realtime updates, optimistic conflicts, archive/restore, saved views, and the hosted attachment upload/download/authorization/delete path.

A fresh smoke run against the current 2026-10-04 release commit has **not** yet been recorded. This remains a release-validation blocker.

## Android release state

Implemented and CI-validated:

- Android APK/AAB release compilation in regular CI
- manual **TaskPilot Android signed release** workflow
- signing-input validation
- signature verification steps
- secure Firebase client configuration injection support
- optional Google Play internal-track upload path

Not yet evidenced:

- a successful production-signed Android workflow run
- production artifact name/version/build/commit evidence
- installation on a physical Android device
- physical-device offline/reconnect/conflict/session-expiry/Sync Center validation
- Firebase/FCM registration and delivery on a real device
- Google Play internal-track install and launch

Do not mark these complete until the corresponding workflow/device/provider evidence exists.

## iOS release state

Verified in CI:

- Flutter analyze/tests
- unsigned iOS release build

Not yet evidenced:

- a successful signed IPA workflow run
- TestFlight upload
- real-iPhone validation
- production APNs/FCM delivery

These remain externally blocked until Apple credentials and a physical iPhone are available.

## Workers and scheduled jobs

The codebase and CI cover Celery-backed invitation/notification/webhook behavior, retries, scheduled reminders, and failure handling.

Still not operationally evidenced on the hosted environment:

- Celery worker process running and connected to hosted Redis
- a real hosted background job processed by that worker
- exactly one Celery Beat scheduler active
- scheduled jobs emitted by Beat
- failed jobs/retries visible in hosted operations

Provider delivery must not be claimed if SMTP/push credentials are absent; successful job execution with graceful provider failure is sufficient evidence for that case.

## Observability

Repository implementation and CI validation exist for Prometheus, Grafana, Loki, Alertmanager, PostgreSQL exporter, Redis exporter, blackbox monitoring, and associated configuration.

Still required for a production observability claim:

- collectors connected to the hosted TaskPilot deployment
- real request/latency/5xx/readiness traffic visible
- PostgreSQL and Redis health visible
- realtime/WebSocket and worker visibility confirmed
- retry exhaustion logs observable
- real alert receivers configured only through secrets
- safe alert test delivered to the intended destination

## Backup and restore

The backup/restore/rollback runbook exists.

No staging/test restore-drill evidence is currently recorded. A valid drill must capture:

- backup timestamp
- database backup
- object-storage state/version
- application commit
- Alembic revision
- restore target
- restore completion
- login after restore
- workspace/project/task integrity
- attachment-reference integrity and object downloads

Never run destructive restore testing against important live data.

## Public demo and screenshots

The repository includes realistic Northstar demo data and a seeder intended for portfolio/demo use.

Still not evidenced as complete:

- currently reachable seeded public demo
- final polished screenshots captured from that live seeded environment
- README screenshot section based on real hosted demo content

Do not present an empty dashboard as the portfolio demo.

## Live security configuration

Source-level production safeguards and CI regressions are implemented, but the following deployed settings still require hosting/control-plane verification:

- PostgreSQL private/non-public
- Redis private/non-public
- metrics protected
- object-storage bucket not globally public
- signed URLs expire
- HTTPS-only browser/API paths
- WSS-only production realtime
- restricted production CORS
- correct refresh-cookie `Secure`/SameSite policy
- no unsafe production default secrets
- no test JWT secrets
- no credentials exposed in build logs
- no Firebase service credentials committed
- no Android signing keys committed
- no object-storage secrets exposed

Passing source CI is not a substitute for this deployment review.

## Dependency state

The current release gate is green. Avoid large framework migrations immediately before release unless they are security-relevant, compatible, and fully validated by the complete CI/release matrix.

Open PR #122 is a product feature/parity change rather than release-evidence work and should not be treated as required by this release-validation checklist.

## Licensing

No project license has been selected. This remains an explicit owner decision. Do not infer or add a license without that decision.

## Remaining external release blockers

Before calling TaskPilot fully release/portfolio validated, complete or explicitly accept the following external/manual items:

- rerun guarded deployment smoke against the final release commit
- verify hosted Celery worker and exactly one Beat scheduler
- exercise and observe at least one hosted worker-backed job
- run the production-signed Android workflow with real signing secrets
- validate the signed build on a physical Android device
- validate FCM on that real device
- validate Google Play internal testing if credentials are available
- validate signed iOS/TestFlight and a real iPhone when Apple credentials/device are available
- connect observability to live traffic and verify real alert delivery
- perform and record a safe staging/test backup-restore drill
- finalize a currently reachable seeded public demo
- capture and add polished portfolio screenshots
- make the final license decision

Core application implementation is not the remaining blocker; the outstanding work is external validation and release evidence.
