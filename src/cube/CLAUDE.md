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
  `queryRewrite`'s `isStudentMember`/`isStaffMember` access gating keys off
  these prefixes, so a misnamed domain cube silently loses its access guard.
  Conformed dims (`dates`, `locations`, `regions`, `terms`, `school_calendars`)
  are deliberately unprefixed — they carry no domain access tier. View names are
  `<domain>_<grain>` (`student_attendance_detail`,
  `student_attendance_summary`). `sql_table` always points at
  `kipptaf_marts.<table>` (the warehouse table keeps its `dim_`/`fct_` prefix) —
  cubes never read district datasets directly.
- **Joins use cube-reference syntax** (`{students.col} = {CUBE}.col`), not raw
  identifiers. Dim joins from facts set `relationship: many_to_one`.
- **Range/non-equi join predicates** (`BETWEEN`, `>=`) are valid in a join
  `sql:` (Cube custom-calendar recipe). `many_to_one` fan-trap protection trusts
  your declared `relationship` + `primary_key`, so any non-overlap invariant the
  join relies on must be test-enforced upstream in dbt.
- **Avoid diamond paths.** Two join paths to the same dim → either a compound
  join on the canonical path (see `student_attendance.yml` → `school_calendars`)
  or a degenerate FK with no declared join (see
  `student_enrollments.location_key`). Comment the choice.
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

Views own access via `access_policy:`. Two patterns:

- **Detail views** (row-level, contain student identifiers): two policy blocks —
  `cube-access-student-data` with `member_level.excludes` listing PII fields
  (names, DOB, all `*_student_identifier`, `salesforce_contact_id`), and
  `cube-access-student-pii` with `includes: "*"`.
- **Summary views** (no direct identifiers, demographic breakdowns only): single
  `cube-access-student-data` block with `includes: "*"`. Add a comment
  explaining why no PII tier is needed.

When adding a field to a detail view, decide PII status per project CLAUDE.md
FERPA guidance. If PII, add it to the `excludes` list under the
`cube-access-student-data` policy block.

## `cube.js` security model

Default-deny, group-driven. Read [`cube.js`](cube.js) before modifying.

- **`contextToGroups`** resolves the requester's email to `cube-*` Google
  Workspace groups via the Admin Directory API, cached until next midnight ET.
  `CUBE_GROUP_MAP` (local dev only, gated on `NODE_ENV !== "production"`) is the
  sole bypass.
- **Group membership is direct-only.** Admin Directory API's
  `groups.list({userKey})` returns direct memberships; nested `cube-*` groups
  don't transitively resolve. Flat-enroll users in every `cube-*` group they
  need (scope tier + `cube-access-student-data`, plus `cube-access-staff-all`
  for staff cubes).
- **Cloud Identity `searchTransitiveGroups` is edition-gated** (Workspace
  Enterprise / Education Plus / Cloud Identity Premium). On lower editions it
  returns `INVALID_ARGUMENT`, not `PERMISSION_DENIED` — don't propose it as a
  transitive-resolution fix without verifying the tenant's edition.
- **`queryRewrite`** enforces three filters:
  - Strips student-domain dims/measures (members where `isStudentMember` is
    true) for users without `cube-access-student-data`.
  - Adds a `locations` filter based on the highest-priority scope group: network
    (no filter) → region (`region_key`) → school (`abbreviation`). No scope
    group → empty `IN ()` filter (default deny).
  - For queries touching a staff-domain cube (`isStaffMember`), injects the
    `staff.reporting_chain` segment unless the user has `cube-access-staff-all`.
- **`isStudentMember` / `isStaffMember` prefix helpers.** Domain gating is
  derived from the cube-name prefix (`student*` / `staff*`), not a static array
  — a query member is `<cube_name>.<member>`, so the cube name is the prefix. A
  new domain cube needs no `cube.js` change as long as it follows the
  domain-prefix naming rule above. A domain cube misnamed off-prefix silently
  loses its guard.
- **`SNAPSHOT_CUBES` / `SNAPSHOT_MEASURE_STEMS` arrays.** For cubes built on
  fact tables with cumulative daily-status flags (values re-stamped on every row
  — overcounts without a point-in-time anchor). `queryRewrite` auto-injects
  `is_latest_record`, `is_month_end_record`, or `is_week_end_record` depending
  on query granularity. To add a new domain: append the cube `name:` to
  `SNAPSHOT_CUBES` and its snapshot measure name stems (e.g.
  `"chronically_absent"`) to `SNAPSHOT_MEASURE_STEMS`. The cube must expose
  `is_latest_record`, `is_month_end_record`, and `is_week_end_record`
  dimensions.
- **`canSwitchSqlUser`** only allows the SQL super-user to impersonate
  `@apps.teamschools.org` accounts (Superset integration). Do not broaden the
  suffix check.

## MCP access (cube)

The `cube` MCP wraps Cube Cloud's REST API. Auth path that works:

- Mint HS256 JWT locally per request from `CUBE_API_SECRET` (1P:
  `op://Data Team/Cube Cloud REST API/credential`).
- The **entire JWT payload is `securityContext`** — top-level `email` claim
  flows into `cube.js`'s `contextToGroups`. Not nested under
  `u`/`securityContext`/`userContext`.
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
- `queryRewrite` default-deny manifests as `WHERE (1 = 0)` plus
  `rlsAccessDenied` in `sortedDimensions` of `/sql` output.
- **Branch endpoints**: `/staging/<branch>/cubejs-api/v1` is the per-branch
  staging endpoint (stable, redeploys on push).
  `/user/<urlencoded-email>/<id>/cubejs-api/v1` is the per-developer Dev Mode
  endpoint. Only Dev Mode surfaces server `console.log` in the playground logs
  panel — staging has no log UI. Debug `cube.js` code paths on Dev Mode.
- **Branch staging configuration doesn't fully inherit from production.** Before
  diagnosing API errors on a branch staging env, verify
  `GOOGLE_DIRECTORY_SA_KEY` / `GOOGLE_DIRECTORY_SA_SUBJECT` (and any other
  required secrets) are set on that environment.

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
2. Temporarily change `sql_table` in the cube YAML to
   `zz_<username>_kipptaf_marts.<table>` — do NOT commit or push
3. Test in local `npm run dev` from `src/cube/` (hot-reloads on file save, no
   push required); or commit+push for Cube Cloud Dev Mode
4. Revert `sql_table` to `kipptaf_marts.<table>` before committing

For **snowflake sub-dims** (cubes joined one-to-one from a parent), swap
`sql_table` on the sub-dim cube file, not the parent. The parent's `sql_table`
stays pointed at prod; only the new sub-dim needs redirecting.

The security hook flags `zz_*` schemas as an access-control regression —
expected if you do commit the temporary change; acknowledge and revert.

## Operational notes

- **Never use the Cube Playground Models tab.** It overwrites YAML in
  `model/cubes/` and `model/views/` with auto-generated content, discarding
  hand-authored definitions.
- **No manual deploy command.** Production redeploys are triggered by merges to
  `main` in Cube Cloud; do not propose a deploy step.
