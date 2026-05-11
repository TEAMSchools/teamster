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
  # setup guide moved to docs/guides/cube.md
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

`{region}` matches `region_key` values from `dim_locations` (lowercased,
hyphenated). `{slug}` matches `abbreviation` from `dim_locations`.

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

At request time, `contextToGroups` calls the Admin Directory API using
`securityContext.email`, filters the result to `cube-*` groups only, and returns
the group list. Results are cached until midnight Eastern time per email.

Locally, `CUBE_GROUP_MAP` env var replaces the Directory API call. The
`contextToGroups` function is `async`.

### Layer 2 — Row-level filtering (`queryRewrite`)

Applied to every query. Logic evaluated in priority order:

1. User has `cube-network-*` → no location filter
2. User has `cube-region-{region}-*` → filter by `region_key` (FK on
   `dim_locations`)
3. User has `cube-school-{slug}-*` → filter by `abbreviation` (on
   `dim_locations`)
4. No matching scope group → query returns empty (default deny)

**Detail vs summary:** The `-detail` and `-summary` group suffixes drive which
views a user can access. Detail views expose individual-row dimensions; summary
views expose only aggregated measures and school-level groupings. This is
enforced via `accessPolicy` on the views themselves (follow-up spec) — not by
`queryRewrite`. `queryRewrite` handles row-level location filtering only.

**Org-hierarchy filter (staff cubes only):** Applied in addition to location
scope unless the user has `cube-access-staff-all`. Implemented as a
`reporting_chain` segment on each staff cube (YAML implementation spec) —
`queryRewrite` adds the segment name to the query.

The segment approach is intentional: Cube's REST API filter operators (`equals`,
`contains`, etc.) do not accept SQL subqueries, and pre-fetching the reporting
chain in `queryRewrite` would require a separate round-trip to BigQuery before
the real query runs — and would bloat the filter with a long
`IN (key1, key2, ...)` list for managers with large teams. Instead, the segment
SQL is part of the `WHERE` clause Cube hands to BigQuery, so the subquery
executes as a single BigQuery operation. Cube templates in
`SECURITY_CONTEXT.email` at query time and never touches the hierarchy data
itself.

```yaml
segments:
  - name: reporting_chain
    sql: >
      {staff_key} IN (
        SELECT h.descendant_staff_key
        FROM kipptaf_marts.bridge_staff_hierarchy h
        JOIN kipptaf_marts.dim_staff s
          ON s.staff_key = h.ancestor_staff_key
        WHERE s.google_email = '{SECURITY_CONTEXT.email}'
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

## Authentication and Identity Flow

Cube never handles Google OAuth directly. User identity enters Cube's
`securityContext` via a signed JWT — the downstream tool is responsible for
minting it using the shared `CUBEJS_API_SECRET`. The flow differs by tool type.

### REST/GraphQL API path (Streamlit and future integrations)

1. User logs into the app via Google OAuth
2. App backend receives the user's Google identity
3. App backend signs a Cube JWT using `CUBEJS_API_SECRET` with
   `{ "email": "user@apps.teamschools.org" }` in the payload
4. App includes the JWT in the `Authorization` header on every Cube API request
5. Cube decodes the JWT — `securityContext.email` is available to
   `contextToGroups` and `queryRewrite` for the duration of the request

### SQL API path (Superset)

Superset connects to Cube via the PostgreSQL wire protocol as a shared service
account rather than as individual users. Per-user security context is
established via SQL user switching on each query.

1. Superset connects to Cube's SQL API as `cube-superset-service` (credentials
   set via `CUBEJS_SQL_SUPER_USER`)
2. For each end-user query, Superset issues
   `SET ROLE 'user@apps.teamschools.org'`
3. Cube calls
   `canSwitchSqlUser('cube-superset-service', 'user@apps.teamschools.org')` —
   passes only if `current_user === 'cube-superset-service'` and
   `new_user.endsWith('@apps.teamschools.org')`; any other caller is blocked
4. The switched user's email becomes `securityContext.email` for that query
5. `contextToGroups` and `queryRewrite` run against the end-user's identity, not
   the service account's — every row and column filter applies as if the user
   queried Cube directly

### What `securityContext.email` drives

| Hook              | How it uses email                                                           |
| ----------------- | --------------------------------------------------------------------------- |
| `contextToGroups` | Key for Google Directory API call; key for midnight-Eastern in-memory cache |
| `queryRewrite`    | Passed to `SECURITY_CONTEXT.email` in the `reporting_chain` segment SQL     |

## `cube.js` Configuration

Four responsibilities:

### 1. dbt Cloud metadata integration

dbt Cloud integration is configured in the **Cube Cloud UI** (Settings →
Integrations → dbt Cloud) — no `cube.js` code is required. Cube fetches the
compiled manifest from dbt Cloud project `211862` automatically. Column
descriptions, model descriptions, types, and PK/FK relationships populate Cube's
schema from the manifest. The `primary_key` and `foreign_key` constraints added
to every mart in PR #3714 are surfaced in `manifest.json` as machine-readable
join metadata — Cube uses these to discover join paths between cubes without
manual YAML configuration.

For local dev, Cube reads a locally generated manifest. Run
`uv run dbt compile --project-dir src/dbt/kipptaf` once on initial setup and
again only when dbt model definitions change (new columns, renamed models). If
you are only editing cube YAML files, the existing manifest stays valid. Cube
will query BigQuery correctly without an up-to-date manifest — you lose
auto-populated column descriptions but nothing else.

### 2. `contextToGroups` — identity resolution

Async function. Checks `CUBE_GROUP_MAP` first (local dev fallback). In Cloud
deployments, calls the Admin Directory API using `securityContext.email`,
filters to `cube-*` groups, and caches the result until midnight Eastern per
email. Group membership changes are not expected mid-day.

### 3. `queryRewrite` — row-level security

Parses `cube-*` groups from the resolved context. Applies location and
org-hierarchy filters as described in the security model. Default deny if no
scope group matches. Users without `cube-access-student-data` have all
student-domain cubes removed from their query context before evaluation.

### 4. `canSwitchSqlUser`

Enables per-user SQL API connections so each user's session carries their own
security context rather than a shared service account. Required for Superset
impersonation (downstream integration, follow-up spec) — included now since
removing it later would be a breaking change.

Scoped to the Superset service account only — any other SQL API user is blocked
from switching:

```javascript
canSwitchSqlUser: (current_user, new_user) =>
  current_user === process.env.CUBEJS_SQL_SUPER_USER &&
  new_user.endsWith("@apps.teamschools.org");
```

## New dbt Model: `bridge_staff_hierarchy`

**Location:** `src/dbt/kipptaf/models/marts/bridges/bridge_staff_hierarchy.sql`

**Purpose:** Transitive closure of the org chart. Used by `queryRewrite` to
filter staff cube results to a manager's reporting chain.

**Schema:**

```text
ancestor_staff_key    STRING   NOT NULL
descendant_staff_key  STRING   NOT NULL
depth                 INT64    NOT NULL
```

One row per (ancestor, descendant) pair at any depth, including self-referential
rows (`depth = 0`). Built recursively from the reporting relationship in
`dim_work_assignment_reporting_relationships`. Refreshes on the standard marts
cadence so org chart changes propagate automatically.

`bridge_staff_hierarchy` is not a Cube model — it is a small lookup table used
only as a filter subquery in `queryRewrite`.

!!! warning "Prerequisite for staff cubes" Before staff cubes (`dim_staff`,
`fct_staff_attrition`, etc.) can be added to the Cube semantic layer,
`bridge_staff_hierarchy` must return correct depth-1+ rows. This requires fixing
`dim_staff_work_assignments.staff_key`, which is currently `NULL` for all rows
in production due to an OID vs. worker ID join mismatch in its upstream
intermediate model. Tracked in
[#3729](https://github.com/TEAMSchools/teamster/issues/3729).

## Cube Cloud Setup (one-time)

Performed in the Cube Cloud UI:

1. Connect `TEAMSchools/teamster` GitHub repo
2. Set Cube project path to `src/cube/`
3. Set production branch to `main` — merges trigger automatic redeploy
4. Main deployment type: **Development Instance** for now; switch to
   **Production Cluster** before connecting downstream tools so queries don't
   hit a cold start on an idle deployment
5. Set environment variables (never committed to repo)
6. Request domain-wide delegation for the `GOOGLE_DIRECTORY_SA_KEY` service
   account from Google Workspace admin — required for Admin Directory API access
   in Cloud deployments

Staging environments are per-branch — switching to a branch in Cube Cloud
activates an isolated staging environment with its own API endpoints. Multiple
branches can have active staging environments simultaneously. Environments
suspend after 10 minutes of inactivity; toggle **always active** in Settings →
Staging Environments to keep a branch live for extended stakeholder review.

## Local Development

**VS Code task** starts Cube Core with one click:

1. Runs `npm install` if `node_modules` is absent
2. Runs `npm run dev`
3. Cube Core Playground available at `localhost:4000`

**BigQuery auth** uses ADC (`gcloud auth application-default login`) — already
configured in the devcontainer. No service account key needed locally.

**Group simulation** — set `CUBE_GROUP_MAP` in your local `.env` to a JSON
string mapping your email to a list of `cube-*` groups. This bypasses the
Directory API call.

**Warning:** do not use the Cube Playground's built-in Models tab. In dev mode,
Cube treats it as a live editor and overwrites YAML files. Edit in VS Code only.

## Environment Variables

| Variable                        | Local dev                          | Cube Cloud                                     |
| ------------------------------- | ---------------------------------- | ---------------------------------------------- |
| `CUBEJS_DB_TYPE`                | `bigquery`                         | `bigquery`                                     |
| `CUBEJS_DB_BQ_PROJECT_ID`       | `teamster-332318`                  | `teamster-332318`                              |
| `CUBEJS_DB_BQ_CREDENTIALS`      | — (uses ADC)                       | `cube-bq-reader` SA key, base64-encoded        |
| `CUBEJS_API_SECRET`             | any string                         | auto-generated on deployment creation          |
| `CUBEJS_DEV_MODE`               | `true`                             | omit                                           |
| `CUBEJS_CACHE_AND_QUEUE_DRIVER` | `memory`                           | omit (uses CubeStore)                          |
| `CUBE_GROUP_MAP`                | JSON string mapping email → groups | omit (uses Directory API)                      |
| `DBT_CLOUD_TOKEN`               | omit (uses local manifest)         | dbt Cloud service token, read-only             |
| `DBT_CLOUD_PROJECT_ID`          | omit                               | `211862`                                       |
| `GOOGLE_DIRECTORY_SA_KEY`       | omit                               | SA with domain-wide delegation, base64-encoded |
| `CUBEJS_SQL_SUPER_USER`         | omit                               | `cube-superset-service`                        |

## Google Group Creation

Enumerating all required scope groups (one per region and school slug from
`dim_locations`) and assigning members is tracked as a separate issue scoped to
the IT admin team. This spec defines the naming convention and semantics — the
admin task is creating the groups in Workspace Admin and populating initial
membership.
