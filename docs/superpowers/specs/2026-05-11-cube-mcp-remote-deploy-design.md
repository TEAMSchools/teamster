# Cube MCP Remote Deployment Design

**Issue:** [#3879](https://github.com/TEAMSchools/teamster/issues/3879)
**Date:** 2026-05-11 (revised 2026-05-14) **Status:** Approved — ready for
implementation plan

## Background

The data team accesses the Cube semantic layer via a custom MCP server
([`scripts/cube_rest_mcp.py`](../../../scripts/cube_rest_mcp.py)) running
locally in the VS Code Codespace. It wraps Cube Cloud's REST API and mints
per-request JWTs whose `email` claim drives Cube's row-level security context —
each user's `cube-*` Workspace group memberships flow through, scoping query
results appropriately.

The goal is to deploy this same server as a remote MCP service so non-technical
users (directors, school leaders) can access it from `claude.ai` without any
local setup. Every user authenticates with their Google Workspace account; the
existing per-user security model carries over unchanged.

### Option considered and set aside

The fastest path would be pointing users at Cube's native `/api/mcp` endpoint.
Per [Cube's docs](https://cube.dev/docs/product/apis-integrations/mcp-server),
that server is a thin wrapper around Cube's
[Chat API](https://cube.dev/docs/product/apis-integrations/embed-apis/chat-api)
— it exposes a single chat tool that delegates to Cube's own AI agent rather
than giving Claude direct access to the semantic layer. Ruled out because:

1. **Wrong AI does the reasoning.** Claude becomes a relay to Cube's AI agent
   rather than reasoning over the data model itself. The MCP tool calls forward
   natural-language questions to Cube and stream back agent-generated responses.
   Claude's value as the orchestrator (planning multi-step analyses, combining
   Cube results with other tools, applying repo-specific conventions from
   `CLAUDE.md`) is bypassed.
2. **No primitive access.** The custom server exposes `meta`, `load`, and `sql`
   tools that let Claude build queries directly and iterate. Cube's native MCP
   gives no equivalent — the agent is opaque.
3. **LLM guidance.**
   [`scripts/cube_rest_mcp.py`](../../../scripts/cube_rest_mcp.py) ships with
   tighter tool descriptions and query-format guardrails tuned for our views and
   access policies, which Cube's generic chat tool can't carry.

The custom server is worth the deployment work.

## Goal

Deploy the existing Cube MCP server as a Cloud Run service reachable as a remote
MCP server via OAuth. Each user authenticates with their Google Workspace
account; their real email and `cube-*` group memberships drive the Cube security
context per request. The local stdio path (Codespace, Desktop) is unchanged.

## Architecture

```text
claude.ai ──OAuth 2.1 + DCR──▶ WorkOS AuthKit ──OIDC──▶ Google Workspace
   │
   │  Bearer JWT (AuthKit-signed, email claim)
   ▼
Cloud Run: src/cube/mcp/server.py (streamable-http transport)
   1. Validate AuthKit JWT via JWKS
   2. Extract user email from verified claims
   3. Mint Cube JWT signed with CUBE_API_SECRET, email in payload
   ▼
Cube Cloud REST API
   contextToGroups(email) ──▶ Google Directory API
                          ──▶ user's actual cube-* groups
   ▼
   Returns rows scoped to that user's real group memberships
```

**Two-token model.** The OAuth bridge (WorkOS AuthKit) authenticates the _user_
(Google Workspace identity). The MCP server validates the AuthKit token, then
mints a separate _Cube_ JWT per request using the verified email as the security
context. The Cube signing secret never leaves the Cloud Run service.

**No shared identity.** Every request carries the real user's email. Cube Cloud
audit logs show per-director attribution. Access defaults to deny if a user has
no `cube-*` groups — correct behavior.

**Groups resolved by Directory API.** The
[src/cube/cube.js](../../../src/cube/cube.js) `contextToGroups` function calls
the Google Directory API with the user's email and returns their `cube-*` group
memberships. Workspace is the single source of truth for group membership; no
parallel mapping file in this repo.

## Section 1: Code changes to the MCP server

### 1a. File reorganization

The MCP server file moves out of `scripts/` because it is no longer a standalone
executable — it's a deployable service with a Dockerfile and production runtime
config.

| From                       | To                        |
| -------------------------- | ------------------------- |
| `scripts/cube_rest_mcp.py` | `src/cube/mcp/server.py`  |
| (new)                      | `src/cube/mcp/Dockerfile` |
| (new)                      | `src/cube/mcp/CLAUDE.md`  |

The stdio launcher
[`scripts/cube-rest-mcp-launch.sh`](../../../scripts/cube-rest-mcp-launch.sh)
stays in `scripts/` (it _is_ a script) and is updated to invoke
`src/cube/mcp/server.py` at its new path.

The [`scripts/CLAUDE.md`](../../../scripts/CLAUDE.md) script catalog entry is
updated to point at the new location.

### 1b. HTTP transport mode

Add a `TRANSPORT` env var (default: `stdio`). When set to `http`, the server
calls:

```python
mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
```

Port 8080 is what Cloud Run expects. The stdio path is unchanged when
`TRANSPORT` is unset or `stdio`.

### 1c. OAuth resource-server middleware

Add an `AUTHKIT_DOMAIN` env var. When set, the server installs FastMCP auth
middleware that:

1. Fetches the AuthKit JWKS from `https://<AUTHKIT_DOMAIN>/oauth2/jwks` on
   startup (cached).
2. On every MCP request, validates the bearer token's signature, issuer
   (`https://<AUTHKIT_DOMAIN>`), audience, and expiry.
3. Extracts the `email` claim into request-local context.
4. Rejects requests with no/invalid token with a `401 WWW-Authenticate` response
   that points clients at the OAuth metadata endpoint.

The server also exposes OAuth metadata endpoints required by the MCP spec:

- `/.well-known/oauth-protected-resource` — points at the AuthKit AS (RFC 9728
  protected-resource metadata)
- `/.well-known/oauth-authorization-server` — proxies/redirects to AuthKit's
  metadata (RFC 8414); enables DCR client discovery

These endpoints are how `claude.ai` discovers the AS and registers itself as an
OAuth client.

### 1d. Email resolution in HTTP mode

In HTTP mode, `_get_user_email` reads the email from verified token claims in
request-local context. The existing elicit / cache / `CUBE_USER_EMAIL` env-var
path is bypassed entirely on the HTTP path. The stdio path retains its existing
behavior unchanged.

## Section 2: OAuth Authorization Server — WorkOS AuthKit

WorkOS AuthKit handles the OAuth 2.1 + DCR layer. Configuration:

| Setting                     | Value                                                        |
| --------------------------- | ------------------------------------------------------------ |
| Identity provider           | Google Workspace (OIDC)                                      |
| Domain restriction          | `hd=apps.teamschools.org` — rejects personal Gmail accounts  |
| Dynamic Client Registration | Enabled (required for `claude.ai` connector flow)            |
| Access token lifetime       | 1 hour (default)                                             |
| Refresh token lifetime      | 30 days (default)                                            |
| Token format                | JWT, RS256, JWKS at `https://<domain>/oauth2/jwks`           |
| Required claim in token     | `email` — the user's `@apps.teamschools.org` Workspace email |

**Why WorkOS:**

- Published reference templates for remote MCP servers — paved path for the
  exact scenario.
- Google Workspace SSO with domain restriction is a native config field, not a
  custom integration.
- Free tier (1M MAU) covers the network indefinitely at our scale.
- Resource-server code on our side is plain JWKS validation (~30 lines).
- No coupling to staff IT-managed identity systems; setup is self-service by the
  data team.

### Documented alternative: Okta Workforce

Okta Workforce Identity (the existing staff SSO) is a drop-in replacement for
WorkOS AuthKit at the auth layer. Switching would be a config change
(`AUTHKIT_DOMAIN` and metadata endpoints repoint at Okta's custom authorization
server), not a code change. The case to migrate:

- **Pro:** Unified SSO — directors already have an Okta session, so connector
  setup becomes one-click (no second Google sign-in flow).
- **Pro:** No external vendor.
- **Con:** Requires IT-team coordination to enable a custom authorization
  server, configure DCR policy (typically disabled by default in Okta tenants),
  and verify the `email` claim carries the Workspace email.
- **Con:** No MCP-specific reference implementations on Okta — pattern would be
  invented.

WorkOS is chosen for the initial deploy because it avoids IT coordination time.
Migrating to Okta later is a viable future state if the dual sign-in flow proves
friction in practice.

## Section 3: Cube-side prerequisites

Already covered by the team (per issue discussion):

- Google Directory API enabled at the GCP project level.
- Service account with domain-wide delegation; `admin.directory.group.readonly`
  scope authorized in Google Workspace admin console.
- Service account credential configured in Cube Cloud per Cube's docs so
  `contextToGroups` can call the Directory API.

The previously-proposed [src/cube/cube.js](../../../src/cube/cube.js) JWT-groups
pass-through fix (mentioned in the issue comment) is **no longer needed** — with
Directory API working, `contextToGroups` resolves groups from Workspace
directly.

The previously-proposed `CUBE_JWT_GROUPS` config var is also dropped — no shared
identity, no group claims embedded in minted JWTs.

CORS is a non-issue: Cube's REST API allows all origins by default; the repo's
[src/cube/cube.js](../../../src/cube/cube.js) has no override; and Cloud Run →
Cube traffic is server-to-server (no browser, no preflight).

## Section 4: Dockerfile and Cloud Run

### `src/cube/mcp/Dockerfile`

Minimal Python 3.13 image (`python:3.13-slim`). Copies `src/cube/mcp/server.py`,
installs uv, uses `uv run` to execute — inline PEP 723 dependencies (`mcp`,
`httpx`, `pyjwt`, plus new `authlib` or equivalent for JWKS validation)
self-install on container start.

### Cloud Run service config

| Setting           | Value                                                                                        |
| ----------------- | -------------------------------------------------------------------------------------------- |
| Region            | `us-central1` (matches GKE cluster)                                                          |
| Min instances     | 0 (scales to zero — no cost between sessions)                                                |
| Memory            | 256 MB                                                                                       |
| CPU               | 0.25 vCPU                                                                                    |
| Port              | 8080                                                                                         |
| Ingress           | All (Claude.ai is the client; OAuth enforces auth at MCP layer)                              |
| `TRANSPORT`       | `http`                                                                                       |
| `CUBE_REST_URL`   | `https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1`                     |
| `AUTHKIT_DOMAIN`  | `<workspace>.authkit.app` (from WorkOS dashboard)                                            |
| `CUBE_API_SECRET` | Cloud Run secret reference (from 1Password: `op://Data Team/Cube Cloud REST API/credential`) |

`CUBE_USER_EMAIL` and `CUBE_JWT_GROUPS` are **not** set — HTTP mode reads email
from the verified OAuth token; groups resolve via Directory API.

## Section 5: GitHub Actions deployment

New `.github/workflows/deploy-cube-mcp.yaml`, triggered on push to `main` when
`src/cube/mcp/**` changes.

Steps:

1. Authenticate to GCP via Workload Identity Federation.
2. Build and push image to Artifact Registry
   (`us-central1-docker.pkg.dev/teamster-332318/cube-mcp/cube-mcp:<sha>`).
3. `gcloud run deploy` with the new image and config variables.

Follows the same GCP auth pattern as `dagster-cloud-deploy.yaml`.

**Engineer prerequisite to verify:** Does the existing GCP service account used
in GitHub Actions have Cloud Run deploy permissions (`roles/run.admin`,
`roles/iam.serviceAccountUser`)? If not, those roles must be granted before the
workflow can be written.

## Section 6: Claude.ai Custom Connector setup

One-time setup by an admin (data team) at the Claude.ai workspace level:

1. `claude.ai` → **Settings** → **Connectors** → **Add custom connector**.
2. Paste the Cloud Run service URL
   (`https://<service>-<hash>.us-central1.run.app/mcp`).
3. Claude.ai fetches OAuth metadata from the MCP server, discovers WorkOS
   AuthKit as the AS, registers itself via DCR.
4. Connector appears in the workspace; all directors see it in their tools.

The connector configuration is pushed to all workspace members automatically —
no per-user installation step.

## Section 7: End-user (director) workflow

First-time use:

1. Open `claude.ai`. The "Cube" connector is visible in the tools menu.
2. Click **Connect**. A browser tab opens to WorkOS AuthKit.
3. AuthKit displays a **"Sign in with Google"** prompt (or auto-redirects if
   Google is the only configured IdP).
4. Director picks their `@apps.teamschools.org` Workspace account on Google's
   consent screen. The `hd=apps.teamschools.org` restriction rejects personal
   Gmail accounts.
5. Brief AuthKit consent screen — one click.
6. Redirect back to `claude.ai`. Connector status: **Connected**.
7. Director asks a question. Claude picks a Cube tool. The MCP server validates
   the AuthKit token, mints the per-request Cube JWT with the director's email,
   queries Cube with their real group memberships.

Subsequent sessions: refresh tokens keep the connection alive silently. The
director sees no auth prompts until the refresh fails (token revoked in WorkOS
or Workspace), at which point one Connect click re-establishes the session.

## Section 8: Director-facing documentation

New page: `docs/guides/claude-cube-connector.md`.

**Audience:** directors and other non-technical staff using Claude.ai.

**Contents:**

- Two-screenshot walkthrough (Connect button → Google sign-in → "Connected"
  status).
- Example questions to try (aggregate-only — uses `*_summary` views).
- Troubleshooting block:
  - "Access denied" / empty results → email the data team to add your account to
    the appropriate `cube-*` Workspace group.
  - "Disconnected" status → click Connect again.

**PII discipline:** screenshots redact any student data with the placeholder
labels documented in the project CLAUDE.md (`Student A`, etc.). The page is
registered in `mkdocs.yml` under **Guides**.

## Section 9: Local stdio path — unchanged

Data team continues running the MCP server via
[scripts/cube-rest-mcp-launch.sh](../../../scripts/cube-rest-mcp-launch.sh) in
Codespace. The launcher invokes `src/cube/mcp/server.py` at its new path;
`TRANSPORT` and `AUTHKIT_DOMAIN` are not set, so the server runs stdio mode with
the existing `CUBE_USER_EMAIL` resolution (env / cache / elicit).

The [scripts/CLAUDE.md](../../../scripts/CLAUDE.md) and
[scripts/cube-rest-mcp-launch.sh](../../../scripts/cube-rest-mcp-launch.sh)
references are updated to the new server path.

## Section 10: Rollout sequence

1. Engineer verifies GCP service-account permissions for Cloud Run deploy.
2. WorkOS tenant set up; Google Workspace OIDC configured with domain
   restriction.
3. File reorganization (`scripts/cube_rest_mcp.py` → `src/cube/mcp/server.py`)
   on this branch.
4. HTTP transport + AuthKit middleware added to `src/cube/mcp/server.py`.
5. Dockerfile written and tested locally (stdio path unchanged; HTTP path
   smoke-tested with a manually-minted AuthKit token).
6. Manual Cloud Run deploy for end-to-end smoke test.
7. GitHub Actions workflow written and validated.
8. Director-facing docs page drafted and published.
9. Claude.ai Custom Connector created pointing at Cloud Run service URL.
10. Smoke test with one director account before broader rollout.
