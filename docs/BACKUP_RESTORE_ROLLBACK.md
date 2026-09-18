# Backup, restore, and rollback runbook

This runbook is for TaskPilot's production Compose deployment. Adapt the same principles when PostgreSQL or object storage is managed by a cloud provider.

A backup is not considered verified until it has been restored successfully in a non-production environment.

## What must be backed up

TaskPilot's durable state consists of:

- PostgreSQL: users, workspaces, projects, tasks, comments, notification state, integrations, audit/activity data, attachment metadata, and all other application records.
- S3-compatible object storage: attachment objects and generated thumbnails.
- Deployment configuration in an approved secret manager: production environment variables, TLS/reverse-proxy configuration, push/email provider credentials, and signing configuration.

Redis is used for Celery, realtime, and rate limiting. It is not the source of truth for application records and should not replace PostgreSQL/object-storage backups.

## Pre-release backup

Before a production release that contains Alembic migrations, take a database backup and record the release metadata.

From the repository root:

```bash
mkdir -p backups
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

git rev-parse HEAD | tee "backups/release-${STAMP}.commit"

docker compose --env-file .env -f docker-compose.prod.yml exec -T postgres \
  sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "backups/taskpilot-${STAMP}.dump"

docker compose --env-file .env -f docker-compose.prod.yml exec -T backend \
  alembic current \
  | tee "backups/taskpilot-${STAMP}.alembic.txt"
```

Verify that the dump is non-empty before continuing:

```bash
test -s "backups/taskpilot-${STAMP}.dump"
```

Keep backups outside the application host as well. A disk failure that removes both production data and its backup is not a recovery plan.

## Object-storage backup

For the bundled MinIO deployment, install the MinIO Client (`mc`) on an administrative machine that can reach the loopback-bound MinIO endpoint through an approved tunnel or local shell.

Example:

```bash
set -a
. ./.env
set +a

mc alias set taskpilot-local \
  "http://127.0.0.1:${MINIO_API_PORT:-9000}" \
  "$MINIO_ROOT_USER" \
  "$MINIO_ROOT_PASSWORD"

mkdir -p "backups/objects-${STAMP}"
mc mirror --overwrite \
  "taskpilot-local/${STORAGE_BUCKET:-taskpilot}" \
  "backups/objects-${STAMP}/"
```

For managed S3-compatible storage, prefer provider-native versioning/snapshots or a cross-account/cross-region backup policy. Do not rely on the application host as the only copy.

## PostgreSQL restore drill

Perform restore drills against a disposable environment first.

1. Start PostgreSQL and Redis for the target environment.
2. Stop TaskPilot API/web/worker/beat processes so they cannot write while the restore is in progress.
3. Restore the database dump.
4. Restore the corresponding object-storage backup.
5. start TaskPilot and validate readiness plus representative workflows.

For the Compose stack:

```bash
docker compose --env-file .env -f docker-compose.prod.yml stop backend worker beat web

cat backups/taskpilot-YYYYMMDDTHHMMSSZ.dump | \
  docker compose --env-file .env -f docker-compose.prod.yml exec -T postgres \
  sh -lc 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

A restore of a dump from an older release may leave the schema at that release's Alembic revision. Check it before starting the current application:

```bash
docker compose --env-file .env -f docker-compose.prod.yml run --rm backend \
  alembic current
```

Only run `alembic upgrade head` after confirming that the current application version is intended to operate on the restored data.

## Object-storage restore

Using the MinIO Client alias configured above:

```bash
mc mirror --overwrite --remove \
  "backups/objects-YYYYMMDDTHHMMSSZ/" \
  "taskpilot-local/${STORAGE_BUCKET:-taskpilot}"
```

The `--remove` option makes the destination match the backup exactly. Use it only when you are intentionally restoring the entire bucket.

After restoring, validate at least one attachment download through TaskPilot rather than checking only the bucket contents.

## Release rollback decision

A code rollback and a data restore are different operations.

### Code-only rollback

Use a code-only rollback when:

- the release has no incompatible database migration, or
- the migration is backward-compatible with the previous application revision.

Procedure:

1. identify the last known-good Git commit/image;
2. verify the database schema is compatible with it;
3. deploy that code revision;
4. verify `/health/live` and `/health/ready`;
5. run authentication, board/task read/write, realtime, worker, and attachment smoke checks.

Do not downgrade the database automatically merely because application code is being rolled back.

### Migration rollback

Only run an Alembic downgrade when the specific migration's downgrade path is known to be safe for the current production data.

Before a downgrade:

```bash
docker compose --env-file .env -f docker-compose.prod.yml run --rm backend \
  alembic current

docker compose --env-file .env -f docker-compose.prod.yml run --rm backend \
  alembic history --verbose
```

Then stop writers and downgrade to the explicitly reviewed revision:

```bash
docker compose --env-file .env -f docker-compose.prod.yml stop backend worker beat web

docker compose --env-file .env -f docker-compose.prod.yml run --rm backend \
  alembic downgrade <reviewed_revision>
```

Never use `alembic downgrade base` as a production rollback strategy.

Some downgrades can become impossible after new valid data is created. For example, restoring a stricter uniqueness constraint can fail if records created after an upgrade legitimately violate that older constraint. In that situation, prefer a forward fix or restore the pre-release database backup after an explicit incident decision.

## Full data restore

Use a full data restore only when the production data itself must be returned to the backup point.

This discards writes made after the backup. Before doing it:

- identify the incident window;
- preserve a forensic/current backup first;
- explicitly decide that post-backup writes may be lost;
- communicate the recovery point to operators/stakeholders.

Then stop writers, restore PostgreSQL and object storage from the same recovery point, deploy the matching compatible application revision, and validate.

## Post-restore validation

At minimum verify:

- `GET /health/live` returns success;
- `GET /health/ready` confirms PostgreSQL and Redis;
- an existing user can sign in and refresh a session;
- a workspace/project board loads;
- a task can be created, edited, moved, archived, and restored;
- realtime updates reach a second session;
- an existing attachment can obtain a signed URL and download;
- a new attachment can be uploaded;
- a Celery-backed notification/webhook job completes or retries visibly;
- audit/activity history is present;
- production logs contain request/job correlation data without secrets.

## Backup retention

Choose retention according to deployment needs, but keep more than one recovery point. A typical small deployment may retain:

- several recent daily database backups;
- weekly backups for a longer window;
- object-storage versioning or matching periodic mirrors;
- a pre-release backup for every migration-bearing release until that release is proven stable.

Encrypt backups at rest and restrict access to operators who already have production-data privileges.

## Recovery documentation

For every production incident/restore, record:

- affected release commit;
- Alembic revision before and after recovery;
- database/object backup timestamps;
- recovery point and estimated data-loss window;
- commands/actions used;
- validation results;
- follow-up action needed to prevent recurrence.

Do not place passwords, tokens, private keys, or raw provider credentials in incident notes.
