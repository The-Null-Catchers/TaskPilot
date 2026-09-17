# Security

Please report security issues privately to the repository owners instead of opening a public issue containing exploit details or secrets.

## Development rules

- Never commit `.env`, signing keystores, access tokens, private keys, SMTP passwords, or cloud credentials.
- Rotate any credential that is accidentally exposed, even if the commit is later removed.
- Keep production CORS origins explicit.
- Use TLS for all production browser/mobile/API traffic.
- Use a strong random `JWT_SECRET` and separate secrets across environments.
- Review authorization for every new workspace/project/task-scoped endpoint.
- Validate upload MIME type and size before the attachment roadmap item is enabled.

## Current session design

Access JWTs are deliberately short-lived. Refresh tokens are opaque random values, stored only as hashes server-side, and rotated whenever used. Web refresh tokens are HttpOnly cookies; mobile tokens are stored with platform secure storage.
