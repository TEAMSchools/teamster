# CLAUDE.md — `src/cube/`

Cube semantic layer. BigQuery driver; cubes read from `kipptaf_marts` tables
produced by [`src/dbt/kipptaf/`](../dbt/kipptaf/). Setup, env vars, and Cube
Cloud deployment: [`docs/guides/cube.md`](../../docs/guides/cube.md).

## Layout

```text
src/cube/
  cube.js                   # Auth, group resolution, queryRewrite, sql-user gating
  package.json              # Cube server + bigquery driver + googleapis
  .env.example              # Hook-blocked — Read/Grep return errors; ask user to inspect
  model/
    cubes/
      <domain>/<name>.yml   # Fact and dim cubes — private at cube level
      conformed/            # Shared dims joined from multiple fact cubes
    views/
      <domain>/<name>.yml   # Analyst-facing views — the only public surface
```

One cube or view per file. Filename matches `name:`. New cubes go under
`cubes/<domain>/`; cross-domain shared dims (dates, regions, locations, terms,
school_calendars) go in `cubes/conformed/`.

## Authoring conventions

- **Cubes private, views public.** Every cube YAML gets `public: false` at the
  cube level. Dimensions/measures use `public: true` only when meant to be
  exposed via a view. Never flip a cube to `public: true`.
- **Transformation lives in dbt, not cube.** Multi-table joins, window
  functions, and derived grains (SCD2 period-intersection / status spines)
  belong in a dbt mart read via `sql_table` — not inline cube `sql:`, which is
  for thin column/expression shaping only. (Cube's own dbt guidance and the
  `original_sql` pre-agg confirm this.)
- **Naming.** Cube `name:` always matches its filename, and neither carries the
  warehouse `dim_`/`fct_` prefix — the file `conformed/dates.yml` defines
  `name: dates` reading `sql_table: kipptaf_marts.dim_dates`. **Domain-prefix
  rule:** student-domain cubes start with `student` (`student_attendance`,
  `student_enrollments`, `students`); staff-domain cubes start with `staff`.
  This is an organizational convention only — RLS is no longer keyed off the
  cube-name prefix. Every view enforces access through its own `access_policy`
  matching a `securityContext` group (see View access policies below); a
  misnamed cube has no security consequence, but keep the convention so the
  domain is legible from the name. Conformed dims (`dates`, `locations`,
  `regions`, `terms`, `school_calendars`) are deliberately unprefixed — they
  carry no domain access tier. View names are `<domain>_<grain>`
  (`student_attendance_detail`, `student_attendance_summary`). `sql_table`
  always points at `kipptaf_marts.<table>` (the warehouse table keeps its
  `dim_`/`fct_` prefix) — cubes never read district datasets directly.
- **Joins use cube-reference syntax** (`{students.col} = {CUBE}.col`), not raw
  identifiers. Dim joins from facts set `relationship: many_to_one`.
- **Range/non-equi join predicates** (`BETWEEN`, `>=`) are valid in a join
  `sql:` (Cube custom-calendar recipe). `many_to_one` fan-trap protection trusts
  your declared `relationship` + `primary_key`, so any non-overlap invariant the
  join relies on must be test-enforced upstream in dbt.
- **Avoid diamond paths.** Two join paths to the same dim → resolve to one
  canonical path. Reach deeper dims by traversing the FK chain (e.g.
  `student_enrollments` and `student_attendance` both reach `locations` only via
  `student_enrollment_stints.locations` — no direct second join). Alternative
  resolutions: a compound join on the canonical path (see
  `student_attendance.yml` → `school_calendars`), or a degenerate FK with no
  declared join. Comment the choice.
- **Time dimensions** must cast to `TIMESTAMP` in the dim's `sql:`; joins from
  facts cast through (`CAST({CUBE}.date_key AS TIMESTAMP)`).
- **Hidden helper measures** prefix with `_` and set `public: false` (see
  `_sum_attendance_value` building blocks).
- **`meta.folders` is the only Cube-rendered `meta.*` key.** Put guidance in
  `description:`, not `meta.usage` / `meta.synonyms` / etc. — those land in
  `/v1/meta` but Cube Cloud and the chat agent don't read them.
- **Folders group dimensions only.** Cube Cloud separates measures natively;
  don't list measures under `members:`.
- **Folder member naming.** Bare for top-cube members; `<prefix>_<member>` for
  `prefix: true` joins, where `<prefix>` is the last `join_path` segment — so
  `regions_region_name` for
  `student_attendance.student_enrollments.locations.regions`.
- **Branch schema validation is manual.** Cube Cloud Staging Environments don't
  auto-create from pushes. Open Cube Cloud → Data Model → Dev Mode → add branch
  by name to spin up a per-branch staging instance.

## View access policies

Views own access entirely via `access_policy:` — RLS is Cube-native and
declarative, not injected server-side. `cube.js`'s `queryRewrite` carries none
of it (see `cube.js` security model below). Each policy matches one
scope-specific group emitted by `access.buildGroups`; a viewer holds exactly one
group per domain axis, so exactly one policy per view is ever active — no AND/OR
combination to reason about.

- **Student views** (detail = row-level with identifiers; summary = aggregate
  breakdowns): three policies, one per non-`none` `student_location_scope` —
  `student-region` (`row_level` on the region key), `student-school`
  (`row_level` on the school abbreviation), `student-network` (no `row_level` —
  every location). All three use `member_level: { includes: "*" }` — any viewer
  holding one of these groups sees every field on every student view, including
  PII. `none` scope → no group → default-deny (zero rows).
- **Staff views are split.** `staff_directory` (roster/employment/work-contact
  fields — no personal or sensitive data) has one open block:
  `member_level: { includes: "*" }` under `staff-directory`, no `row_level` —
  every resolved staff viewer gets this group. `staff_pii` (the six sensitive
  fields — `personal_email`, `personal_cell_phone`, `birth_date`,
  `gender_identity`, `race`, `is_hispanic` — plus the identity/remit keys needed
  to filter on) has one policy per `staff_pii_scope`: `staff-pii-all_in_scope`
  (`locations_abbreviation` ∩ `department_group` remit),
  `staff-pii-teaching_staff` (that remit +
  `job_function_code IN ('TEACH', 'TIR')`), `staff-pii-reporting_chain`
  (`staff_key IN reportee_staff_keys`),
  `staff-pii-reporting_chain_or_below_rank` (OR of the remit-plus-rank check and
  the chain-IN check). The location∩department remit is precomputed server-side
  into `securityContext.allowed_abbreviations` / `allowed_department_groups` —
  domain-agnostic, reused as-is when comp/observations/benefits views are built.
- **Forward-compatible staff tiers**: `staff-compensation`,
  `staff-observations`, `staff-benefits` are emitted by `buildGroups` when the
  corresponding `*_scope` column is non-`none`, but no view has an
  `access_policy` block for them yet. Wire them when those cubes/views are
  built.

**Authoring rule — `row_level.filters[].member` is a flat view-member name, not
a cube-qualified path.** A path (`locations.abbreviation`) fails to compile:
"Paths aren't allowed in the accessPolicy policy." The exposed name follows the
`prefix:` setting on the `includes:` block that surfaces it: `prefix: true` →
`<lastJoinPathSegment>_<member>` (e.g. `locations_abbreviation`,
`locations_region_key`); `prefix: false` → bare (`department_group`,
`staff_key`, `job_function_code`, `job_function_level`, and — in the student
assessment views, which join `locations` unprefixed — bare
`abbreviation`/`region_key`). Check the view's own `includes:` blocks for the
`prefix:` setting before writing a filter; don't assume it matches another view.

**Interpolation forms.** An array value (`IN`) uses the UNBRACKETED string form:
`values: "{ securityContext.allowed_abbreviations }"`. A single scalar uses the
bracketed form: `values: ["{ securityContext.region_key }"]`.
`operator: equals` + array value compiles to SQL `IN`; an empty array (e.g. an
allow-list computed to nothing) compiles to `IN ()` — zero rows, fail-closed.

**Scope selection is group-based, not `conditions.if`-based.** `conditions.if`
only compiles a bare truthy reference (`if: "{ userAttributes.x }"`) — a `==`
comparison does not compile (Task 1 spike finding). That's why `buildGroups`
emits one scope-specific group per enum value instead of a single group gated by
a `conditions.if` branch.

When adding a sensitive staff field, decide PII status per project CLAUDE.md
FERPA guidance. If PII, add it to `staff_pii.yml` (not `staff_directory.yml`)
and wire its per-field scope in `access.js`'s `STAFF_SENSITIVE_SCOPE_BY_MEMBER`.
Student views have no PII split — any scope-specific `student-*` group sees
every field.

## `cube.js` security model

Default-deny, HR-derived, group-driven. Read [`cube.js`](cube.js) and
[`access.js`](access.js) before modifying. All pure access helpers live in
`access.js` (unit-tested); `cube.js` owns BigQuery reads, caching, and the two
auth hooks. RLS itself lives entirely in per-view `access_policy` (see View
access policies above) — `queryRewrite` retains only the snapshot-anchor guard.

- **`resolveAccess(email)`** is the shared identity-resolution function, called
  from both auth hooks below (not from `contextToGroups`). It reads one row from
  `dim_staff_cube_access` (per-field scope enums) plus the caller's transitive
  reportees from `dim_staff_reporting_chain`, loads the global "universes"
  (`loadUniverses`: every location abbreviation+region, every distinct
  `department_group`), computes `allowed_abbreviations` /
  `allowed_department_groups` via `access.computeAllowedAbbreviations` /
  `computeAllowedDepartmentGroups`, and returns
  `access.buildSecurityContext(...)`. Per-email cache and the global universe
  cache both expire at next midnight ET. Wrapped in try/catch — any BigQuery
  error fails closed to an empty (default-deny) context rather than throwing.
- **`checkAuth` (REST/MCP)** receives the RAW bearer token STRING — a custom
  `checkAuth` replaces Cube's default JWT verify+decode. It verifies the HS256
  signature against `CUBEJS_API_SECRET` itself, reads the `email` claim, and
  sets `req.securityContext = await resolveAccess(email)`. No/invalid token →
  `jwt.verify` throws → Cube rejects the request; no `Authorization` header
  resolves to the empty default-deny context. Auth is skipped entirely in Cube
  developer mode (`CUBEJS_DEV_MODE=true`) — `checkAuth` only runs with dev mode
  off / `NODE_ENV=production`.
- **`checkSqlAuth` (SQL API)** returns
  `{ password: process.env.CUBEJS_SQL_PASSWORD, securityContext }` — Cube
  validates the presented password against the RETURNED one, so returning `null`
  rejects every connection. Identity is resolved from the connecting `user` (or
  `CUBE_SQL_DEV_EMAIL` outside prod); the presented `password` is not compared
  and is absent entirely on `SET USER` re-auth flows.
- **`contextToGroups`** is now a one-line read: `securityContext?.groups ?? []`
  — the BigQuery reads and all group-building logic moved to `resolveAccess` /
  `access.buildGroups`.
- **Group taxonomy (`access.buildGroups`)**: `student-<student_location_scope>`
  (`student-region` / `student-school` / `student-network`); `staff-directory`
  (always, for any resolved row); `staff-pii-<staff_pii_scope>`
  (`staff-pii-all_in_scope` / `-reporting_chain` /
  `-reporting_chain_or_below_rank` / `-teaching_staff`); plus forward-compat
  flat `staff-compensation` / `-observations` / `-benefits` (emitted per
  non-`none` scope; no view consumes them yet). `none` on any axis → no group
  for that axis → default-deny on the views gated by it.
- **`SNAPSHOT_CUBES` / `SNAPSHOT_MEASURE_STEMS` / `SNAPSHOT_ANCHOR_OVERRIDES`.**
  For cubes built on fact tables with cumulative daily-status flags (values
  re-stamped on every row — overcounts without a point-in-time anchor), or a
  `count_distinct` over a daily grain (a member appearing on N days counts N
  without an anchor). `queryRewrite` auto-injects `is_latest_record`,
  `is_month_end_record`, or `is_week_end_record` depending on query granularity.
  To add a new domain: append the cube `name:` to `SNAPSHOT_CUBES` and add its
  snapshot measure name stems under that **same cube key** in
  `SNAPSHOT_MEASURE_STEMS` (a per-cube map — stems are NOT shared across cubes,
  so e.g. `count_students` is a snapshot stem for `student_enrollments` but not
  `student_attendance`, whose `count_students` is stint-keyed and
  additive-safe). The cube must expose `is_latest_record`,
  `is_month_end_record`, and `is_week_end_record` dimensions. To change a cube's
  no-granularity default anchor (e.g. enrollment uses `is_current_record`, the
  per-school period-end-as-of-now flag, instead of the `is_latest_record`
  default), add a per-cube entry to `SNAPSHOT_ANCHOR_OVERRIDES`. **The injected
  anchor is a query-level filter, so it constrains every measure in the query**
  — do not put an additive measure (e.g. `avg_daily_attendance`) and a guarded
  snapshot measure in the same request, or the additive one is wrongly anchored
  ([#4160](https://github.com/TEAMSchools/teamster/issues/4160)).
- **`access_policy` blocks, it does not strip.** When a user requests a member
  their tier excludes, Cube denies the whole query — it does not silently drop
  the column and return the rest. BI tools connected via the SQL API (Superset)
  avoid this because the field list is filtered per-user at connection time. In
  Tableau, a workbook published by someone with broader access may error at
  query time for viewers with narrower access. A `queryRewrite` member-strip
  approach (detect and remove inaccessible members before execution) is tracked
  in [#4268](https://github.com/TEAMSchools/teamster/issues/4268).
- **`canSwitchSqlUser`** only allows the SQL super-user to impersonate
  `@apps.teamschools.org` accounts (Superset integration). Do not broaden the
  suffix check.

## MCP access (cube)

The `cube` MCP wraps Cube Cloud's REST API. Auth path that works:

- Mint HS256 JWT locally per request from `CUBE_API_SECRET` (1P:
  `op://Data Team/Cube Cloud REST API/credential`).
- The **entire JWT payload is `securityContext`** — top-level `email` claim
  flows into `cube.js`'s `checkAuth`, which resolves it via `resolveAccess` into
  the enriched `securityContext` every view's `access_policy` reads. Not nested
  under `u`/`securityContext`/`userContext`.
- `Authorization` header is raw token — **no `Bearer` prefix** (Cube Cloud
  Metadata API exception per docs is a footnote, not the norm).
- Cube Cloud "Personal Core Data API Token" (PAT) returns 403 against `/meta`
  even with the right format — labeled "for SQL API connections" and behaves
  that way. JWT-from-secret is the only reliable path.
- Cube SQL API `SET sql_user TO '...'` does NOT persist across MCP `execute_sql`
  calls (each call = fresh Postgres connection). REST is the right abstraction
  for stateless tool calls.

## Diagnostic surfaces

- `/meta` returning `{"cubes": []}` ≠ model not deployed. With no matching
  `cube-*` group, access policies hide every cube — looks identical to an
  unpopulated branch. Compile a query via `/sql` to verify model presence before
  assuming the deployment is empty.
- `/sql` compiles queries even against `public: false` members; `/load` enforces
  hiding. A `/load` 500 "You requested hidden member" with `/sql` succeeding =
  security-context delta, not a schema bug.
- `access_policy` default-deny (no `securityContext` group matches any policy on
  the view) manifests as `WHERE (1 = 0)` plus `rlsAccessDenied` in
  `sortedDimensions` of `/sql` output — same diagnostic signature as the old
  `queryRewrite`-based deny.
- **Branch endpoints**: `/staging/<branch>/cubejs-api/v1` is the per-branch
  staging endpoint (stable, redeploys on push).
  `/user/<urlencoded-email>/<id>/cubejs-api/v1` is the per-developer Dev Mode
  endpoint. Only Dev Mode surfaces server `console.log` in the playground logs
  panel — staging has no log UI. Debug `cube.js` code paths on Dev Mode.
- **Branch staging configuration doesn't fully inherit from production.** Before
  diagnosing API errors on a branch staging env, verify the BigQuery connection
  variables (`CUBEJS_DB_TYPE`, `CUBEJS_DB_BQ_PROJECT_ID`,
  `CUBEJS_DB_BQ_CREDENTIALS`) are set on that environment. Also verify
  `dim_staff_cube_access` and `dim_staff_reporting_chain` exist in prod
  `kipptaf_marts` — branch staging reads prod, so identity resolution fails
  silently (default deny) if those models haven't been deployed yet.
- **Validate a cube against a Tableau dashboard from the workbook extract**:
  `unzip <workbook>.twbx`, then query `Data/Extracts/*.hyper` with
  `uv run --with tableauhyperapi python` (the data table is
  `"Extract"."Extract"`). Reproduce a Tableau categorical group (e.g. a
  Subject-Area "Literacy" bin) from its `<calculation class='categorical-bin'>`
  `<value>` list in the `.twb`. Cube side = the PR-branch fact joined to prod
  dims with the same filters.

## Jinja in cube YAML

Cube data models support Jinja macros and `{% set %}` variables for SQL snippet
reuse. Before factoring with Jinja, check whether a dbt-derived dim column (e.g.
`dates.is_current_academic_year` from `{{ var("current_academic_year") }}`) is a
better fit — keeps Cube and dbt in lockstep.

## Measure filters and joined-cube references

Measure `filters:` SQL substitutes dimension expressions at compile time,
including `{other_cube.member}` references to joined cubes. Transitive joins
auto-resolve; don't add redundant intermediate-hop joins. "Column not found" in
a filter usually means the dimension SQL references a bare column on the
filtering cube — route through `{joined_cube.col}` instead.

## Cube can't classify an aggregate by a data-driven range

Cube has no non-equi/range (BETWEEN) join, and a dimension can't reference a
measure (only surface one via `sub_query`). Mapping an aggregated value to a
band via per-row threshold rows (e.g. percent_correct → performance band) can't
be expressed in Cube — materialize that classification upstream in dbt.

## Testing Cube measures backed by new dbt columns

When a cube YAML references a column added in this branch (not yet in
`kipptaf_marts`), the playground errors: "Name X not found inside Y". To test
before merge:

1. Build in your dev schema:
   `uv run dbt run --select <model> --project-dir src/dbt/kipptaf --target dev`
   → creates `zz_<username>_kipptaf_marts.<model>`
2. Temporarily redirect the cube YAML to the dev schema — do NOT commit or push:
   - For `sql_table` cubes: change `sql_table: kipptaf_marts.<table>` to
     `sql_table: zz_<username>_kipptaf_marts.<table>`
   - For inline `sql:` cubes (e.g. `staff`, which LEFT JOINs
     `dim_staff_cube_access`): change the dataset reference(s) inside the `sql:`
     block. If `cube.js` also reads the same table directly (e.g.
     `dim_staff_cube_access` for identity resolution), redirect those queries
     too.
3. Test in the local dev server — launch the **`Cube: Dev Server`** VS Code task
   (`.vscode/tasks.json`; installs `src/cube/node_modules` if missing, then
   `npm --prefix src/cube run dev`). Hot-reloads on file save, no push required.
   Claude can't run it (long-running server) — ask the user to start the task
   and report back. Or commit+push for Cube Cloud Dev Mode.
4. Revert all dev-schema redirects to `kipptaf_marts.<table>` before committing.
   Verify with `grep -r "zz_" src/cube/` before pushing.

For **snowflake sub-dims** (cubes joined one-to-one from a parent), swap the
dataset reference on the sub-dim cube file, not the parent.

The security hook flags `zz_*` schemas as an access-control regression —
expected if you do commit the temporary change; acknowledge and revert.

**`zz_*` redirect — never `git add` the whole cubes/ dir while it's live.** When
a dev-schema redirect is in the working tree, staging with `git add -A`,
`git add .`, or `git add src/cube/model/cubes/` accidentally commits the
redirect. Name files explicitly in every `git add` while any cube YAML is
redirected.

**Never `bq cp` a dev-schema table into `kipptaf_marts` to unblock testing.**
`kipptaf_marts` is the live prod dataset read by all dashboards, the Cube
semantic layer, and dbt downstream models. Overwriting a mart table corrupts
prod for all consumers with no rollback path. Use the dev-schema redirect above
instead.

## School weeks vs ISO weeks

PowerSchool's per-school school week (`week_start_monday`) is NOT a clean
Monday-Sunday grid — weeks split at month/term boundaries (~14% of calendar days
diverge from ISO Monday). Both topline surfaces key on school weeks:
`int_topline__ada_running_weekly` (attendance) and
`int_extracts__student_enrollments_weeks` (enrollment) both group by
`week_start_monday`. Use `dim_dates.school_week_start_date` (same values, routed
cleanly via the join) rather than a raw fact column — Cube can throw "not found"
on a `DATE` fact column cast to `TIMESTAMP` in a BigQuery view.

**Snapshot guard drives the week period off `dates_school_week_start_date`
grouping, not Cube's native `granularity: "week"` (ISO).** The guard detects a
weekly trend when any query member's last dotted segment equals
`dates_school_week_start_date`; ISO `granularity: "week"` throws for snapshot
measures. `_week_end` named measures require this grouping.

## `prefix: true` join member names

A member inside a `prefix: true` includes block is exposed with the last
`join_path` segment prepended: `school_week_start_date` under
`join_path: student_enrollments.dates` (prefix: true) surfaces as
`dates_school_week_start_date`. A same-named fact-level dimension alongside the
join creates ambiguity Cube can't resolve at query time. Route via the join when
`dim_dates` carries the same value — avoids the compile error and the redundant
fact column.

## Operational notes

- **Never use the Cube Playground Models tab.** It overwrites YAML in
  `model/cubes/` and `model/views/` with auto-generated content, discarding
  hand-authored definitions.
- **No manual deploy command.** Production redeploys are triggered by merges to
  `main` in Cube Cloud; do not propose a deploy step.
