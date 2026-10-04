# Release validation evidence

This document records factual evidence for the current TaskPilot release candidate without treating implementation or CI coverage as proof of external provider/device validation.

## Release candidate

- Latest `main` application/operations commit reviewed before this evidence-only refresh: `ab829b808bd8f3070ed6cae1240e45bd2e743f36`
- Branch: `main`
- Review date: 2026-10-04 UTC
- Hosted demo/staging services:
  - Web: https://taskpilot-web-test.onrender.com
  - API: https://taskpilot-api-test.onrender.com

The release-evidence document can be updated after the application release commit. External checks below are only marked complete when direct evidence exists.

## Repository and branch state

Repository cleanup is complete for the temporary Android build branch:

- `build/render-test-apk` is no longer present.
- Current branches are `main` plus the short-lived `feat/mobile-milestone-management` branch for open PR #122.
- PR #122 is product/parity work and is not required by this release-validation checklist, so it was not merged as part of this review.

The former temporary build branch contained no unique product code, as recorded by the earlier release review.

## Current-main CI

The latest reviewed `main` commit passed the full repository gate:

- Workflow: **TaskPilot CI**
- Run: https://github.com/The-Null-Catchers/TaskPilot/actions/runs/37200089575
- Commit: `ab829b808bd8f3070ed6cae1240e45bd2e743f36`
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

## Hosted deployment state

Render control-plane inspection on 2026-10-04 found:

- `taskpilot-web-test` is active, auto-deploying from `main`, region Frankfurt.
- The currently live web deploy is application commit `ef62b239c3676c5f577c0b026ff02656e25f3b72`; later commits inspected during this release review did not produce a newer web deploy through Render's path-aware behavior.
- `taskpilot-api-test` is active, auto-deploying from `main`, region Frankfurt.
- The latest API deploy remains application commit `ef967836af2e86b8437decb03cc7fe82cba70b72`; later commits did not require a backend deploy through the service's path-aware auto-deploy behavior.
- Hosted PostgreSQL `taskpilot-db-test` is available on PostgreSQL 17.
- Hosted Redis `taskpilot-redis-test` is available in Frankfurt.
- A prior read-only live database check recorded Alembic revision `0016_product_settings` and non-empty application data.

These checks establish that the expected Render resources and persisted application data exist. They do not replace the guarded browser smoke suite.

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

A fresh smoke run against the current release window has **not** yet been recorded. This remains a release-validation blocker.

## Workers and scheduled jobs

Repository production configuration defines:

- Celery worker: `celery -A app.worker.celery worker --loglevel=INFO`
- Celery Beat: `celery -A app.worker.celery beat --loglevel=INFO`

Render control-plane inspection on 2026-10-04 again found **no TaskPilot worker service and no TaskPilot Beat service**. Only the TaskPilot web and API services are deployed.

Therefore the hosted worker/Beat requirement is not merely missing evidence: the current Render staging/demo environment does not contain those processes. The following are unverified and currently unavailable on this environment:

- worker connection to Redis
- real worker-backed job processing
- exactly one Beat scheduler
- scheduled job emission
- hosted retries/failure visibility

Do not mark these complete until the worker and Beat processes are actually deployed and exercised.

## Android release state

Implemented and CI-validated:

- Android APK/AAB release compilation in regular CI
- manual **TaskPilot Android signed release** workflow
- signing-input validation
- signature verification steps
- secure Firebase client configuration injection support
- optional Google Play internal-track upload path

Current external evidence:

- The latest signed-release run found during this review is https://github.com/The-Null-Catchers/TaskPilot/actions/runs/35602021813 on commit `371b8263d68991d12d139ea433c5c9f33de52b1d`.
- That run concluded **failure** and therefore is not production-signed release evidence.

Not yet evidenced:

- a successful production-signed Android workflow run with real signing secrets
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

## Observability

Repository implementation and CI validation exist for Prometheus, Grafana, Loki, Alertmanager, PostgreSQL exporter, Redis exporter, blackbox monitoring, and associated configuration.

No dedicated TaskPilot Prometheus/Grafana/Loki/Alertmanager services are present in the connected Render workspace.

Still required for a production observability claim:

- collectors connected to the hosted TaskPilot deployment
- real request/latency/5xx/readiness traffic visible
- PostgreSQL and Redis health visible in the chosen observability stack
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

The connected Render database has previously been confirmed non-empty, but this review has not established that the public environment is the intended polished Northstar portfolio dataset.

Still not evidenced as complete:

- final seeded portfolio-demo state
- final polished screenshots captured from that live seeded environment
- README screenshot section based on real hosted demo content

Do not present an empty or accidental test dataset as the portfolio demo.

## Live security configuration

Render control-plane verification on 2026-10-04 established:

- Redis has no public IP allow-list entries and is not exposed through a public Render web service.
- Web and API are public HTTPS Render services, as expected for the demo/staging application.
- PostgreSQL `taskpilot-db-test` currently has an IP allow-list entry of `0.0.0.0/0` (`everywhere`). This fails the release requirement that PostgreSQL be private/restricted and must be corrected before claiming production-safe live configuration.

Still requiring direct verification or remediation:

- restrict PostgreSQL network access
- metrics protection
- object-storage bucket not globally public
- signed URL expiry in live configuration
- WSS-only production realtime
- restricted production CORS values
- correct refresh-cookie `Secure`/SameSite deployment values
- no unsafe production default secrets or test JWT secrets
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

- rerun guarded deployment smoke against the final release window
- deploy a real Celery worker and exactly one Beat process to the hosted environment
- exercise and observe at least one hosted worker-backed job
- restrict hosted PostgreSQL network access
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

Core application implementation is not the remaining blocker; the outstanding work is external deployment completion, validation, and release evidence.
