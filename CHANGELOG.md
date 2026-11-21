# Changelog

All notable TaskPilot portfolio changes should be tied to a Git revision and verified CI evidence. The unreleased section is not a production release announcement.

## Unreleased: portfolio/taskpilot-completion

### Added
- Backend idempotency metadata for supported offline task, subtask, checklist, and comment mutations (migration `0017_offline_idempotency`).
- Mobile conflict preview comparing current server values with preserved offline draft values.
- Portfolio case study, demo walkthrough, recording script, and evidence ledger.

### Changed
- Flutter sends a stable `Idempotency-Key` on the initial mutation and every replay.
- Offline queue operations are serialized, preserve FIFO order, persist drafts before the first network send, and checkpoint acknowledged mutations before processing later ones.
- Sync Center requires explicit conflict review before applying a local task edit.
- Workspace, project, board, and task-detail cache keys are scoped by account to avoid cross-account cache display.
- Concurrent mobile 401 responses share a single refresh-token rotation.
- Task activity summaries record changed fields and version transitions.
- Idempotent comment replay validation includes the original task ID.

### Validation
- Baseline `main` CI passed on `9ce715ad5cb9cfdded7d52e950ad3c4a0920644b`.
- Feature branch requires exact-SHA CI, emulator/physical-device walkthrough, and release evidence before promotion.

### Known limitations
- Physical Android/iOS, signed store distribution, external push, staging backup/restore, and final screenshots/recording remain manual gates.
- Licensing has not yet been selected.
