# Workspace Management

TaskPilot workspace collaboration is enforced by the FastAPI authorization layer. The web workspace settings screen exposes the same backend rules rather than relying on UI-only permission checks.

## Roles

- **Owner** can rename, archive, restore, delete, transfer ownership, manage non-owner members, and invite admins/members/guests.
- **Admin** can manage members and guests and invite members/guests. Admins cannot manage other admins or the owner.
- **Member** can collaborate in workspace projects but cannot manage workspace membership.
- **Guest** can only access projects where they have an explicit project membership.

## Invitations

Workspace managers create invitations for a specific email address and role. The API stores only a SHA-256 digest of the opaque invitation token. The raw token is returned once so the caller can construct a link such as `/invite/{token}`.

Invitations expire after seven days, can be cancelled by an authorized manager, and may only be previewed, accepted, or rejected by an authenticated user whose account email matches the invitation email. Expired invitations are excluded from the active invitation list.

Invitation email delivery is implemented through Celery when SMTP is configured. The validation token is stored only as a SHA-256 digest; an encrypted one-time delivery copy is retained for the worker and cleared after successful delivery. The web settings UI exposes delivery state and still provides the one-time secure link as a fallback when SMTP is unavailable.

## Workspace lifecycle

Owners can archive a workspace. Archiving invalidates outstanding invitations and blocks normal workspace, project, task, and WebSocket access until the owner restores it. Archived workspaces remain visible in workspace settings for members so the owner can restore or permanently delete them and non-owners can leave them.

Permanent deletion remains owner-only and cascades workspace-scoped data according to database foreign-key rules. Ownership must be transferred before an owner can leave a workspace.

## Audit events

The workspace routes currently write audit records for invitation creation/acceptance/rejection/cancellation, role changes, member removal/leave, ownership transfer, archive/restore, and workspace deletion. Audit metadata intentionally excludes passwords, cookies, access tokens, refresh tokens, and invitation tokens.
