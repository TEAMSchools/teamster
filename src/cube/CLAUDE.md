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
- **Naming.** Cube names use business-entity names with no `dim_`/`fct_` prefix.
  Convention by domain:
  - **Student cubes** — base dim: `students`; all others: `student_<name>` (e.g.
    `student_attendance`, `student_enrollments`, `student_ell_status`).
  - **Staff cubes** — base dim: `staff`; all others: `staff_<name>` (e.g.
    `staff_attrition`, `staff_observations`, `staff_work_history`).
  - **Conformed shared dims** — bare business name: `dates`, `locations`,
    `regions`, `terms`, `school_calendars`.
  - **View names** — student-domain views use `student_<domain>_<grain>` (e.g.
    `student_attendance_detail`, `student_attendance_summary`); staff views use
    `staff_<grain>` (e.g. `staff_detail`, `staff_summary`). The
    `student_`/`staff_` prefix is required — `isStudentMember`/`isStaffMember`
    in `queryRewrite` match on `startsWith`, so view names must mirror cube
    naming convention for the security gate to fire at the view level. Adding a
    new student cube named `student_*` is sufficient; it is automatically
    covered. `sql_table` still points at `kipptaf_marts.<warehouse_table>` — the
    warehouse table name (which retains `dim_`/`fct_`) is separate from the Cube
    cube name.
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

Views own access via `access_policy:`. Two patterns:

- **Detail views** (row-level, contain student identifiers): two policy blocks —
  `detail-access` with `member_level.excludes` listing PII fields (names, DOB,
  all `*_student_identifier`, `salesforce_contact_id`), and
  `cube-access-student-pii` (or `cube-access-staff-pii`) with `includes: "*"`.
- **Summary views** (no direct identifiers, demographic breakdowns only): single
  `summary-access` block with `includes: "*"`. Add a comment explaining why no
  PII tier is needed.

`detail-access` and `summary-access` are synthetic groups emitted by
`contextToGroups` from real `*-detail` / `*-summary` Google groups — see
`cube.js`. `cube-access-student-data` access is enforced by `queryRewrite`, not
in view access policies.

When adding a field to a detail view, decide PII status per project CLAUDE.md
FERPA guidance. If PII, add it to the `excludes` list under the `detail-access`
policy block.

## `cube.js` security model

Default-deny, group-driven. Read [`cube.js`](cube.js) before modifying.

- **`contextToGroups`** resolves the requester's email to `cube-*` Google
  Workspace groups via the Admin Directory API, cached until next midnight ET.
  `CUBE_GROUP_MAP` (local dev only, gated on `NODE_ENV !== "production"`) is the
  sole bypass. After resolving real groups, `withSyntheticGroups()` emits
  `detail-access` (if any `*-detail` group is present) and `summary-access` (if
  any `*-detail` or `*-summary` group is present). Synthetic groups are not
  cached — derived fresh on every return.
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
  - Strips dims/measures from student-domain cubes (via `isStudentMember`) for
    users without `cube-access-student-data`.
  - Adds a `dim_locations` filter based on the highest-priority scope group:
    network (no filter) → region (`region_key`) → school (`abbreviation`). No
    scope group → empty `IN ()` filter (default deny).
  - For queries touching staff-domain cubes (via `isStaffMember`), injects the
    `dim_staff.reporting_chain` segment unless the user has
    `cube-access-staff-all`.
- **`isStudentMember` / `isStaffMember`.** Match via `startsWith("student")` /
  `startsWith("staff")` — no maintenance required when new cubes follow the
  naming convention above.
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

## Operational notes

- **Never use the Cube Playground Models tab.** It overwrites YAML in
  `model/cubes/` and `model/views/` with auto-generated content, discarding
  hand-authored definitions.
- **No manual deploy command.** Production redeploys are triggered by merges to
  `main` in Cube Cloud; do not propose a deploy step.
