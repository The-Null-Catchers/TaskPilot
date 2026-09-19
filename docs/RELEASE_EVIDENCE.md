# Release validation evidence

This document records evidence for the current TaskPilot release candidate without treating implementation or CI coverage as proof of external provider/device validation.

## Release candidate

- Git commit: `5cfd228fc59de5987bbe5e70b6f16630e5d5d939`
- Branch: `main`
- Last validated hosted environment:
  - Web: https://taskpilot-web-test.onrender.com
  - API: https://taskpilot-api-test.onrender.com
- Validation date: 2026-09-18 UTC

## Repository and CI

Required CI passed on the exact release commit:

- Workflow: **TaskPilot CI**
- Run: https://github.com/The-Null-Catchers/TaskPilot/actions/runs/35389794789
- Result: success
- Jobs passed:
  - backend lint, migrations, and tests
  - web lint, tests, typecheck, and production build
  - Chromium browser E2E
  - Flutter analyze/tests plus Android release APK/AAB builds
  - Flutter analyze/tests plus unsigned iOS release build
  - production Docker/Compose validation and image builds

Artifacts retained by that run:

- `taskpilot-android` — credential-free contributor/test APK/AAB artifact
- `taskpilot-ios-unsigned` — unsigned iOS release build
- `taskpilot-playwright-report` — browser E2E report

These artifacts are not substitutes for production signing or device/store validation.

## Hosted deployment smoke

The guarded hosted-environment smoke workflow passed on the same commit:

- Workflow: **TaskPilot deployment smoke**
- Run: https://github.com/The-Null-Catchers/TaskPilot/actions/runs/35390223028
- Result: success
- Report artifact: `taskpilot-deployment-smoke-report` (artifact ID `10565541580`)
- Hosted web origin: https://taskpilot-web-test.onrender.com
- Hosted API origin: https://taskpilot-api-test.onrender.com
- `/health/live`: `{"api":"ok"}`
- `/health/ready`: `{"api":"ok","database":"ok","redis":"ok"}`

The deployed Playwright smoke suite completed **3/3 tests** successfully. It covered:

- registration, onboarding, and real board/task creation
- invitations, permissions, collaboration, notifications, realtime updates, optimistic conflicts, archive/restore, and saved views
- real S3-compatible attachment upload/download flow, signed download authorization, unauthorized access denial, and deletion

This proves the application paths exercised by the smoke suite against that hosted target at that point in time. It does not prove that every infrastructure process or third-party provider is currently healthy.

## Object storage

Remote browser smoke passed the attachment storage scenario against the hosted environment. That validates the deployed S3-compatible attachment behavior exercised by the test suite, including controlled download and authorization.

Cloud provider credentials, bucket policy, and runtime environment values are external deployment configuration and are intentionally not recorded here. The object store must remain private except for short-lived signed access flows.

## Android release state

The regular CI Android artifact is green and downloadable, but it is not the production distribution artifact.

The repository contains the manual **TaskPilot Android signed release** workflow, which validates signing inputs, builds signed APK/AAB files, verifies signatures, supports Firebase client configuration injection, and can optionally upload an AAB to Google Play internal testing.

Not yet evidenced in this document:

- a successful production-signed Android workflow run
- installation on a physical Android device
- Google Play internal-track installation
- production Firebase/FCM delivery on a real device

Do not mark these complete until a signed workflow run and device/provider evidence are available.

## iOS release state

The exact release commit passes the unsigned iOS CI build and produces `taskpilot-ios-unsigned`.

Not yet evidenced in this document:

- a successful signed IPA workflow run
- TestFlight upload
- real-iPhone validation
- production APNs/FCM notification delivery

These remain externally blocked until Apple signing/provider credentials and a device are available.

## Workers and scheduled jobs

The codebase and CI cover Celery-backed invitation/notification/webhook behavior, retries, and failure handling. The hosted browser smoke also validates application behavior that emits notifications.

A direct operational check proving that the deployed Celery worker and exactly one Celery Beat scheduler are currently running has not been recorded here. Verify them in the hosting control plane before promotion.

## Observability

Prometheus/Grafana/Loki/Alertmanager configuration and validation are present in the repository and covered by CI.

Still required for a production claim:

- deploy/confirm the collectors against the hosted environment
- show real TaskPilot traffic in dashboards
- configure the intended alert receivers through secrets
- safely exercise representative readiness, 5xx, worker, and retry-exhaustion alerts

## Backup and restore

The backup/restore/rollback runbook exists, but no staging restore-drill evidence is recorded here yet.

Before production promotion, record:

- backup timestamp
- commit SHA
- Alembic revision
- restore target/environment
- restore outcome
- attachment-reference verification

Never run a destructive restore drill against valuable production data.

## Demo and portfolio presentation

The repository contains the Northstar demo seeder and portfolio-oriented data model. A polished public demo and final real screenshots should be captured only from a currently reachable seeded deployment.

README should link the live demo only after a fresh reachability/smoke re-check.

## Dependency state

There are no open pull requests at the time this evidence was prepared. The latest dependency consolidation already merged compatible updates. Known framework-breaking/incompatible upgrades should stay deferred unless they are security-relevant and validated through the full CI/release matrix.

## Licensing

No project license has been selected. This remains an explicit owner decision and should not be inferred from repository maturity.

## Promotion checklist

Before calling the release fully validated, complete or explicitly accept the remaining external items:

- rerun guarded deployment smoke immediately before promotion
- production-signed Android workflow and physical-device validation
- FCM real-device validation
- signed iOS/TestFlight validation when Apple credentials are available
- hosting-level Celery worker/Beat verification
- real observability traffic and alert delivery
- non-destructive backup/restore drill
- seeded public demo and final screenshots
- final license decision

