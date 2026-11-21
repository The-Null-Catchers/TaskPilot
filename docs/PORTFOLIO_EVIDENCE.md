# TaskPilot portfolio evidence ledger

This ledger separates **observed CI results** from implementation work and unverified acceptance scenarios.

## Revisions

- Starting revision on main: `9ce715ad5cb9cfdded7d52e950ad3c4a0920644b`.
- Feature branch: `portfolio/taskpilot-completion`.
- Initial feature-branch checkpoint: `5bee1ab9594713907fe9604b074bd632bcc4e6c5`.
- Mobile sync/queue implementation checkpoint: `b953e23597a6ac193ac3b7cebabdb0cb1b11b8cc`.
- Final release-candidate SHA: **not assigned**. Update this after all code/docs changes and successful exact-SHA CI.

## Verified historical evidence

| Revision | Evidence | Result | Scope |
| --- | --- | --- | --- |
| `9ce715ad5cb9cfdded7d52e950ad3c4a0920644b` | [TaskPilot CI #44529059942](https://github.com/The-Null-Catchers/TaskPilot/actions/runs/44529059942) | Success | Existing baseline CI; not the feature branch |
| `5e57197ed66f2abd729f6c7c07c4ca6f5f7d5d3d` | [TaskPilot CI #44304699815](https://github.com/The-Null-Catchers/TaskPilot/actions/runs/44304699815) | Success | PR #136 browser collaboration / stale edit regression |

The historical CI jobs include backend Ruff/Pytest/migrations, web lint/Vitest/typecheck/build, browser E2E, Flutter analyze/tests and Android builds, unsigned iOS build, and production Compose/Docker build. These successes do **not** transfer automatically to later commits.

## Current feature-branch evidence

- [PR #140](https://github.com/The-Null-Catchers/TaskPilot/pull/140) is a draft against `main`. Do not merge until all gates pass.
- [TaskPilot CI run #44916081158](https://github.com/The-Null-Catchers/TaskPilot/actions/runs/44916081158) for `b953e23597a6ac193ac3b7cebabdb0cb1b11b8cc`: backend migration and browser E2E setup **failed** because the new Alembic revision identifier exceeded PostgreSQL's 32-character version column. Web lint/test/typecheck/build passed. Do not use this run as a passing release gate.
- Fix commit: `1ba5d2386f0749207bf817a2240394a359091102` shortens the Alembic revision ID. [Follow-up CI #44916220188](https://github.com/The-Null-Catchers/TaskPilot/actions/runs/44916220188) was in progress when this ledger was drafted. Recheck before claiming success.
- The new backend migration revision is `0017_offline_idempotency` (shortened after a CI failure caused by the original 33-character revision ID). Migration upgrade/downgrade must be reverified on the final SHA.

## Pending acceptance matrix

| Requirement | Evidence still required |
| --- | --- |
| Durable offline edit across process restart | Flutter test plus emulator/device restart |
| FIFO replay and idempotent retry | Flutter + backend tests, exact SHA CI |
| HTTP 409 conflict and preserved draft | Mobile test and Android/web E2E |
| Server/local comparison and guarded resolution | Mobile widget/controller test and Android E2E |
| Account switching and local cache isolation | Mobile tests and device account-switch walkthrough |
| Audit history records one actual update | Backend test and demo verification |
| Two browser realtime collaboration | Existing PR #136 evidence; rerun on final SHA |
| Android APK/AAB and iOS unsigned build | Final SHA CI |
| Staging smoke, push providers, restore drill | Environment-specific manual validation |
| Screenshots (4–6) and 60–120s recording | Genuine running app capture; not yet available |
| License and contributor attribution | Maintainer decision |

## Screenshots and recording

No new screenshots or recording are claimed for the feature branch at this checkpoint. Historical Playwright artifacts may contain genuine browser screenshots but must be inspected, matched to their SHA, and curated before publication. Do not invent images or mark this gate complete.

## Security and release limitations

Offline SharedPreferences are account-partitioned but not a substitute for an encrypted local database. Backend idempotency covers supported endpoints, not arbitrary operations. Physical Android/iOS push, signed store distribution, restore drills, and production deployment are not validated by this evidence ledger.

Update this file with links to exact successful checks and screenshots after they exist.
