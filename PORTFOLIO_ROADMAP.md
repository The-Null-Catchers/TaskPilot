# TaskPilot portfolio roadmap

Baseline reviewed on November 17, 2026. Repository roadmap published on November 18, 2026.

This roadmap applies to this repository and follows the shared Null Catchers portfolio plan. Verify the documented state against the current code and runs before starting work.

**Estimated initial demo effort** 20–35 hours for a developer familiar with the project. The estimate excludes external reviews, store accounts, target environment setup, and later milestones.

## Project priorities

**Documented state** The web and Flutter apps include realtime updates, HTTP 409 conflict handling, offline queues, permissions, attachments, and notifications. Hosted and physical-device evidence and licensing remain open.

**P0 — Demo** Verify the Sync Center flow on a physical device after the two-browser realtime and stale-update checks.

**P1 — Validation and depth** Verify Android installation, session expiry, resync, and attachments. Check the worker and scheduler independently and rehearse staging restore. Treat app signing and push setup as separate from browser acceptance.

**P2 — Later** Add one integration based on a real user need, then improve onboarding and guest permissions from feedback.

**Acceptance criteria** Offline edits persist and sync once. Users can understand conflicts, unauthorized users cannot see the project, and release evidence records the revision, smoke results, and limits.

**Demo scenario** Assign a task → edit offline → resolve a conflict → see notification and audit history. [README](https://github.com/The-Null-Catchers/TaskPilot/blob/main/README.md), [Release Checklist](https://github.com/The-Null-Catchers/TaskPilot/blob/main/docs/RELEASE_CHECKLIST.md).

## Portfolio completion checkpoint (November 21, 2026)

The draft [PR #140](https://github.com/The-Null-Catchers/TaskPilot/pull/140) extends the existing baseline rather than replacing it. Its first implementation commits add backend idempotency metadata, stable mobile mutation IDs, ordered replay, explicit server/local conflict comparison, and account-scoped task caches. The migration revision identifier was shortened to fit PostgreSQL's Alembic version column.

**Still open:** exact-SHA CI confirmation, emulator/physical-device offline scenario, audit verification against both clients, genuine screenshots/recording, staging smoke and restore drill, and licensing. The earlier baseline CI success does not close these new acceptance gates.

The demo, engineering decisions, and evidence are documented in [PORTFOLIO_DEMO.md](docs/PORTFOLIO_DEMO.md), [CASE_STUDY.md](docs/CASE_STUDY.md), and [PORTFOLIO_EVIDENCE.md](docs/PORTFOLIO_EVIDENCE.md).

## Next milestones

[PR #136](https://github.com/The-Null-Catchers/TaskPilot/pull/136) verified that a card moves between two browsers without reload and that a stale edit gets HTTP 409 while its draft remains visible. [Browser run](https://github.com/The-Null-Catchers/TaskPilot/actions/runs/44304699815).

1. [ ] Open the same task on Android and web in a test deployment. Disconnect Android, edit locally, then edit on web. Confirm the mobile draft persists on reopening and shows a pending state.
2. [ ] Reconnect and resolve the conflict in Sync Center. Confirm both clients show the chosen version and audit history records one save.
3. [ ] Record browser, device, and deployment results with the tested revision. Run hosted smoke when its environment is available.

## Portfolio acceptance checklist

- [ ] Another person can reproduce the primary workflow from a clean checkout using the README and test credentials or fixtures.
- [ ] The demo tells one complete story with a defined user, problem, and saved result.
- [ ] Tests cover the main flow, an important failure, and access boundaries when multiple accounts are involved.
- [ ] Demo data is labeled synthetic and reproducible. Review screenshots and recordings for secrets and customer data.
- [ ] Include four to six real screenshots where appropriate, a 60–120 second recording, and working links. Identify the revision used for capture.
- [ ] The README describes implemented capabilities, setup, architecture, limits, tests, and the demo.
- [ ] A short case study explains two engineering decisions, a considered alternative, and how the system handles an actual failure.
- [ ] Release evidence records the commit SHA, CI, prerequisites, and limits. Performance data includes workload, hardware, and method.
- [ ] Licensing and contributor attribution are settled before distribution. Choose the license for each repository individually.

A hosted demo is optional. Code execution, server administration, and secret management can be demonstrated through a recording and a reproducible isolated environment. Keep public demo access scoped to the activities it needs.

## Implementation and follow-up

- Break P0 into tasks with expected behavior, acceptance criteria, and a suitable test.
- Verify existing functionality first. Update this plan when evidence tied to a commit or PR closes a milestone.
- Record the fixture source, the revision used for evidence, and the tested limits.
- Review the final diff and verify required checks for its exact SHA before merging. Follow branch protection.
- For documentation-only changes with no applicable workflow, verify content and links and record the checks actually performed.
- Tie performance, security, and readiness claims to supporting evidence.
