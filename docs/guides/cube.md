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

Test in the Cube Cloud Playground. Your real access row from
`kipptaf_marts.dim_staff_cube_access` applies here — use this to verify security
behavior against live HR data.

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

1. `cp src/cube/.env.example src/cube/.env` and fill in the BigQuery connection
   variables (already pre-filled in `.env.example` for the teamster project — no
   credentials needed, ADC handles auth)
2. Run the **GCloud: Application Default Login** VS Code task if your ADC token
   is stale
3. Run the **Cube: Dev Server** VS Code task (`Ctrl+Shift+P` → Tasks: Run Task)
4. Playground opens at `http://localhost:4000`
5. Click **Edit Security Context** and set
   `{"email": "you@apps.teamschools.org"}` — Cube resolves your real access row
   from `kipptaf_marts.dim_staff_cube_access`. Change the email to test as
   another user.

## Warnings

Do **not** set `CUBE_GROUP_MAP` in Cube Cloud. This variable is a dev bypass
that short-circuits BigQuery identity reads; it must never be configured in
production.

Do **not** use the Cube Playground **Models** tab in dev mode. It overwrites
YAML files in `model/cubes/` and `model/views/` with auto-generated content,
discarding hand-authored definitions.

When a user requests a field their access tier excludes, Cube **blocks the
entire query** — it does not silently drop the column and return the rest. In
practice this only surfaces in Tableau, where a workbook published by someone
with broad access (e.g. `staff-pii`) may error at query time for viewers with
narrower access. BI tools that connect via Cube's SQL API (Superset) avoid this
because each user's field list is filtered at connection time. A member-strip
approach that drops inaccessible fields transparently is tracked in
[#4268](https://github.com/TEAMSchools/teamster/issues/4268). Until then, build
Tableau workbooks using only the fields your least-privileged audience can see,
or publish separate workbooks per access tier.

## Using Cube with Claude

The Cube MCP server lets Claude query your organization's data using plain
English — no SQL required. Once connected, you can ask questions like:

- "What metrics are available?"
- "Show me ADA by school for this year"
- "What are the available dimensions in the student cube?"

Claude uses the Cube semantic layer to find and return the right data. You'll
need a Cube API key from the data team before getting started.

### Claude Desktop

1. **Install Node.js** if you don't have it:

   ```bash
   node --version
   ```

   If you see a version number, skip ahead. Otherwise install via Homebrew:

   ```bash
   brew install node
   ```

   Then find the full path to `npx` — you'll need it below:

   ```bash
   which npx
   ```

2. **Open the config file.** In Claude Desktop, go to **Settings → Developer →
   Edit Config**. Or navigate directly in Finder:

   ```text
   ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

   If the file doesn't exist yet, create it with an empty `{}`.

3. **Add the Cube MCP server.** Replace `[YOUR-API-KEY]` with your key, and
   update the `command` path if your `npx` location differs:

   ```json
   {
     "mcpServers": {
       "cube-mcp-server": {
         "command": "/opt/homebrew/bin/npx",
         "args": [
           "-y",
           "mcp-remote",
           "https://ai.gcp-us-central1.cubecloud.dev/api/mcp",
           "--transport",
           "http"
         ],
         "env": {
           "CUBE_TOKEN": "[YOUR-API-KEY]"
         }
       }
     }
   }
   ```

   If your config already has content, add `mcpServers` alongside the existing
   keys — don't replace anything.

4. **Restart Claude Desktop.** Press `Cmd+Q` to fully quit (don't just close the
   window), then reopen. A tools/hammer icon in the bottom-right of the chat
   input confirms the server is connected.

!!! warning "Keep your API key private." Treat it like a password — don't share
your config file with anyone outside the pilot group.

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

### How access is resolved

Cube resolves each user's access at query time via two BigQuery reads against
`kipptaf_marts` (no Google Admin Directory API):

1. **`dim_staff_cube_access`** — one row per active+primary staff member, keyed
   on `google_email`. Carries per-field scope enums
   (`student_detail_location_scope`, `staff_pii_scope`, etc.) that `cube.js`
   translates into Cube group strings via `access.buildGroups(row)`.
2. **`dim_staff_reporting_chain`** — transitive closure of the org tree, keyed
   on `(manager_staff_key, reportee_staff_key)`. Used to resolve the viewer's
   direct and indirect reports for `reporting_chain` and
   `reporting_chain_or_below_rank` scopes.

Results are cached until next midnight ET. A staff member not in
`dim_staff_cube_access` (e.g. a non-staff admin user) resolves to an empty group
list and sees no data (default deny).

### Access tiers

`buildGroups(row)` emits the following tier strings based on the access row's
scope columns:

| Tier                 | Emitted when                               |
| -------------------- | ------------------------------------------ |
| `student-summary`    | `student_summary_location_scope != 'none'` |
| `student-detail`     | `student_detail_location_scope != 'none'`  |
| `student-pii`        | `student_pii_scope == 'all'`               |
| `staff-directory`    | always (every resolved viewer)             |
| `staff-pii`          | `staff_pii_scope != 'none'`                |
| `staff-compensation` | `staff_compensation_scope != 'none'`       |
| `staff-observations` | `staff_observations_scope != 'none'`       |
| `staff-benefits`     | `staff_benefits_scope != 'none'`           |

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
   - `CUBEJS_SQL_SUPER_USER=cube-superset-service` — SQL API super-user for
     Superset user impersonation (follow-up integration)

   Cube Cloud automatically generates `CUBEJS_API_SECRET`, the SQL API username,
   and the SQL API password on deployment creation — find them under the
   deployment's **Settings → Environment Variables**. Do not set these manually.

6. The service account for BigQuery needs `roles/bigquery.dataViewer` and
   `roles/bigquery.jobUser` on the `teamster-332318` project — both for the
   warehouse data (`dim_*` / `fct_*`) and for `dim_staff_cube_access` /
   `dim_staff_reporting_chain` used for identity resolution
