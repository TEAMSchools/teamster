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

**Groups resolved by Directory API.** Cube's
[`contextToGroups`](https://cube.dev/docs/reference/configuration/config#contexttogroups)
hook (a per-request callback Cube exposes for dynamic group resolution) is
implemented in [src/cube/cube.js](../../../src/cube/cube.js) to call the Google
Admin SDK Directory API with the user's email and return their `cube-*` group
memberships. Workspace is the single source of truth for group membership; no
parallel mapping file in this repo. (Directory API integration is a repo-local
implementation of Cube's hook, not a Cube-documented feature.)

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

Add an `AUTHKIT_DOMAIN` env var. When set, the server configures FastMCP as an
OAuth resource server using the SDK's `TokenVerifier` + `AuthSettings` (per the
[MCP Python SDK README](https://github.com/modelcontextprotocol/python-sdk)):

1. Fetches the AuthKit JWKS from `https://<AUTHKIT_DOMAIN>/oauth2/jwks` on
   startup (cached).
2. On every MCP request, validates the bearer token's signature, issuer
   (`https://<AUTHKIT_DOMAIN>`), audience, and expiry.
3. Extracts the `email` claim into request-local context.
4. Rejects requests with no/invalid token with a `401 WWW-Authenticate` response
   that points clients at the OAuth metadata endpoint.

The server also exposes the OAuth metadata endpoint required by the MCP spec
(MCP 2025-06-18 authorization section):

- `/.well-known/oauth-protected-resource` — points at the AuthKit AS (RFC 9728
  protected-resource metadata; **MUST** per the MCP spec)

AuthKit hosts its own `/.well-known/oauth-authorization-server` (RFC 8414) and
DCR endpoint (RFC 7591 — **SHOULD** per the MCP spec); clients follow the
protected-resource metadata to discover the AS and register themselves.

These endpoints are how `claude.ai` discovers the AS and registers itself as an
OAuth client.

### 1d. Email resolution in HTTP mode

In HTTP mode, `_get_user_email` reads the email from verified token claims in
request-local context. The existing elicit / cache / `CUBE_USER_EMAIL` env-var
path is bypassed entirely on the HTTP path. The stdio path retains its existing
behavior unchanged.

## Section 2: OAuth Authorization Server — WorkOS AuthKit

WorkOS AuthKit handles the OAuth 2.1 + DCR layer. Configuration:

| Setting                     | Value                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------ |
| Identity provider           | Google Workspace (OIDC)                                                                          |
| Domain restriction          | Configured via the WorkOS Google connection to limit sign-ins to `apps.teamschools.org` accounts |
| Dynamic Client Registration | Enabled in the WorkOS tenant (required for `claude.ai` connector flow per MCP spec)              |
| Access token lifetime       | 1 hour (configured in tenant)                                                                    |
| Refresh token lifetime      | 30 days (configured in tenant)                                                                   |
| Token format                | JWT, RS256, JWKS at `https://<domain>/oauth2/jwks`                                               |
| Required claim in token     | `email` — the user's `@apps.teamschools.org` Workspace email                                     |

**Why WorkOS:**

- Published [MCP integration guide](https://workos.com/docs/authkit/mcp) — paved
  path for the exact scenario.
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

## Section 4: GCP project setup

The Cloud Run service is deployed to a **new GCP project**, separate from
`teamster-332318` (which hosts BigQuery, Dagster's GKE cluster, and the
warehouse-side service accounts). Reasons to isolate:

- The MCP service is public-facing (reachable over the internet, gated only by
  OAuth) and federates with external identity (WorkOS). Keeping it out of the
  warehouse project contains blast radius — a compromise of the service cannot
  pivot into BigQuery or Dagster credentials.
- The Cloud Run service has no IAM dependency on `teamster-332318`: it talks to
  Cube Cloud (external) and WorkOS (external), so no cross-project IAM is needed
  for the runtime.
- Cleaner audit log / cost attribution for the public-facing surface.

Proposed project ID: **`teamster-mcp`** (final name subject to org naming
convention).

### One-time setup

```bash
# 1. Create project, link billing
gcloud projects create teamster-mcp --name="Teamster MCP Services"
gcloud beta billing projects link teamster-mcp --billing-account=<BILLING_ACCOUNT_ID>

# 2. Enable required APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  --project=teamster-mcp

# 3. Artifact Registry repo for the container image
gcloud artifacts repositories create cube-mcp \
  --repository-format=docker \
  --location=us-central1 \
  --project=teamster-mcp

# 4. Cloud Run runtime service account (narrow scope — reads one secret only)
gcloud iam service-accounts create cube-mcp-runtime \
  --display-name="Cube MCP Cloud Run runtime" \
  --project=teamster-mcp

# 5. Store the Cube signing secret in Secret Manager
#    (value pulled from 1Password by the operator running this step;
#     never committed to the repo)
gcloud secrets create cube-api-secret \
  --replication-policy=automatic \
  --project=teamster-mcp
echo -n "<paste-from-1password>" | gcloud secrets versions add cube-api-secret \
  --data-file=- --project=teamster-mcp
gcloud secrets add-iam-policy-binding cube-api-secret \
  --member="serviceAccount:cube-mcp-runtime@teamster-mcp.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=teamster-mcp
```

### Workload Identity Federation (cross-project)

The existing WIF pool/provider in `teamster-332318` can mint tokens for service
accounts in any project, so we **reuse the existing WIF pool** rather than
creating a new one. Two options for the GitHub Actions deploy identity:

**Option A — Cross-project IAM binding on the existing deploy SA** (simpler):

```bash
# Grant the existing teamster-332318 deploy SA permission to deploy to
# teamster-mcp. Replace <DEPLOY_SA> with the SA currently used by
# dagster-cloud-deploy.yaml or equivalent.
gcloud projects add-iam-policy-binding teamster-mcp \
  --member="serviceAccount:<DEPLOY_SA>@teamster-332318.iam.gserviceaccount.com" \
  --role="roles/run.admin"
gcloud projects add-iam-policy-binding teamster-mcp \
  --member="serviceAccount:<DEPLOY_SA>@teamster-332318.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding teamster-mcp \
  --member="serviceAccount:<DEPLOY_SA>@teamster-332318.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

**Option B — New deploy SA scoped to `teamster-mcp`** (cleaner least-privilege,
more setup). Create a new SA in `teamster-mcp`, bind it to the existing WIF
pool's GitHub repo principal, and reference it from the workflow.

Recommendation: **Option A** for the initial deploy; revisit if/when more MCP
services join `teamster-mcp` and a dedicated deploy SA is warranted.

## Section 5: Dockerfile and Cloud Run

### `src/cube/mcp/Dockerfile`

Minimal Python 3.13 image (`python:3.13-slim`). Copies `src/cube/mcp/server.py`,
installs uv, uses `uv run` to execute — inline PEP 723 dependencies (`mcp`,
`httpx`, `pyjwt`, plus the MCP SDK's JWKS-validation dependency or equivalent)
self-install on container start.

### Cloud Run service config

| Setting           | Value                                                                                   |
| ----------------- | --------------------------------------------------------------------------------------- |
| Project           | `teamster-mcp`                                                                          |
| Region            | `us-central1`                                                                           |
| Min instances     | 0 (scales to zero — no cost between sessions)                                           |
| Memory            | 256 MB                                                                                  |
| CPU               | 0.25 vCPU                                                                               |
| Port              | 8080 ([Cloud Run default](https://cloud.google.com/run/docs/container-contract))        |
| Ingress           | `all` — required for `claude.ai` to reach it; OAuth at MCP layer is the access boundary |
| Runtime SA        | `cube-mcp-runtime@teamster-mcp.iam.gserviceaccount.com`                                 |
| `TRANSPORT`       | `http`                                                                                  |
| `CUBE_REST_URL`   | `https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1`                |
| `AUTHKIT_DOMAIN`  | `<workspace>.authkit.app` (from WorkOS dashboard)                                       |
| `CUBE_API_SECRET` | Secret Manager reference: `projects/teamster-mcp/secrets/cube-api-secret:latest`        |

`CUBE_USER_EMAIL` and `CUBE_JWT_GROUPS` are **not** set — HTTP mode reads email
from the verified OAuth token; groups resolve via Directory API.

## Section 6: GitHub Actions deployment

New `.github/workflows/deploy-cube-mcp.yaml`, triggered on push to `main` when
`src/cube/mcp/**` changes.

Steps:

1. Authenticate to GCP via Workload Identity Federation (pool in
   `teamster-332318`; impersonates the deploy SA per Section 4).
2. Build and push image to Artifact Registry
   (`us-central1-docker.pkg.dev/teamster-mcp/cube-mcp/cube-mcp:<sha>`).
3. `gcloud run deploy --project=teamster-mcp` with the new image and config
   variables.

Follows the same GCP auth pattern as `dagster-cloud-deploy.yaml`, with the
`--project` flag retargeted to `teamster-mcp`.

## Section 7: Claude.ai Custom Connector setup

One-time setup by an admin (data team) at the Claude.ai workspace level:

1. `claude.ai` → **Settings** → **Connectors** → **Add custom connector**.
2. Paste the Cloud Run service URL
   (`https://<service>-<hash>.us-central1.run.app/mcp`).
3. Claude.ai fetches OAuth metadata from the MCP server, discovers WorkOS
   AuthKit as the AS, registers itself via DCR.
4. Connector appears in the workspace; all directors see it in their tools.

The connector configuration is pushed to all workspace members automatically —
no per-user installation step.

## Section 8: End-user (director) workflow

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

## Section 9: Director-facing documentation

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

## Section 10: Data-team workflow — dogfood the remote service

The data team switches their VS Code Codespace `.mcp.json` `cube` entry to point
at the same Cloud Run service the directors use. The Claude Code VS Code
extension's native remote-MCP+OAuth support is undocumented and has known bugs
([anthropics/claude-code#46640](https://github.com/anthropics/claude-code/issues/46640)),
so the bridge tool [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) runs
as a stdio adapter — the extension sees stdio (well supported), the remote
service sees HTTP (well supported), and OAuth (DCR, browser flow, token refresh)
is handled inside `mcp-remote`. The pattern is the same one Claude Desktop uses
to reach remote MCP servers.

Updated `.mcp.json` `cube` entry:

```json
{
  "mcpServers": {
    "cube": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://<cloud-run-url>/mcp"]
    }
  }
}
```

Benefits:

- Per-user OAuth identity for the data team — same auth surface as directors.
- Cube signing secret no longer fetched into every Codespace via 1Password.
- New engineers don't need 1Password access to the Cube credential to query
  Cube. They only need it if they're modifying the MCP server itself.
- Tool description / instruction tuning ships via Cloud Run deploy; no
  per-Codespace MCP restart required.
- Dogfoods the same path directors are using — issues surface to engineers who
  can fix them.

### Smoke test required before rollout

`mcp-remote`'s OAuth flow opens a browser with a `localhost:<port>` callback.
Codespaces auto-forwards localhost ports, but this needs end-to-end verification
before declaring it the official data-team path. Step 12 in the rollout sequence
(Section 11) covers this.

### Escape hatch — stdio mode for MCP-server development

Stdio mode in `src/cube/mcp/server.py` is retained as a development mode for
iterating on the MCP server itself (editing tool descriptions, adding tools,
fixing bugs locally before deploy). The launcher
[scripts/cube-rest-mcp-launch.sh](../../../scripts/cube-rest-mcp-launch.sh)
stays in `scripts/`, updated to point at the new `src/cube/mcp/server.py` path.
Behavior is unchanged from today: `TRANSPORT` and `AUTHKIT_DOMAIN` unset →
server runs stdio with `CUBE_USER_EMAIL` resolution.

### CLAUDE.md updates required

- Project CLAUDE.md "MCP tool selection" section: drop the "VS Code extension
  silently swallows elicit; call `set_user_email`" workaround — no longer
  applies to the data-team path. Replace with a note that `cube` MCP is now
  served from Cloud Run via `mcp-remote`; stdio mode (and `set_user_email`) is
  documented as MCP-server-development-only.
- [scripts/CLAUDE.md](../../../scripts/CLAUDE.md) script-catalog entry for
  `cube-rest-mcp-launch.sh` reframed as "dev-mode launcher" rather than the
  default cube MCP path.

## Section 11: Rollout sequence

1. `teamster-mcp` GCP project created, billing linked, APIs enabled, Artifact
   Registry repo created, runtime SA created, Cube signing secret stored in
   Secret Manager (per Section 4).
2. Cross-project IAM binding granted to the existing GitHub Actions deploy SA
   (or new SA created in `teamster-mcp` per Option B).
3. WorkOS tenant set up; Google Workspace OIDC connection configured with domain
   restriction; DCR enabled.
4. File reorganization (`scripts/cube_rest_mcp.py` → `src/cube/mcp/server.py`)
   on this branch.
5. HTTP transport + OAuth resource-server config added to
   `src/cube/mcp/server.py`.
6. Dockerfile written and tested locally (stdio path unchanged; HTTP path
   smoke-tested with a manually-minted AuthKit token).
7. Manual Cloud Run deploy to `teamster-mcp` for end-to-end smoke test.
8. GitHub Actions workflow written and validated.
9. Director-facing docs page drafted and published.
10. Claude.ai Custom Connector created pointing at Cloud Run service URL.
11. Smoke test with one director account before broader rollout.
12. Data-team smoke test: one engineer switches their Codespace `.mcp.json` to
    the `mcp-remote` bridge entry per Section 10 and verifies the Codespace
    OAuth callback flow works end to end. If successful, document the switch in
    the project CLAUDE.md and roll out to the rest of the data team. If the
    Codespace callback flow fails, file an upstream issue against `mcp-remote`
    or the VS Code extension and revert that engineer to stdio dev mode while
    the Cloud Run path remains live for directors.
