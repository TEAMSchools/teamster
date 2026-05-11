# Cube MCP Remote Deployment Design

**Issue:** [#3879](https://github.com/TEAMSchools/teamster/issues/3879)
**Date:** 2026-05-11 **Status:** Draft — auth option (Section 4) requires
decision before implementation

## Background

The data team accesses the Cube semantic layer via a custom MCP server
(`scripts/cube_rest_mcp.py`) running locally in the VS Code Codespace. It wraps
Cube Cloud's REST API and mints per-user JWTs, giving each user appropriately
scoped access to the data model.

For a director-level POC training (target: two weeks), we need a version of this
server that directors can reach from Claude without any local setup — no cloning
the repo, no copying scripts, no distributing secrets.

### Option A considered and set aside

The fastest path would be minting a long-lived JWT and pointing users at Cube's
native `/api/mcp` endpoint with `mcp-remote`. This was ruled out for two
reasons:

1. **Token overhead.** Cube's native MCP server is verbose — it returns the full
   data model catalog on every session and generates more tokens per query than
   the custom server.
2. **LLM guidance.** `cube_rest_mcp.py` ships with tighter tool descriptions and
   query-format guardrails that meaningfully improve response quality for
   non-technical users.

The custom server is worth the deployment work.

---

## Goal

Deploy `scripts/cube_rest_mcp.py` as a Cloud Run service reachable as a remote
MCP server. All directors connect to one URL; no per-user script installation or
secret distribution required. The existing stdio path (Codespace, Desktop) is
unchanged.

## Out of scope

Per-user identity, Google Groups Directory API integration, and per-user OAuth
(email-scoped Cube access). Those are a follow-up once the POC validates the
concept. Note: OAuth as an HTTP-layer auth mechanism for the Cloud Run endpoint
is in scope — see Section 4.

---

## Section 1: Code changes to `cube_rest_mcp.py`

Two backward-compatible additions to the existing script.

### 1a. HTTP transport mode

Add a `TRANSPORT` config variable (default: `stdio`). When set to `http`, the
server calls:

```python
mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
```

Port 8080 is what Cloud Run expects. The stdio path is completely unchanged when
`TRANSPORT` is unset or `stdio`.

### 1b. JWT group embedding

`cube.js` resolves access groups in this order:

1. `securityContext.groups` — JWT claims (pass-through, no Directory API call)
2. `groupCache` — populated by `contextToGroups` if it ran first
3. `CUBE_GROUP_MAP` — local dev only

The Directory API (path 2) is not yet configured. If a JWT carries no `groups`
claim and the email doesn't resolve via Directory API, `queryRewrite` applies
the default-deny filter (`WHERE 1=0`).

Fix: add a `CUBE_JWT_GROUPS` config variable. When set, its comma-separated
values are embedded in every minted JWT as a `groups` claim. The `cube.js`
pass-through picks them up without hitting the Directory API.

For the shared remote service:

```
CUBE_JWT_GROUPS=cube-network-summary,cube-access-student-data
```

This gives directors network-wide access including student-level data. Adjust
before production if finer scoping is needed.

---

## Section 2: Shared credential

The remote service uses a single shared identity:

| Variable          | Value                                                            |
| ----------------- | ---------------------------------------------------------------- |
| `CUBE_USER_EMAIL` | `ai-assistant@apps.teamschools.org` (or similar service account) |
| `CUBE_JWT_GROUPS` | `cube-network-summary,cube-access-student-data`                  |

Every query is executed as this identity. Cube Cloud logs show this email for
all director traffic, distinguishing it from individual data team queries.

When the Directory API and per-user Google Workspace groups are configured
(post- POC), the shared credential is replaced by OAuth and each user's own
email flows through.

---

## Section 3: Dockerfile and Cloud Run

### `Dockerfile.cube-mcp` (repo root)

Minimal Python 3.13 image. Copies only `scripts/cube_rest_mcp.py` and uses
`uv run` to execute it — inline script dependencies (`mcp`, `httpx`, `pyjwt`)
self-install on first run.

### Cloud Run service config

| Setting           | Value                                                                              |
| ----------------- | ---------------------------------------------------------------------------------- |
| Region            | `us-central1` (matches GKE cluster)                                                |
| Min instances     | 0 (scales to zero — no cost between sessions)                                      |
| Memory            | 256 MB                                                                             |
| CPU               | 0.25 vCPU                                                                          |
| Port              | 8080                                                                               |
| `TRANSPORT`       | `http`                                                                             |
| `CUBE_REST_URL`   | `https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1`           |
| `CUBE_USER_EMAIL` | `ai-assistant@apps.teamschools.org`                                                |
| `CUBE_JWT_GROUPS` | `cube-network-summary,cube-access-student-data`                                    |
| `CUBE_API_SECRET` | Cloud Run secret (from 1Password: `op://Data Team/Cube Cloud REST API/credential`) |

---

## Section 4: HTTP authentication — decision required

**Claude.ai workspace integrations only support OAuth for authentication — not
bearer tokens.** (Confirmed:
[anthropics/claude-ai-mcp#112](https://github.com/anthropics/claude-ai-mcp/issues/112),
marked "closed, not planned".) This is likely what the team encountered when
attempting to connect the native Cube MCP.

Three options are presented for the director and engineer to decide:

### Option A: No HTTP auth (recommended for POC)

Deploy Cloud Run with `--allow-unauthenticated`. The service URL is shared
internally only. Security relies on Cube-level access controls: the shared JWT
limits all queries to `cube-network-summary` and `cube-access-student-data` — no
admin access, no write access, no other users' data.

**Tradeoff:** Anyone who discovers the URL can query Cube as the shared
credential. Acceptable for a short-lived internal POC; must be addressed before
production.

**Claude Teams setup:** Add the Cloud Run URL directly as a workspace
integration with no auth header. All members get it automatically in the
browser, zero per-user config.

### Option B: Bearer token, Claude Desktop only

Protect the endpoint with a shared bearer token validated by middleware in the
MCP server. Directors add one entry to
`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cube": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://<cloud-run-url>/mcp",
        "--header",
        "Authorization: Bearer <token>"
      ]
    }
  }
}
```

**Tradeoff:** Per-user config is required (one step, but not zero). Claude.ai
browser workspace integrations cannot use bearer tokens — browser access is
blocked. Best if the team is comfortable with Desktop-only for the POC.

### Option C: Google OAuth (recommended for production)

Add OAuth 2.0 (Google as provider) to the Cloud Run server using FastMCP's auth
middleware. Claude.ai workspace integrations support OAuth natively — users
authenticate once with their Google account, no config required.

**Tradeoff:** Meaningful additional build time. Likely out of scope for the
two-week POC deadline, but the right long-term answer. Per-user email flows
through to Cube automatically, making the Directory API integration
straightforward to add afterward.

---

## Section 5: GitHub Actions deployment

New `.github/workflows/deploy-cube-mcp.yaml`, triggered on push to `main` when
`scripts/cube_rest_mcp.py` or `Dockerfile.cube-mcp` changes.

Steps:

1. Authenticate to GCP via Workload Identity Federation
2. Build and push image to Artifact Registry
   (`us-central1-docker.pkg.dev/teamster-332318/cube-mcp/cube-mcp:<sha>`)
3. `gcloud run deploy` with the new image and config variables

Follows the same GCP auth pattern as `dagster-cloud-deploy.yaml`.

**Engineer prerequisite to verify:** Does the existing GCP service account used
in GitHub Actions have Cloud Run deploy permissions (`roles/run.admin`,
`roles/iam.serviceAccountUser`)? If not, a new service account scoped to Cloud
Run is needed before the workflow can be written.

---

## Section 6: Claude Teams workspace integration

Once the Cloud Run service is running (and auth option is decided):

1. Admin opens **claude.ai → Settings → Integrations → Add integration**
2. Enters the Cloud Run service URL (`https://<hash>-uc.a.run.app/mcp`)
3. Auth: none (Option A), or OAuth flow (Option C)

All workspace members get the integration automatically. In Claude Desktop,
members see a one-time prompt to enable workspace integrations; after that it is
seamless.

**Caveat:** Claude Desktop workspace integration sync behavior should be
verified at training time. If it does not flow through automatically, the
browser-based claude.ai is the reliable fallback — workspace integrations work
there without any client-side config.

---

## Rollout sequence

1. Engineer verifies GCP service account permissions (prerequisite)
2. Director decides on auth option (Section 4)
3. Code changes to `cube_rest_mcp.py` (Sections 1a, 1b)
4. `Dockerfile.cube-mcp` written and tested locally
5. Cloud Run service deployed manually (smoke test)
6. GitHub Actions workflow written and tested
7. Workspace integration added to Claude Teams
8. Director-level smoke test before training
