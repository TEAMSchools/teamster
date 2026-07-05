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
  `queryRewrite`'s `isStudentMember` access gating keys off the `student`
  prefix, so a misnamed student-domain cube silently loses its access guard.
  Staff cubes carry no prefix-based gate in `cube.js` — staff RLS is governed by
  the location scope filter plus each staff view's `cube-access-staff-data`
  access policy. The `staff` prefix is still a naming convention, not a guard.
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
- **Avoid diamond paths.** Two join paths to the same dim → resolve to one
  canonical path. Reach deeper dims by traversing the FK chain (e.g.
  `student_enrollments` and `student_attendance` both reach `locations` only via
  `student_enrollment_stints.locations` — no direct second join). Alternative
  resolutions: a compound join on the canonical path (see
  `student_attendance.yml` → `school_calendars`), or a degenerate FK with no
  declared join. Comment the choice.
- **Time dimensions** must cast to `TIMESTAMP` in the dim's `sql:` — but never
  reference a time dimension in a join `sql:`. Cube substitutes the
  query-timezone conversion (`convertTz`) into join predicates, so
  `{dates.date_day} = CAST({CUBE}.date_key AS TIMESTAMP)` matches zero rows
  under any non-UTC query timezone (#4298). Join on raw DATE keys instead
  (`{dates.date_key} = {CUBE}.date_key`).
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
- **Staff views**: `staff_summary` uses a single `cube-access-staff-data` block
  with `includes: "*"` — aggregate demographics only, no direct identifiers.
  `staff_detail` uses two blocks: `cube-access-staff-data` with `includes: "*"`
  and `excludes:` the personal/sensitive fields (`personal_email`,
  `personal_cell_phone`, `birth_date`, `gender_identity`, `race`,
  `is_hispanic`), plus `cube-access-staff-pii` with `includes: "*"`.
  Work-directory info (names, work/google email, AD username, `staff_unique_id`,
  manager contacts) stays in the base tier — already internally public.
  Demographics are gated row-level in `staff_detail` but remain valid aggregate
  breakdowns in `staff_summary` (low-n suppression tracked separately in
  [#4237](https://github.com/TEAMSchools/teamster/issues/4237)).

When adding a field to a detail view, decide PII status per project CLAUDE.md
FERPA guidance. If PII, add it to the `excludes` list under the base-tier policy
block — `cube-access-student-data` for student views, `cube-access-staff-data`
for `staff_detail`.

## `cube.js` security model

Default-deny, group-driven. Read [`cube.js`](cube.js) before modifying.

- **`contextToGroups`** resolves the requester's email to `cube-*` Google
  Workspace groups via the Admin Directory API, cached until next midnight ET.
  `CUBE_GROUP_MAP` (local dev only, gated on `NODE_ENV !== "production"`) is the
  sole bypass.
- **Group membership is direct-only.** Admin Directory API's
  `groups.list({userKey})` returns direct memberships; nested `cube-*` groups
  don't transitively resolve. Flat-enroll users in every `cube-*` group they
  need: a scope tier (`cube-network-*` / `cube-region-*` / `cube-school-*`) plus
  `cube-access-student-data` for student views and `cube-access-staff-data` for
  staff views.
- **Cloud Identity `searchTransitiveGroups` is edition-gated** (Workspace
  Enterprise / Education Plus / Cloud Identity Premium). On lower editions it
  returns `INVALID_ARGUMENT`, not `PERMISSION_DENIED` — don't propose it as a
  transitive-resolution fix without verifying the tenant's edition.
- **`queryRewrite`** enforces two filters:
  - Strips student-domain dims/measures (members where `isStudentMember` is
    true) for users without `cube-access-student-data`.
  - Adds a `locations` filter based on the highest-priority scope group: network
    (no filter) → region (`region_key`) → school (`abbreviation`). No scope
    group → empty `IN ()` filter (default deny). This scope filter applies to
    staff views too (resolved through their `locations` join).
- **`isStudentMember` prefix helper.** Student-domain gating is derived from the
  cube-name prefix (`student*`), not a static array — a query member is
  `<cube_name>.<member>`, so the cube name is the prefix. A new student-domain
  cube needs no `cube.js` change as long as it follows the naming rule above; a
  misnamed one silently loses its guard. Staff has no equivalent `cube.js` gate
  (manager-hierarchy RLS was removed pending a view-aware rebuild).
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

## Semi-additive / period-end snapshot measures (Tesseract `grain`) — BLOCKED

We attempted to replace the `queryRewrite` anchor injection +
`_year_end`/`_month_end`/`_week_end` named measures with a single grain-adaptive
multi-stage `rank` + `{rank} = 1` measure (cube-js semi-additive recipe). It is
**blocked**: on `student_attendance`, multi-stage measures only compile when
every referenced member is a **plain local column** — no `{CUBE}`, no
joined-cube refs, and no partitioning across a `{CUBE}`-based join. Our cube
reaches date grains and eligibility inputs through joins, so the measures fail
to compile (`student_attendance is not defined` / `CUBE is not defined`).

Full write-up, every variation tried, exact errors, and local repro steps:
[`docs/superpowers/specs/2026-06-18-chronic-absence-eop-tesseract-handoff.md`](../../docs/superpowers/specs/2026-06-18-chronic-absence-eop-tesseract-handoff.md).
Do not re-attempt the multi-stage `*_eop` measures without resolving that
constraint (see the handoff doc's options A/B). `grain` requires
`CUBEJS_TESSERACT_SQL_PLANNER=true` and cube ≥ 1.6.59 (1.6.38 has no `grain`).

## Testing Cube measures backed by new dbt columns

When a cube YAML references a column added in this branch (not yet in
`kipptaf_marts`), the playground errors: "Name X not found inside Y". To test
before merge:

1. Build in your dev schema:
   `uv run dbt run --select <model> --project-dir src/dbt/kipptaf --target dev`
   → creates `zz_<username>_kipptaf_marts.<model>`
2. Temporarily change `sql_table` in the cube YAML to
   `zz_<username>_kipptaf_marts.<table>` — do NOT commit or push
3. Test in the local dev server — launch the **`Cube: Dev Server`** VS Code task
   (`.vscode/tasks.json`; installs `src/cube/node_modules` if missing, then
   `npm --prefix src/cube run dev`). Hot-reloads on file save, no push required.
   Claude can't run it (long-running server) — ask the user to start the task
   and report back. Or commit+push for Cube Cloud Dev Mode.
4. Revert `sql_table` to `kipptaf_marts.<table>` before committing

For **snowflake sub-dims** (cubes joined one-to-one from a parent), swap
`sql_table` on the sub-dim cube file, not the parent. The parent's `sql_table`
stays pointed at prod; only the new sub-dim needs redirecting.

The security hook flags `zz_*` schemas as an access-control regression —
expected if you do commit the temporary change; acknowledge and revert.

**`zz_*` redirect — never `git add` the whole cubes/ dir while it's live.** When
a `sql_table` redirect to a `zz_*` dev schema is in the working tree, staging
with `git add -A`, `git add .`, or `git add src/cube/model/cubes/` accidentally
commits the redirect. Name files explicitly in every `git add` while any cube
YAML is redirected.

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
