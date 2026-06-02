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
- **Naming.** Cube names follow the convention in the model YAML spec: student
  cubes start with `student_`, staff cubes with `staff_`, conformed dims use
  bare business names (`dates`, `locations`, `regions`, `terms`,
  `school_calendars`). View names are `<domain>_<grain>`
  (`student_attendance_detail`, `student_attendance_summary`). `sql_table`
  always points at `kipptaf_marts.<table>` — cubes never read district datasets
  directly.
- **Joins use cube-reference syntax** (`{dim_x.col} = {CUBE}.col`), not raw
  identifiers. Dim joins from facts set `relationship: many_to_one`.
- **Avoid diamond paths.** Two join paths to the same dim → either a compound
  join on the canonical path (see `attendance.yml` → `dim_school_calendars`) or
  a degenerate FK with no declared join (see
  `dim_student_enrollments.location_key`). Comment the choice.
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
  `dim_regions_region_name` for the two-hop
  `attendance.dim_locations.dim_regions`.
- **Branch schema validation is manual.** Cube Cloud Staging Environments don't
  auto-create from pushes. Open Cube Cloud → Data Model → Dev Mode → add branch
  by name to spin up a per-branch staging instance.

## View access policies

Views own access via `access_policy:`. The base gate uses synthetic groups
emitted by `withSyntheticGroups` in `cube.js` — `detail-access` (any user with a
`*-detail` scope group) and `summary-access` (any user with a `*-detail` or
`*-summary` scope group). PII is a second, independent layer.

- **Detail views** (row-level, may contain identifiers): `detail-access` block
  with PII fields in `excludes:`; then a PII-group block
  (`cube-access-student-pii` or `cube-access-staff-pii`) with `includes: "*"` to
  restore those fields.
- **Summary views** (no direct identifiers, demographic breakdowns only): single
  `summary-access` block with `includes: "*"`. Add a comment explaining why no
  PII tier is needed.
- **Compensation fields**: gated by `cube-access-staff-compensation` — a third
  block alongside `detail-access` and `cube-access-staff-pii` in staff views.

When adding a field to a detail view, decide PII status per project CLAUDE.md
FERPA guidance. If PII, add it to the `excludes` list under the `detail-access`
block.

## PII tagging and dimension descriptions

**PII flags — first pass per cube:** Before writing any cube's dimensions, open
the source dbt model's property YAML and grep for `contains_pii: true`. For
every column flagged, add `meta: {pii: true}` to the Cube dimension. Do this on
the first pass — do not defer it.

**`dim_staff` gap:** `dim_staff` does NOT have `contains_pii: true` tags in dbt,
despite carrying direct identifiers (name, DOB, emails, phone, AD username). Use
the spec's explicit PII list for staff dimensions: `full_name`, `first_name`,
`last_name`, `birth_date`, `work_email`, `google_email`, `personal_email`,
`personal_cell_phone`, `active_directory_username`, `staff_unique_id`. All
require `meta: {pii: true}`. Compensation fields (`annual_wage`, `hourly_wage`,
`daily_rate`, `period_rate`) also carry `meta: {pii: true}`.

**Dimension descriptions:** Metadata sync (#3764) is not yet live. Copy
`description:` from the source dbt model's property YAML when writing each
dimension. If the dbt column has no description, omit the field. When sync ships
it will populate missing descriptions and may overwrite hand-authored values.
Measure `description:` fields must always be hand-authored (no dbt equivalent).
View-level `description:` is also hand-authored.

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
  - Strips dims/measures from student-domain cubes for users without
    `cube-access-student-data` — via `isStudentMember`
    (`startsWith("student")`).
  - Adds a `locations` filter based on the highest-priority scope group: network
    (no filter) → region (`region_key`) → school (`abbreviation`). No scope
    group → empty `IN ()` filter (default deny).
  - For queries touching staff-domain cubes, injects the `staff.reporting_chain`
    segment unless the user has `cube-access-staff-all` — via `isStaffMember`
    (`startsWith("staff")`).
- **Naming convention drives security — no static arrays to maintain.** The
  `student_` and `staff_` prefixes automatically route cubes through the correct
  `queryRewrite` gates. Do NOT add new cubes to a `STUDENT_CUBES` or
  `STAFF_CUBES` array — those arrays were removed when Plan 0 ran.
- **`cube-access-staff-data`** is required to see any staff-domain member
  (dimensions and measures), identical to `cube-access-student-data` for
  students. Without it, all `staff_`-prefixed members are stripped from queries.
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

- Mint HS256 JWT locally per request from `CUBEJS_API_SECRET` (1P:
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
`dim_dates.is_current_academic_year` from `{{ var("current_academic_year") }}`)
is a better fit — keeps Cube and dbt in lockstep.

## Measure filters and joined-cube references

Measure `filters:` SQL substitutes dimension expressions at compile time,
including `{other_cube.member}` references to joined cubes. Transitive joins
auto-resolve; don't add redundant intermediate-hop joins. "Column not found" in
a filter usually means the dimension SQL references a bare column on the
filtering cube — route through `{joined_cube.col}` instead.

## Testing Cube measures backed by new dbt columns

When a cube YAML references a column added in this branch (not yet in
`kipptaf_marts`), the playground errors: "Name X not found inside Y". To test
before merge:

1. Build in your dev schema:
   `uv run dbt run --select <model> --project-dir src/dbt/kipptaf --target dev`
   → creates `zz_<username>_kipptaf_marts.<model>`
2. Temporarily change `sql_table` in the cube YAML to
   `zz_<username>_kipptaf_marts.<table>`, commit, push
3. Test in Dev Mode playground (or local `npm run dev` from `src/cube/`)
4. Revert `sql_table` to `kipptaf_marts.<table>`, commit, push before merging

The security hook flags `zz_*` schemas as an access-control regression —
expected for the temporary test commit; acknowledge and revert.

## Operational notes

- **Never use the Cube Playground Models tab.** It overwrites YAML in
  `model/cubes/` and `model/views/` with auto-generated content, discarding
  hand-authored definitions.
- **No manual deploy command.** Production redeploys are triggered by merges to
  `main` in Cube Cloud; do not propose a deploy step.
