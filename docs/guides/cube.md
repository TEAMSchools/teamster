# Cube

Cube is the semantic layer between BigQuery and downstream reporting tools
(dashboards, LLMs, apps, etc.). Cube models live in `src/cube/` alongside dbt
models and are version-controlled in this repository. Security — row-level
filtering, column access policies, group membership — is enforced once in Cube
for all downstream consumers.

**Jump to:** [Concepts](#concepts) ·
[Development Workflow](#development-workflow) ·
[Review and Staging](#review-and-staging) · [Local Dev](#local-dev) ·
[Using Cube with Claude](#using-cube-with-claude) · [Admin Setup](#admin-setup)

## Concepts

### Deployment types

Cube Cloud has two deployment types that control infrastructure scaling:

- **Development Instance** — deallocates after inactivity and reallocates when a
  request comes in. Cheaper, but has a cold-start delay on the first query after
  idle.
- **Production Cluster** — always running, no cold starts. Use once downstream
  tools are live and users expect instant responses.

### Environments

A Cube Cloud deployment has two contexts:

- **Production environment** — always tracks `main`. This is what downstream
  tools (Superset, Streamlit) connect to. Redeploys automatically when `main`
  changes.
- **Staging environments** — one per branch, activated automatically when a user
  switches to that branch in the Cube Cloud UI. Each has its own isolated API
  endpoints. Multiple staging environments can be active simultaneously for
  different branches. Suspends after 10 minutes of inactivity by default; toggle
  **always active** in Settings → Staging Environments to keep a branch live for
  multi-day stakeholder review.

**Development mode** is the interactive UI session in Cube Cloud (not a separate
environment — it targets whichever branch is currently active in the UI).
Switching branches in development mode activates that branch's staging
environment.

### How KIPP uses them

One deployment covers everything:

| Context    | What it is                                        | Tracks                                     |
| ---------- | ------------------------------------------------- | ------------------------------------------ |
| Production | Production environment                            | `main`, auto-redeploys on merge            |
| Staging    | Per-branch staging environments, separate API URL | Any branch, multiple active simultaneously |

Staging environments are how analysts test feature branches, reviewers validate
changes, and stakeholders preview models before merge — all within one
deployment, with no additional infrastructure.

## Development Workflow

### 1. Create a branch

```bash
git fetch origin main && git merge origin/main
git checkout -b you/feat/my-cube-change
```

### 2. Edit cube models in VS Code

Edit files in `src/cube/model/cubes/` or `src/cube/model/views/`.

If `main` has new or renamed dbt models since you last compiled, regenerate the
local manifest first:

```bash
uv run dbt compile --project-dir src/dbt/kipptaf
```

You only need this when dbt model definitions change. If you are only editing
Cube YAML files, the existing manifest stays valid.

!!! warning "Do not use the Playground Models tab."

    In dev mode, Cube treats it as a live editor and overwrites YAML files.
    Edit in VS Code only.

### 3. Test locally

Run the **Cube: Dev Server** VS Code task to start Cube at `localhost:4000`. Use
`CUBE_GROUP_MAP` in your `.env` to simulate different users' group membership —
see [Local Dev](#local-dev) for setup.

### 4. Test in Cube Cloud

Push your branch, then switch to it in the Cube Cloud UI's development mode
branch switcher. Cube Cloud activates a staging environment for the branch
automatically.

Test in the Cube Cloud Playground. Your real Google Workspace group membership
applies here — use this to verify security behavior against the real Directory
API.

Check:

- Cubes and views load without errors
- Queries return expected results against live BigQuery data
- Row-level security behaves correctly for your groups
- Existing cubes and views still work (no regressions)

### 5. Open a PR

When ready, open a pull request from your feature branch to `main`.

## Review and Staging

### Peer review

The reviewing analyst:

1. Reads through the YAML changes in the PR
2. Switches to the author's branch — in Cube Cloud dev mode or locally — and
   tests in the Playground:
   - Do all cubes and views load without errors?
   - Do queries return expected results against live BigQuery data?
   - Do existing cubes and views still work?
3. To test security behavior with specific group combinations, run locally with
   `CUBE_GROUP_MAP` set to the groups you want to simulate
4. Leaves review comments on the PR, or approves

Author and reviewer can work together in the same Cube Cloud Playground session
since they're both hitting the same branch.

### Stakeholder review

When a business user needs to validate changes before merge:

1. In Cube Cloud, switch to the feature branch — this activates a staging
   environment for that branch
2. Go to **Settings → Staging Environments** and toggle the branch to **always
   active** so queries don't fail when no one is viewing the branch
3. Find the branch's API URL under **API Credentials**
4. Point the staging instance of the connected tool (dashboard, etc.) at that
   URL and share it with the stakeholder
5. Stakeholder tests queries and dashboards against live data — multiple
   branches can have active staging environments simultaneously
6. Once the stakeholder approves, merge the PR — production redeploys
   automatically from `main`

## Local Dev

1. `cp src/cube/.env.example src/cube/.env`
2. Fill in `CUBE_GROUP_MAP` with your email and the groups you want to simulate:
   ```text
   CUBE_GROUP_MAP='{"you@apps.teamschools.org":["cube-network-detail"]}'
   ```
3. Run the **Cube: Dev Server** VS Code task (`Ctrl+Shift+P` → Tasks: Run Task)
4. Playground opens at `http://localhost:4000`

ADC is used for BigQuery auth locally — run the **GCloud: Application Default
Login** VS Code task first if you haven't already.

## Warnings

Do **not** set `CUBE_GROUP_MAP` in Cube Cloud — it bypasses the Directory API
entirely and must only be used for local dev. The `cube.js` guard relies on
`NODE_ENV !== "production"` as a second line of defense, but the variable should
never be configured in Cube Cloud in the first place.

Do **not** use the Cube Playground **Models** tab in dev mode. It overwrites
YAML files in `model/cubes/` and `model/views/` with auto-generated content,
discarding hand-authored definitions.

## Maintenance

### Keeping Cube in sync when dbt column names change

There is no automatic cross-tool check out of the box. Three layers of
protection cover it:

**Layer 1 — dbt contracts (already enforced)** All `dim_*` and `fct_*` models
have `contract: enforced: true`. Renaming a column requires updating the
properties YAML or the dbt build fails in CI. That required edit is the natural
moment to check whether any Cube YAML in `src/cube/model/` references the old
column name. Treat the contract YAML diff in PR review as the signal: if a
column name changes there, grep `src/cube/model/` for it.

**Layer 2 — Cube query-time errors (reactive)** With explicit column references
in every `sql:` field, a broken reference produces a clear BigQuery error the
first time someone queries that dimension — not a silent wrong result. It points
directly to the broken field.

**Layer 3 — `cube validate` in CI (target state)** Cube's `cube validate`
command parses all YAML and dry-runs the SQL against the warehouse. Adding this
step to the CI pipeline catches broken column references at merge time, before
they reach production. This should be wired up as part of the infrastructure
work — it is the right long-term answer and removes the manual grep step from PR
review.

**Analyst-facing name vs. source column name** The Cube `name:` field (what
analysts see in the UI and API) and the `sql:` field (the BigQuery column
reference) are independent. A dbt column rename requires updating `sql:` only —
the analyst-facing `name:` is stable. Renaming a field in the UI requires
updating `name:` only — no BigQuery query changes. Keep these two concerns
separate when reviewing rename PRs.

### Renaming `name:` fields when BI tools are connected

Once a BI tool (Tableau, Superset, Streamlit, etc.) is connected to a Cube view,
the `name:` field is a public API. Renaming it breaks any saved report,
dashboard, or query that references the old name — the field silently drops or
returns "not found".

**Rule: treat view `name:` fields as stable contracts once a BI tool is
connected. Do not rename without coordinating with BI consumers first.**

Three options when a rename is unavoidable:

**Option 1 — Deprecation window** Keep the old `name:` in the view alongside the
new one temporarily. Communicate the cutover date to BI consumers, remove the
old name after dashboards are updated.

**Option 2 — Views as the stable interface (structural mitigation)** This is the
strongest argument for the two-view pattern. Analysts connect BI tools to
`attendance_detail` / `attendance_summary` views, not directly to cubes. A
`name:` change inside the cube can be remapped in the view without touching the
field name the BI tool sees — the view `name:` stays stable even if the
underlying cube dimension is reorganized.

**Option 3 — Cube aliases** Cube does not have a native field deprecation
mechanism today. Until it does, Option 1 or Option 2 are the available paths.

**Internal vs. external `name:` fields** Cube `name:` fields are internal — safe
to rename freely before any BI tool connects. View `name:` fields are external
once a downstream consumer exists — coordinate before changing. Document which
views have active BI connections in the exposure YAML (`models/exposures/`) so
the boundary is visible in PR review.

## Using Cube with Claude

The Cube MCP server lets Claude query your organization's data using plain
English — no SQL required. Once connected, you can ask questions like:

- "What metrics are available?"
- "Show me ADA by school for this year"
- "What are the available dimensions in the student cube?"

Claude uses the Cube semantic layer to find and return the right data.

### Claude Desktop

The Cube MCP uses OAuth. You authenticate with your `@apps.teamschools.org`
Google Workspace account on first use.

1. **Install Node.js** if you don't have it:

   ```bash
   node --version
   ```

   If you see a version number, skip ahead. Otherwise install via Homebrew:

   ```bash
   brew install node
   ```

2. **Get the Cube MCP service URL** from the data team.

3. **Open the config file.** In Claude Desktop, go to **Settings → Developer →
   Edit Config**. Or navigate directly in Finder:

   ```text
   ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

   If the file doesn't exist yet, create it with an empty `{}`.

4. **Add the Cube MCP server.** Replace `<CUBE_MCP_URL>` with the URL from step
   2:

   ```json
   {
     "mcpServers": {
       "cube": {
         "command": "npx",
         "args": ["-y", "mcp-remote", "<CUBE_MCP_URL>"]
       }
     }
   }
   ```

   If your config already has content, add `mcpServers` alongside the existing
   keys — don't replace anything.

5. **Restart Claude Desktop.** Press `Cmd+Q` to fully quit (don't just close the
   window), then reopen.

6. **Authenticate.** The first time Claude uses the Cube tool, a browser tab
   opens to a Google sign-in prompt. Sign in with your `@apps.teamschools.org`
   account. After approving, you're redirected back to Claude Desktop and the
   connection is live. Subsequent sessions authenticate silently via refresh
   token.

### Claude Code (VS Code)

In the Codespace, the Cube MCP server is already configured in `.mcp.json` — no
manual setup required. When Claude Code first tries to use it, you'll be
prompted to OAuth into Cube Cloud. Approve the connection and you're ready to
query.

### Using Cube in Claude

Once connected, toggle Cube MCP on via the **+** or tools menu in your chat,
then ask questions in plain English:

- "What data do you have access to?"
- "What metrics can I query?"
- "Show me [metric] by [dimension] for [time period]"

Claude interprets your question using the Cube semantic layer and returns
results directly in the chat. No table names, field names, or SQL required.

### Troubleshooting

**"Server disconnected" error** — Claude can't find `npx`. Run `which npx` in
Terminal and make sure the path in your config matches exactly.

**`npx` not found** — Node.js isn't installed. Follow step 1 above.

**Tools icon doesn't appear after restart** — Your JSON has a formatting error
(missing comma, mismatched brackets). Paste the file into
[jsonlint.com](https://jsonlint.com) to check.

**Check the logs** — For any other issue, check the MCP server log:

```bash
tail -f ~/Library/Logs/Claude/mcp-server-cube-mcp-server.log
```

## Admin Setup

### Why a Service Account Key Is Required

Cube looks up each user's Google Workspace group membership at query time using
the Admin Directory API. It calls the API as a service account with
[domain-wide delegation](https://developers.google.com/workspace/guides/create-credentials#optional_set_up_domain-wide_delegation_for_a_service_account)
— a mechanism that lets the service account impersonate a Workspace super-admin,
which is required for cross-domain group lookups.

Keyless authentication (Workload Identity Federation) would eliminate the need
for a stored key, but it requires the workload to present an OIDC token from a
trusted identity provider to Google's Security Token Service. Cube Cloud is
managed SaaS running on Cube's infrastructure — KIPP cannot configure Workload
Identity on those pods. A service account key is the only viable credential for
this deployment.

If Cube is ever migrated to a self-hosted deployment on KIPP's GKE cluster,
Workload Identity can replace the key — `GoogleAuth` would pick up ambient ADC
credentials automatically and `GOOGLE_DIRECTORY_SA_KEY` could be removed.

### Directory API Service Account Setup

Performed once by an admin. Creates the service account used by Cube to look up
Workspace group membership.

#### 1. Enable the Admin SDK API

In the [GCP Console](https://console.cloud.google.com/apis/library) for project
`teamster-332318`, search for **Admin SDK API** and enable it.

#### 2. Create the service account

In **IAM & Admin → Service Accounts**, create a new service account:

- Name: `cube-directory-reader`
- ID: `cube-directory-reader@teamster-332318.iam.gserviceaccount.com`
- No GCP IAM roles — access is granted via Workspace DWD, not GCP IAM

Do not reuse the BigQuery service account (`CUBEJS_DB_BQ_CREDENTIALS`). The
BigQuery SA has GCP data access; combining it with DWD means a single key
compromise grants both warehouse access and domain-wide group enumeration.

#### 3. Create a JSON key

In the service account details, go to **Keys → Add key → Create new key →
JSON**. Download the file and keep it secure.

#### 4. Grant domain-wide delegation in Google Workspace

In [Google Workspace Admin](https://admin.google.com), go to **Security → Access
and data control → API controls → Domain-wide delegation → Add new**:

- **Client ID**: the numeric client ID from the service account details page in
  GCP
- **OAuth scopes**:
  `https://www.googleapis.com/auth/admin.directory.group.readonly`

#### 5. Encode the key and set environment variables

Base64-encode the JSON key (no line wrapping):

```bash
base64 -w 0 key.json
```

Set the following in Cube Cloud:

- `GOOGLE_DIRECTORY_SA_KEY` — the base64-encoded output
- `GOOGLE_DIRECTORY_SA_SUBJECT` — email of the dedicated Workspace admin account
  used as the impersonation subject (see below)

!!! warning "Delete the key file after encoding — never store the raw JSON."

#### Key rotation

Rotate the key if it is ever exposed. In GCP, create a new key on the service
account, update `GOOGLE_DIRECTORY_SA_KEY` in Cube Cloud, then delete the old
key.

#### 6. Create the impersonation subject account

The Directory API requires the service account to act as a Workspace super-admin
— this is the `GOOGLE_DIRECTORY_SA_SUBJECT` value. It must be a **dedicated
shared admin account**, not a personal one. If the account is suspended,
deleted, or has super-admin revoked, every Cube query will fail with a default
deny (no data visible to any user).

In [Google Workspace Admin](https://admin.google.com):

1. **Directory → Users → Add new user** — create
   `cube-service@apps.teamschools.org` (or similar)
2. **Account → Admin roles → Super Admin → Assign** on that user

Set `GOOGLE_DIRECTORY_SA_SUBJECT` to that account's email in Cube Cloud.

!!! warning "Never use a personal admin account as the impersonation subject."

### Cube Cloud One-Time Setup

Performed in the Cube Cloud UI by an admin:

1. Create a new Cube Cloud deployment — use **Development Instance** type for
   now; switch to **Production Cluster** before connecting downstream tools
   (Superset, Streamlit) so queries don't hit a cold start
2. Connect the `TEAMSchools/teamster` GitHub repository
3. Set the Cube project path to `src/cube/`
4. Set the production branch to `main` — merges trigger automatic redeploy
5. Set the following environment variables in Cube Cloud:
   - `CUBEJS_DB_TYPE=bigquery`
   - `CUBEJS_DB_BQ_PROJECT_ID=teamster-332318`
   - `CUBEJS_DB_BQ_CREDENTIALS` — service account JSON (base64-encoded)
   - `GOOGLE_DIRECTORY_SA_KEY` — Admin Directory API service account
     (base64-encoded)
   - `GOOGLE_DIRECTORY_SA_SUBJECT` — email of the dedicated Workspace admin
     account used as the impersonation subject (e.g.
     `cube-service@apps.teamschools.org`)
   - `CUBEJS_SQL_SUPER_USER=cube-superset-service` — SQL API super-user for
     Superset user impersonation (follow-up integration)

   Cube Cloud automatically generates `CUBEJS_API_SECRET`, the SQL API username,
   and the SQL API password on deployment creation — find them under the
   deployment's **Settings → Environment Variables**. Do not set these manually.

6. The service account for BigQuery needs `roles/bigquery.dataViewer` and
   `roles/bigquery.jobUser` on the `teamster-332318` project
7. The Admin Directory API service account needs domain-wide delegation scoped
   to `https://www.googleapis.com/auth/admin.directory.group.readonly`
