# ADR-002: Authentication Provider — Clerk

**Status:** Accepted

**Date:** 2025-01-20

## Context

The modernized Ashta Chamma application requires user authentication to support
persistent profiles, leaderboards, and multiplayer rooms tied to real accounts.
We need a solution that handles:

- User registration and login (email/password + social OAuth).
- JWT issuance for API and WebSocket authorization.
- Account management (password reset, email verification, MFA).
- Secure integration with FastAPI and the React SPA.

Options evaluated:

| Option | Pros | Cons |
|---|---|---|
| AWS Cognito | Native AWS integration; no extra vendor | Complex setup; poor developer experience; React SDK is clunky |
| Auth0 | Mature product; good DX | Expensive at scale; extra external dependency |
| Clerk (chosen) | Excellent React/Next.js SDKs; RS256 JWTs; built-in UI components; generous free tier | External SaaS dependency; vendor lock-in risk |
| Custom auth (FastAPI + bcrypt) | Full control; no vendor | High maintenance; security risk; no MFA out of the box |

## Decision

We will use **Clerk** as the external authentication provider.

- The React SPA integrates via `@clerk/clerk-react` for auth UI components and
  session management.
- The FastAPI backend validates JWTs using Clerk's JWKS endpoint
  (`https://api.clerk.dev/v1/jwks`) with RS256 signature verification.
- JWKS keys are cached in Redis with a 15-minute TTL to eliminate per-request
  external calls.
- Clerk user IDs (`clerk_id`) are stored in the `users` PostgreSQL table as a
  unique key linking Clerk identity to application profiles.
- WebSocket connections are authenticated by passing the JWT as a query parameter
  on the WSS upgrade request; the server validates once at connect time.

## Consequences

### Positive

- Zero-effort auth UI: Clerk provides pre-built, accessible login/signup/profile
  components that match the SPA theme.
- RS256 JWTs with standard claims enable stateless backend validation — no
  session store required.
- MFA, social login (Google, GitHub), and email verification are available
  with no additional implementation.
- Clerk's generous free tier (10,000 MAU) covers the expected initial load.

### Negative

- Application availability is partially dependent on Clerk's uptime. If Clerk is
  down, new logins fail (existing sessions with cached JWTs continue to work for
  the cache TTL).
- Vendor lock-in: migrating away from Clerk requires updating auth flows in both
  client and backend.
- JWKS caching must be managed carefully; stale keys after rotation could cause
  transient 401 errors.

### Risks

- **Key rotation gap**: If Clerk rotates JWKS keys and the Redis cache still holds
  old keys, a 15-minute window of failed validations occurs.
  Mitigation: On JWT validation failure, force-refresh JWKS from Clerk before
  returning 401, then retry.
- **Clerk service outage**: Mitigated by Redis JWT claim caching so in-progress
  games survive short outages.
