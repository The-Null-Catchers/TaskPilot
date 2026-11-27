# TaskPilot portfolio demonstration

This is a reproducible **local synthetic-data** walkthrough, not a production test. It uses the Northstar Product Team seeder. Never use customer data or production credentials.

## Setup

Requirements: Docker with Compose, an available browser, and Flutter SDK plus an Android emulator or physical Android device for the mobile portion.

From a clean checkout of the intended revision:

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
curl -fsS http://localhost:8000/health/live
curl -fsS http://localhost:8000/health/ready
make demo
```

If the demo dataset already exists, `make demo` resets the synthetic demo workspace and users. It must **not** be run against production. Open http://localhost:3000. The seeder refuses APP_ENV=production.

## Demo users and roles

| User | Login | Workspace role |
| --- | --- | --- |
| Alex Morgan | alex.demo@taskpilot.local | Owner |
| Maya Chen | maya.demo@taskpilot.local | Admin |
| Sam Rivera | sam.demo@taskpilot.local | Member |

The default **local-only synthetic demo** password is `TaskPilot-Demo-2026!`. Set `TASKPILOT_DEMO_PASSWORD` in the backend environment to change it. Do not reuse this password for any real account.

## Web + realtime walkthrough

1. Sign in as Alex in browser window A. Open **Northstar Product Team** and the **Mobile App 2.0** project.
2. Open the Kanban board and create a task named **Verify portfolio offline sync** in **To Do**. Note its identifier and current version.
3. Assign Maya to the new task.
4. Open a separate browser profile/window B and sign in as Maya. Open the same board.
5. Move the task from **To Do** to **In Progress** in A. Confirm B updates without a refresh.
6. Add a comment in A and mention Maya using the task UI. Confirm Maya sees the notification and activity entry.
7. Open the task in both browser sessions. Save an edit in A, then attempt to save the stale draft in B. Confirm HTTP 409 and preservation of B's draft.
8. Visit the project analytics view and inspect the task counts and activity.

## Native Android + offline conflict walkthrough

```bash
cd mobile
flutter create . --platforms=android --project-name=taskpilot_mobile --org=dev.taskpilot
flutter pub get
flutter run --dart-define=API_URL=http://10.0.2.2:8000
```

The emulator's `10.0.2.2` address reaches the host loopback API. For a physical device, replace the API URL with an address reachable from that device; use a secure test environment and do not expose the development API publicly.

1. Sign in as Alex on Android and open the same task from the **Mobile App 2.0** board.
2. Disable Android networking, edit the task title or description, and save. Confirm the app reports a locally queued change.
3. Fully close and reopen the mobile app while still offline. Verify the local draft and queue survive restart.
4. In browser A, edit the same task and save a different title.
5. Re-enable Android networking and open **Sync Center**. Tap **Sync now**. Confirm the queued edit becomes **Needs review** after HTTP 409.
6. Tap **Review conflict** and compare the current server values with the saved local draft.
7. Choose **Apply my changes** or **Keep server version**. If the server changed again during review, reopen the comparison rather than overwriting.
8. Confirm the queue clears for the resolved mutation. Refresh both clients and verify they show the chosen final version.
9. Open task activity history and verify the number of actual updates matches the saves (no duplicate replay entries).
10. Repeat with expired session, temporary server failure, account switching, and two queued edits. Record results separately.

**Important:** These are acceptance instructions. A checked-off step requires observed results from a real emulator/device and server, not just a passing unit test.

## 90-second recording script

| Time | Interaction | Narration cue |
| --- | --- | --- |
| 0–10s | Open seeded dashboard and Mobile App 2.0 | "TaskPilot connects project planning and task ownership." |
| 10–25s | Create task and assign Maya | "Teams can create, assign, and track work." |
| 25–40s | Move Kanban card and show second browser updating | "Changes appear in realtime across collaborators." |
| 40–50s | Comment, mention, and show notification | "Collaboration stays attached to the task." |
| 50–65s | Disconnect Android, edit, and show pending queue | "Mobile drafts remain available without connectivity." |
| 65–80s | Make a conflicting web edit, reconnect, open Sync Center | "A newer server version is never silently overwritten." |
| 80–90s | Compare versions, choose result, show history and analytics | "The user resolves the conflict and can audit the result." |

Record only real running application screens. Mask access tokens, private addresses, and any non-synthetic information. Store approved screenshots in `docs/images/portfolio/` and record the capture commit in `PORTFOLIO_EVIDENCE.md`.

## Verification commands

Follow [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) for the full matrix. At minimum:

```bash
cd backend && ruff check app tests && pytest -q
cd ../web && npm ci && npm run lint && npm test && npm run typecheck && npm run build
cd ../mobile && flutter pub get && flutter analyze && flutter test
```

For browser E2E, run `npm run e2e` from `web/` with the required test services. For mobile builds, run the Android APK/AAB commands in the release checklist. Do not treat a locally scripted walkthrough as validated until it is actually executed.
