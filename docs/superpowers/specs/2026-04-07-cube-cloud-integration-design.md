# Cube Cloud Integration Design

**Date:** 2026-04-07 **Status:** Draft

## Overview

Integrate Cube Cloud Enterprise with the teamster repository as the semantic
layer between BigQuery and all downstream analytics tools. Cube model files live
in `src/cube/` alongside dbt models, are editable in VS Code, and are deployed
automatically by Cube Cloud via Git sync. Security — row-level, column-level,
and org-hierarchy filtering — is configured once in Cube and enforced for all
consumers.

## Goals

- Cube model files (`src/cube/model/`) live in the teamster repo and go through
  the same PR/review process as dbt models
- Cube Cloud handles all deployment infrastructure via Git sync — no self-hosted
  Docker or Cloud Run
- A single security configuration in `cube.js` enforces row-level, column-level,
  and org-hierarchy access for all downstream tools
- Developers validate changes locally (Cube Core) before pushing to their Cube
  Cloud dev deployment
- Analysts develop models using VS Code; Cube Cloud UI is a testing surface only

## Non-goals

- Self-hosted Cube deployment (Dockerfile, Cloud Run, GitHub Actions deploy
  workflow)
- dbt Semantic Layer as Cube data source — Cube reads BigQuery `kipptaf` schema
  directly; dbt integration is metadata enrichment only
- Vercel and Supabase integrations — future work
- Cube model expansion beyond existing marts — this spec covers integration
  setup and core model scaffolding only

## Repository Structure

```text
src/cube/
  cube.js                  # Main config: dbt integration, security context,
                           #   Directory API cache, queryRewrite, access policies
  package.json             # @cubejs-backend/server + dev script
  package-lock.json
  .env.example             # Required env vars for local dev (committed)
  .gitignore               # excludes .env, node_modules, .cubestore
  model/
    cubes/                 # One YAML file per mart (carried from feature branch)
      dim_dates.yml
      dim_locations.yml
      dim_staff.yml        # salary/compensation → cube-perm-hr access policy
      dim_students.yml     # PII fields → cube-perm-pii access policy
      dim_terms.yml
      fct_family_communications.yml
      fct_staff_attrition.yml
      fct_staff_benefits_enrollments.yml
      fct_staff_observation_microgoals.yml
      fct_student_attendance_daily.yml
      fct_student_attendance_interventions.yml
      fct_work_assignment_additional_earnings.yml
    views/
      attendance_metrics.yml
      staff_information_metrics.yml
  SETUP.md                 # Cube Cloud one-time setup + local dev guide
```

Carried over from `claude/feat/cube-semantic-layer`.

## Architecture

```text
Google Workspace (Admin Directory API)
        │ group membership, cached 5 min per user
        ▼
┌─────────────────────────────────────────────┐
│             Cube Cloud (Enterprise)          │
│  cube.js: contextToGroups, queryRewrite,     │
│           member access policies,            │
│           dbt Cloud metadata                 │
│  model/cubes/  ·  model/views/               │
│  prod deployment → main branch               │
│  dev deployment  → feature branch (per eng.) │
└─────────────────────────────────────────────┘
        │ reads data directly
        ▼
BigQuery — kipptaf schema (marts)
        ▲ materialized by
        │
dbt Cloud (project 211862)
  └─ metadata only → cube.js at startup

Downstream consumers (all authenticate per-user):
  Tableau Server  — Semantic Layer Sync, PAT auth
  Superset        — SQL API, impersonation
  Streamlit       — REST API, JWT
```

## Google Group Naming Convention

All Cube-relevant groups use a `cube-` prefix so `contextToGroups` can filter
them out of a user's full group list without a mapping table. Existing groups
are untouched — staff are assigned to both existing and new Cube groups.

**Scope groups** (control which rows a user can see):

```text
cube-network-detail          # all regions, row-level access
cube-network-trends          # all regions, aggregates only

cube-region-{region}-detail  # all schools in region, row-level
cube-region-{region}-trends  # all schools in region, aggregates only

cube-school-{slug}-detail    # one school, row-level
cube-school-{slug}-trends    # one school, aggregates only
```

A user with `cube-school-{slug}-detail` implicitly has access to trends for
their school — the detail group is a superset of trends access. The
`cube-school-{slug}-trends` group exists for users who should see aggregated
data for a school without seeing individual rows (e.g., a community partner).

`{region}` matches `location_region` values from `dim_locations` (lowercased,
hyphenated). `{slug}` matches `location_abbreviation` from `dim_locations`.

**Permission groups** (control which columns or cubes a user can see):

```text
cube-perm-hr          # salary, compensation fields on dim_staff
cube-perm-pii         # PII fields on dim_students
cube-perm-all-staff   # bypass org-hierarchy filter on staff cubes
cube-perm-academic    # access to academic cubes (attendance, assessments, etc.)
                      # users without this group (e.g. finance) do not see
                      # academic cubes in schema introspection or query results
```

**Examples:**

| Role                     | Groups assigned                                                         |
| ------------------------ | ----------------------------------------------------------------------- |
| Newark AP (Bold Academy) | `cube-school-bold-detail`, `cube-region-newark-trends`                  |
| Newark Head of Schools   | `cube-region-newark-detail`, `cube-perm-all-staff`                      |
| Network HR Director      | `cube-network-detail`, `cube-perm-hr`, `cube-perm-all-staff`            |
| Finance analyst          | `cube-network-trends` (no `cube-perm-academic` → academic cubes hidden) |

## Security Model

Three layers, all enforced in `cube.js` and cube YAML. No security configuration
exists in downstream tools — Cube is the single source of truth.

### Layer 1 — Identity resolution (`contextToGroups`)

At request time, Cube resolves two things from the authenticated user's email,
both cached 5 minutes per user:

1. **Google Group memberships** — calls Admin Directory API, filters to `cube-*`
   groups only. Locally, reads from `CUBE_GROUP_MAP` env var instead.
2. **Employee number** — lookup against `dim_staff` by email. Used for
   org-hierarchy filtering on staff cubes.

Both lookups run in parallel. The `contextToGroups` function is `async`.

### Layer 2 — Row-level filtering (`queryRewrite`)

Applied to every query. Logic evaluated in priority order:

1. User has `cube-network-*` → no location filter
2. User has `cube-region-{region}-*` → filter by `location_region`
3. User has `cube-school-{slug}-*` → filter by `location_abbreviation`
4. No matching scope group → query returns empty (default deny)

**Trends vs detail:** Views are split by access level. Detail views expose
individual-row dimensions; trends views expose only aggregated measures and
school-level groupings. A user with `cube-region-newark-trends` can query
`attendance_trends` but not `attendance_detail`.

**Org hierarchy filter (staff cubes only):** Applied in addition to location
scope unless the user has `cube-perm-all-staff`:

```sql
WHERE employee_number IN (
  SELECT descendant_employee_number
  FROM kipptaf_marts.dim_staff_hierarchy
  WHERE ancestor_employee_number = {current_user_employee_number}
)
```

This requires a new dbt model — see [New dbt Model](#new-dbt-model) below.

### Layer 3 — Column-level access policies (YAML)

Sensitive dimensions are marked with `accessPolicy` in their cube YAML:

- `salary`, `previous_salary`, `hourly_rate` on `dim_staff` → requires
  `cube-perm-hr`
- PII fields on `dim_students` → requires `cube-perm-pii`. The specific field
  list must be enumerated during implementation by reviewing all `dim_students`
  columns and classifying each as PII or not.

Users without the required permission group do not see those dimensions in any
tool — they are absent from schema introspection and query results.

## New dbt Model

**`dim_staff_hierarchy`** — transitive closure of the org chart. New model in
`src/dbt/kipptaf/models/marts/dimensions/`.

Schema:

```
ancestor_employee_number   STRING
descendant_employee_number STRING
depth                      INT64
```

One row per (ancestor, descendant) pair at any depth. Built from
`dim_staff.manager_employee_number` recursively. Refreshes on the standard marts
cadence so org chart changes propagate automatically.

## `cube.js` Configuration

Four responsibilities:

**1. dbt Cloud metadata integration** Cube fetches the compiled manifest from
dbt Cloud project `211862` at startup using `DBT_CLOUD_TOKEN` and
`DBT_CLOUD_PROJECT_ID`. Column descriptions, model descriptions, and types
populate Cube's schema automatically. For local dev, Cube reads a locally
generated manifest — run `uv run dbt compile --project-dir src/dbt/kipptaf`
before starting Cube. Exact `cube.js` API key for dbt Cloud must be verified
against current Cube docs during implementation (two options: dbt Cloud API or
local manifest path).

**2. `contextToGroups` — identity resolution** Async function. Checks
`CUBE_GROUP_MAP` first (local dev fallback). In Cloud deployments, calls Admin
Directory API with 5-minute in-memory cache per email, in parallel with
`dim_staff` employee number lookup.

**3. `queryRewrite` — row-level security** Parses `cube-*` groups from the
resolved context. Applies location and org-hierarchy filters as described in the
security model. Default deny if no scope group matches.

**4. `canSwitchSqlUser: () => true`** Enables per-user SQL API connections for
Superset — each user's session carries their own security context rather than a
shared service account's.

## Pre-aggregations

All pre-aggregations include the location dimension (`location_abbreviation` or
`location_region`) so `queryRewrite` filters hit CubeStore rather than BigQuery.
BigQuery is only queried during scheduled refreshes.

Refresh schedule is configured in Cube Cloud per pre-aggregation, aligned to the
dbt run cadence. Exact timing is a setup detail.

| Cube                           | Detail grain             | Trends grain           |
| ------------------------------ | ------------------------ | ---------------------- |
| `fct_student_attendance_daily` | school + student + date  | school + month         |
| `fct_staff_attrition`          | school + employee + date | school + academic_year |
| `dim_staff`                    | school + employee        | school                 |

Lower-volume cubes fall through to BigQuery until pre-aggregations are added in
a follow-on PR — acceptable for infrequently queried data.

`dim_staff_hierarchy` is not pre-aggregated — it is a small table used only as a
filter subquery.

## Downstream Integrations

### Tableau Server — Semantic Layer Sync

Cube Cloud pushes the data model to Tableau Server using a Personal Access Token
(PAT). Published data sources appear in Tableau for analysts to connect to
directly — no SQL or schema knowledge required. Sync runs automatically on merge
to `main`.

**A1 — verify during setup:** Cube Cloud must forward the Tableau viewer's
username back to Cube for `queryRewrite` to apply per-user security. If this is
not supported by the Tableau connector version in use, column-level and
row-level security for Tableau users must be handled at the published data
source level (separate data sources per access tier) rather than dynamically.

### Superset — SQL API with Impersonation

Superset connects to Cube via a SQLAlchemy Postgres connection. The "Impersonate
the logged in user" setting on the Cube database connection in Superset passes
the Google-authenticated user's email as the SQL username. Cube's `checkSqlAuth`
validates the identity and applies the user's full security context.

**Verify during setup:** Superset's impersonation feature is well-tested with
Hive and Trino but needs validation against Cube's SQL API (Postgres wire
protocol). **Fallback:** if impersonation does not work, Superset connects as a
service account, sensitive cubes (`cube-perm-hr`, `cube-perm-pii`) are excluded
from the Superset connection, and location filtering is handled by Superset's
own row-level security. This breaks the single-security-config goal for Superset
specifically.

Managed Superset (Preset) is compatible with the same design — decision between
self-hosted and Preset is out of scope for this spec.

### Streamlit — REST API

Python apps call Cube's REST endpoint using `cubejs-client` or plain `requests`.
Each request carries a JWT signed with `CUBEJS_API_SECRET` containing the user's
email. `checkAuth` extracts the email and resolves the full security context.
Full per-user security confirmed — no caveats.

## Local Development

**VS Code task** starts Cube Core with one click:

1. Runs `npm install` if `node_modules` is absent
2. Runs `npm run dev`
3. Cube Core Playground available at `localhost:4000`

Prerequisite: run `uv run dbt compile --project-dir src/dbt/kipptaf` once to
generate the local dbt manifest before starting Cube.

BigQuery auth uses ADC (`gcloud auth application-default login`) — no service
account key needed locally.

**Warning:** do not use the Cube Playground's built-in model editor (the Models
tab). In dev mode, Cube treats it as a live editor and overwrites YAML files.
Edit in VS Code only.

## Cube Cloud Setup (one-time)

Performed in the Cube Cloud UI:

1. Connect `TEAMSchools/teamster` GitHub repo
2. Set Cube project path to `src/cube/`
3. Set production branch to `main` — merges trigger automatic redeploy
4. Create one dev deployment per engineer who works on Cube models:
   - Type: Development
   - Name: `dev-{name}`
   - Branch: engineer's current feature branch (updated in UI when they switch)
   - Unique `CUBEJS_API_SECRET` per deployment
5. Set environment variables per deployment (never committed to repo)
6. Configure Tableau Semantic Layer Sync with PAT credentials
7. Request domain-wide delegation for `GOOGLE_DIRECTORY_SA_KEY` service account
   from Google Workspace admin — required for Admin Directory API access

## Environment Variables

| Variable                        | Local dev                    | Cloud (prod/dev)                               |
| ------------------------------- | ---------------------------- | ---------------------------------------------- |
| `CUBEJS_DB_TYPE`                | `bigquery`                   | `bigquery`                                     |
| `CUBEJS_DB_BQ_PROJECT_ID`       | `teamster-332318`            | `teamster-332318`                              |
| `CUBEJS_DB_BQ_CREDENTIALS`      | — (uses ADC)                 | `cube-bq-reader` SA key, base64-encoded        |
| `CUBEJS_API_SECRET`             | any string                   | random 64-char, unique per deployment          |
| `CUBEJS_DEV_MODE`               | `true`                       | omit                                           |
| `CUBEJS_CACHE_AND_QUEUE_DRIVER` | `memory`                     | omit (uses CubeStore)                          |
| `CUBE_GROUP_MAP`                | JSON string for local groups | omit (uses Directory API)                      |
| `DBT_CLOUD_TOKEN`               | omit (uses local manifest)   | dbt Cloud service token, read-only             |
| `DBT_CLOUD_PROJECT_ID`          | omit                         | `211862`                                       |
| `GOOGLE_DIRECTORY_SA_KEY`       | omit                         | SA with domain-wide delegation, base64-encoded |
| `TABLEAU_SERVER_URL`            | omit                         | Tableau Server URL                             |
| `TABLEAU_PAT_NAME`              | omit                         | PAT name for Semantic Layer Sync               |
| `TABLEAU_PAT_SECRET`            | omit                         | PAT secret                                     |

## dbt Exposure Update

`src/dbt/kipptaf/models/exposures/cube.yml` requires two updates:

1. Add `url:` once the Cube Cloud deployment URL is known
2. Expand `depends_on` to include all 12 cube model files in scope: `dim_dates`,
   `dim_locations`, `dim_staff`, `dim_students`, `dim_terms`,
   `fct_family_communications`, `fct_staff_attrition`,
   `fct_staff_benefits_enrollments`, `fct_staff_observation_microgoals`,
   `fct_student_attendance_daily`, `fct_student_attendance_interventions`,
   `fct_work_assignment_additional_earnings`.

## Day-to-Day Development Cycle

1. Create a feature branch
2. Edit `src/cube/model/` YAML files in VS Code
3. Validate locally with the VS Code task (Cube Core, localhost:4000)
4. Push branch → Cube Cloud dev deployment updates automatically
5. Optionally test in Cube Cloud UI against real BigQuery data
6. Open PR → merge to `main` → production deployment updates automatically

## Out of Scope / Future Work

- Vercel and Supabase integrations
- Pre-aggregations for lower-volume cubes
- Cube model expansion to additional marts (planned overhaul)
- Looker Studio or other BI tool integrations
