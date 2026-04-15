# Cube Infrastructure Design

**Date:** 2026-04-15 **Status:** Draft

## Overview

Configure the `src/cube/` repository structure, security model, and Cube Cloud
deployment so engineers can develop and validate Cube models locally and in Cube
Cloud dev deployments. This spec covers infrastructure only — cube model YAML
files are addressed in a follow-up spec.

## Goals

- `src/cube/` is a fully configured Cube project, version-controlled alongside
  dbt models
- Security is enforced once in `cube.js` for all downstream consumers — no
  per-tool access configuration
- Engineers can run Cube Core locally against BigQuery using ADC and simulate
  any group membership via `CUBE_GROUP_MAP`
- Cube Cloud handles all deployment infrastructure via Git sync — no self-hosted
  Docker or Cloud Run

## Non-goals

- Cube model YAML files (67 models across 12 domains) — follow-up spec
- Pre-aggregations — follow-up spec
- Downstream integrations (Tableau, Superset, Streamlit) — follow-up spec
- Google Group creation and member assignment in Workspace Admin — separate
  issue scoped to IT admin team
- Vercel and Supabase integrations — future work

## Repository Structure

```text
src/cube/
  cube.js                  # Main config: dbt integration, contextToGroups,
                           #   queryRewrite, access policies
  package.json             # @cubejs-backend/bigquery-driver + dev script
  package-lock.json
  .env.example             # Required env vars for local dev (committed)
  .gitignore               # excludes .env, node_modules, .cubestore
  model/
    cubes/                 # One YAML file per mart — populated in follow-up spec
    views/                 # Empty for now — populated in follow-up spec
  SETUP.md                 # Cube Cloud one-time setup + local dev guide
```

## Security Model

Three layers, all enforced in `cube.js` and cube YAML. No security configuration
exists in downstream tools — Cube is the single source of truth.

### Google Group Naming Convention

All Cube-relevant groups use a `cube-` prefix so `contextToGroups` can filter
them from a user's full group list without a mapping table.

**Scope groups** (control which rows a user can see):

```text
cube-network-detail          # all regions, row-level access
cube-network-summary         # all regions, aggregates only

cube-region-{region}-detail  # all schools in region, row-level
cube-region-{region}-summary # all schools in region, aggregates only

cube-school-{slug}-detail    # one school, row-level
cube-school-{slug}-summary   # one school, aggregates only
```

`{region}` matches `location_region` values from `dim_locations` (lowercased,
hyphenated). `{slug}` matches `location_abbreviation` from `dim_locations`.

A user with `-detail` access can see everything a `-summary` user can see, plus
individual rows. `cube-school-{slug}-summary` exists for users who should see
aggregated data only (e.g., a user from another school) — they do not need a
`-detail` group.

**Access groups** (control which columns or cubes a user can see):

```text
cube-access-student-data         # student-domain cubes visible
                                 #   (attendance, behavior, grades, assessments,
                                 #   surveys, etc.) — users without this group
                                 #   see no student cubes in schema introspection
cube-access-student-pii          # PII fields on student cubes
cube-access-staff-pii            # PII fields on staff cubes
cube-access-staff-compensation   # salary and pay rate fields on staff cubes
cube-access-staff-all            # bypass org-hierarchy filter — see all staff
                                 #   records, not just your reporting chain
```

**Groups are additive.** A user's effective permissions are the union of all
their `cube-*` groups — there is no role hierarchy to configure. Assign whatever
combination of scope and access groups matches what the person actually needs.
For example, a Newark Head of Schools with `cube-region-newark-detail` and
`cube-access-staff-all` sees all Newark staff (location scope from the first
group, org-hierarchy filter removed by the second) — but not staff in other
regions. Network-wide staff access requires `cube-network-detail`.

**Examples:**

| Role                     | Groups assigned                                                                  |
| ------------------------ | -------------------------------------------------------------------------------- |
| Newark AP (Bold Academy) | `cube-school-bold-detail`, `cube-region-newark-summary`                          |
| Newark Head of Schools   | `cube-region-newark-detail`, `cube-access-staff-all`                             |
| Network HR Director      | `cube-network-detail`, `cube-access-staff-compensation`, `cube-access-staff-all` |
| Finance analyst          | `cube-network-summary` (no `cube-access-student-data` — student cubes hidden)    |

### Layer 1 — Identity resolution (`contextToGroups`)

At request time, two lookups run in parallel, both cached 5 minutes per user:

1. **Google Group memberships** — calls Admin Directory API, filters to `cube-*`
   groups only
2. **Employee number** — lookup against `dim_staff` by email, used for
   org-hierarchy filtering on staff cubes

Locally, `CUBE_GROUP_MAP` env var replaces both lookups. The `contextToGroups`
function is `async`.

### Layer 2 — Row-level filtering (`queryRewrite`)

Applied to every query. Logic evaluated in priority order:

1. User has `cube-network-*` → no location filter
2. User has `cube-region-{region}-*` → filter by `location_region`
3. User has `cube-school-{slug}-*` → filter by `location_abbreviation`
4. No matching scope group → query returns empty (default deny)

**Detail vs summary:** The `-detail` and `-summary` group suffixes drive which
views a user can access. Detail views expose individual-row dimensions; summary
views expose only aggregated measures and school-level groupings. This is
enforced via `accessPolicy` on the views themselves (follow-up spec) — not by
`queryRewrite`. `queryRewrite` handles row-level location filtering only.

**Org-hierarchy filter (staff cubes only):** Applied in addition to location
scope unless the user has `cube-access-staff-all`:

```sql
WHERE employee_number IN (
  SELECT descendant_employee_number
  FROM kipptaf_marts.dim_staff_hierarchy
  WHERE ancestor_employee_number = {current_user_employee_number}
)
```

### Layer 3 — Column-level access policies (YAML)

Sensitive dimensions are marked with `accessPolicy` in their cube YAML:

- Salary, pay rate fields on staff cubes → requires
  `cube-access-staff-compensation`
- PII fields on student cubes → requires `cube-access-student-pii`
- PII fields on staff cubes → requires `cube-access-staff-pii`

Users without the required access group do not see those dimensions in any tool
— they are absent from schema introspection and query results. The specific PII
field list for each cube is enumerated during model YAML implementation.

Users without `cube-access-student-data` have all student-domain cubes excluded
from their query context entirely.

## `cube.js` Configuration

Four responsibilities:

**1. dbt Cloud metadata integration**

Cube fetches the compiled manifest from dbt Cloud project `211862` at startup
using `DBT_CLOUD_TOKEN`. Column descriptions, model descriptions, and types
populate Cube's schema automatically.

For local dev, Cube reads a locally generated manifest. Run
`uv run dbt compile --project-dir src/dbt/kipptaf` once on initial setup and
again only when dbt model definitions change (new columns, renamed models). If
you are only editing cube YAML files, the existing manifest stays valid. Cube
will query BigQuery correctly without an up-to-date manifest — you lose
auto-populated column descriptions but nothing else.

**2. `contextToGroups` — identity resolution**

Async function. Checks `CUBE_GROUP_MAP` first (local dev fallback). In Cloud
deployments, runs in parallel:

- Admin Directory API call filtered to `cube-*` groups, 5-minute in-memory cache
  per email
- `dim_staff` employee number lookup by email

**3. `queryRewrite` — row-level security**

Parses `cube-*` groups from the resolved context. Applies location and
org-hierarchy filters as described in the security model. Default deny if no
scope group matches. Users without `cube-access-student-data` have all
student-domain cubes removed from their query context before evaluation.

**4. `canSwitchSqlUser: () => true`**

Enables per-user SQL API connections so each user's session carries their own
security context rather than a shared service account. Required for Superset
impersonation (downstream integration, follow-up spec) — included now since
removing it later would be a breaking change.

## New dbt Model: `dim_staff_hierarchy`

**Location:** `src/dbt/kipptaf/models/marts/dimensions/dim_staff_hierarchy.sql`

**Purpose:** Transitive closure of the org chart. Used by `queryRewrite` to
filter staff cube results to a manager's reporting chain.

**Schema:**

```text
ancestor_employee_number    STRING   NOT NULL
descendant_employee_number  STRING   NOT NULL
depth                       INT64    NOT NULL
```

One row per (ancestor, descendant) pair at any depth, including self-referential
rows (`depth = 0`). Built recursively from `dim_staff.manager_employee_number`.
Refreshes on the standard marts cadence so org chart changes propagate
automatically.

`dim_staff_hierarchy` is not a Cube model — it is a small lookup table used only
as a filter subquery in `queryRewrite`.

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
6. Request domain-wide delegation for the `GOOGLE_DIRECTORY_SA_KEY` service
   account from Google Workspace admin — required for Admin Directory API access
   in Cloud deployments

## Local Development

**VS Code task** starts Cube Core with one click:

1. Runs `npm install` if `node_modules` is absent
2. Runs `npm run dev`
3. Cube Core Playground available at `localhost:4000`

**BigQuery auth** uses ADC (`gcloud auth application-default login`) — already
configured in the devcontainer. No service account key needed locally.

**Group simulation** — set `CUBE_GROUP_MAP` in your local `.env` to a JSON
string mapping your email to a list of `cube-*` groups. This bypasses both the
Directory API call and the `dim_staff` employee number lookup.

**Warning:** do not use the Cube Playground's built-in Models tab. In dev mode,
Cube treats it as a live editor and overwrites YAML files. Edit in VS Code only.

## Environment Variables

| Variable                        | Local dev                          | Cube Cloud                                     |
| ------------------------------- | ---------------------------------- | ---------------------------------------------- |
| `CUBEJS_DB_TYPE`                | `bigquery`                         | `bigquery`                                     |
| `CUBEJS_DB_BQ_PROJECT_ID`       | `teamster-332318`                  | `teamster-332318`                              |
| `CUBEJS_DB_BQ_CREDENTIALS`      | — (uses ADC)                       | `cube-bq-reader` SA key, base64-encoded        |
| `CUBEJS_API_SECRET`             | any string                         | random 64-char, unique per deployment          |
| `CUBEJS_DEV_MODE`               | `true`                             | omit                                           |
| `CUBEJS_CACHE_AND_QUEUE_DRIVER` | `memory`                           | omit (uses CubeStore)                          |
| `CUBE_GROUP_MAP`                | JSON string mapping email → groups | omit (uses Directory API)                      |
| `DBT_CLOUD_TOKEN`               | omit (uses local manifest)         | dbt Cloud service token, read-only             |
| `DBT_CLOUD_PROJECT_ID`          | omit                               | `211862`                                       |
| `GOOGLE_DIRECTORY_SA_KEY`       | omit                               | SA with domain-wide delegation, base64-encoded |

## Google Group Creation

Enumerating all required scope groups (one per region and school slug from
`dim_locations`) and assigning members is tracked as a separate issue scoped to
the IT admin team. This spec defines the naming convention and semantics — the
admin task is creating the groups in Workspace Admin and populating initial
membership.
