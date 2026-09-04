---
paths:
  - "**/src/cube/model/**"
  - "**/src/cube/*.js"
---

# Cube authoring

Loads on the first read of a Cube model file or `cube.js` / `access.js`. Layout,
MCP access, and operational notes stay in `src/cube/CLAUDE.md`; local testing
and diagnostics are in the `cube-ops` skill.

## Authoring conventions

- **Cubes private, views public.** Every cube YAML gets `public: false` at the
  cube level. Dimensions/measures use `public: true` only when meant to be
  exposed via a view. Never flip a cube to `public: true`.
- **Transformation lives in dbt, not cube. A cube's `sql:` / `sql_table:` reads
  exactly ONE dbt model — never a `JOIN`, subquery, CTE, or `SELECT t.*`.**
  Multi-table joins, window functions, and derived grains (SCD2
  period-intersection / status spines) belong in a dbt mart. To surface columns
  from a second table on a view, give that table its own cube (`public: false`,
  exposing only the needed dimensions) and bring them in with a **Cube join**
  keyed on the shared grain — never inline the join in a cube `sql:`.
  `SELECT t.*` is separately forbidden: it silently breaks the moment the base
  model gains a same-named column. The Cube custom-calendar **range-join
  recipe** (`BETWEEN` / `>=`) applies only to a _join's_ `sql:` predicate — it
  is NOT a license for a `JOIN` inside a cube-body `sql:`. (Cube's own dbt
  guidance and the `original_sql` pre-agg confirm the one-model rule.) The
  one-model rule holds with zero exceptions: SCD2 period-intersection grains
  (`staff_work_history` ← `dim_staff_work_history`,
  `staff_reporting_relationships` ← `dim_staff_reporting_periods`) are
  materialized in dbt marts and read via `sql_table:`, not built in a cube-body
  `sql:`.
- **Naming.** Cube `name:` always matches its filename, and neither carries the
  warehouse `dim_`/`fct_` prefix — the file `conformed/dates.yml` defines
  `name: dates` reading `sql_table: kipptaf_marts.dim_dates`. **Domain-prefix
  rule:** student-domain cubes start with `student` (`student_days`,
  `student_periods`, `student_school_enrollments`, `students`); staff-domain
  cubes start with `staff`. This is an organizational convention only — RLS is
  no longer keyed off the cube-name prefix. Every view enforces access through
  its own `access_policy` matching a `securityContext` group (see View access
  policies below); a misnamed cube has no security consequence, but keep the
  convention so the domain is legible from the name. Conformed dims (`dates`,
  `locations`, `regions`, `terms`, `school_calendars`) are deliberately
  unprefixed — they carry no domain access tier. Student views are single,
  collapsed views named `<domain>_view` (`student_days_view`,
  `student_periods_view`, `student_section_enrollments_view`,
  `student_assessment_scores_view`) — a view can't share a bare name with its
  same-domain cube, hence the `_view` suffix. Staff views keep the
  `<domain>_<grain>` pattern (`staff_directory`, `staff_pii`) since that split
  is a genuine access tier, not a grain distinction (see View access policies
  below). `sql_table` always points at `kipptaf_marts.<table>` (the warehouse
  table keeps its `dim_`/`fct_` prefix) — cubes never read district datasets
  directly.
- **Joins use cube-reference syntax** (`{students.col} = {CUBE}.col`), not raw
  identifiers. Dim joins from facts set `relationship: many_to_one`.
- **Range/non-equi join predicates** (`BETWEEN`, `>=`) are valid in a join
  `sql:` (Cube custom-calendar recipe). `many_to_one` fan-trap protection trusts
  your declared `relationship` + `primary_key`, so any non-overlap invariant the
  join relies on must be test-enforced upstream in dbt.
- **Avoid diamond paths.** Two join paths to the same dim → resolve to one
  canonical path. Reach deeper dims by traversing the FK chain (e.g.
  `student_days` reaches `locations` only via
  `student_school_enrollments.locations`, never directly — no second join).
  Alternative resolutions: a compound join on the canonical path (see
  `student_days.yml` → `school_calendars`), or a degenerate FK with no declared
  join. Comment the choice.
- **Second join to an already-role-played mart → fresh `sql_table` cube, not
  `extends`.** To add a SECOND, differently-filtered join to a mart another cube
  already reaches (e.g. a stint cube reaching "the current homeroom section" of
  `dim_student_section_enrollments`), define a fresh `public: false`
  `sql_table:` cube — NOT `extends` the existing one. `extends` inherits the
  base's joins, forming a cycle with the new reverse join.
- **Time dimensions** must cast to `TIMESTAMP` in the dim's `sql:` — but never
  reference a time dimension in a join `sql:`. Cube substitutes the
  query-timezone conversion (`convertTz`) into join predicates, so
  `{dates.date_day} = CAST({CUBE}.date_key AS TIMESTAMP)` matches zero rows
  under any non-UTC query timezone (#4298). Join on raw DATE keys instead
  (`{dates.date_key} = {CUBE}.date_key`). A bare `DATE` column is NOT an
  alternative to the cast: Cube always emits `TIMESTAMP` literals, so a
  `type: time` dimension over an uncast DATE fails with
  `No matching signature for operator >= for argument types: DATE, TIMESTAMP`.
- **Qualify the column with `{CUBE}` in any expression-bodied dimension whose
  column name also exists on a joined cube.** Cube auto-qualifies a scalar
  `sql: <column>` but NOT an expression, so `sql: CAST(date_key AS TIMESTAMP)`
  on `student_days` was ambiguous against `dim_dates.date_key` and **filtering
  that published member failed outright** with
  `Column name date_key is ambiguous`. Grouping by it compiled fine — the
  asymmetry is why this survives review, so check filters, not just group-bys.
  Same root cause as the #4546 `CONCAT` note on `dates.academic_year_label`.
- **A date filter routed through the `dates` join cannot prune a partitioned
  fact.** `dates_date_day` compiles to a predicate on `dim_dates`
  (`dates.date_timestamp >= TIMESTAMP(?)`), and BigQuery cannot prune a fact's
  partitions from a predicate on a joined table — so partitioning a mart is a
  **no-op** unless the view also exposes a fact-side time dimension and its
  description routes single-date and range filters there. `fct_student_days` is
  `PARTITION BY DATE_TRUNC(date_key, MONTH)` and `student_days.attendance_date`
  is that member: measured, single-date network headcount reads **63 MiB / 0.7
  slot-seconds** via `attendance_date` against **1,257 MiB / 24–82
  slot-seconds** via `dates_date_day`, identical rows. A `CAST` around the
  partitioning column does NOT block pruning (verified: bare and CAST-wrapped
  predicates both read 34,224 bytes against 38,659,756 unfiltered). Keep the
  `dates_*` members for grouping and for academic-year / month / week-of
  questions, where they are the only path.
- **Hidden helper measures** prefix with `_` and set `public: false` (see
  `_sum_attendance_value` building blocks).
- **`meta.folders` is the only Cube-rendered `meta.*` key.** Put guidance in
  `description:`, not `meta.usage` / `meta.synonyms` / etc. — those land in
  `/v1/meta` but Cube Cloud and the chat agent don't read them.
- **A `description:` states what the member means and where to go instead —
  never what a member used to be.** These strings reach the chat agent and
  analysts through `/v1/meta`, so a reference to a deleted member sends a caller
  at nothing; deleting a member means deleting every description that names it,
  not annotating them as retired. Twice now a deletion has shipped with
  `meta`-visible descriptions still pointing at removed members
  (`count_students_year_end`, the anchor dimensions) — after a member removal,
  `grep -rn '<member>' model/` and clear every hit, including the ones in prose.
- **Measure grain: query-time vs pre-agg.** At query time Cube recomputes every
  measure fresh at the requested grain — including `count_distinct` (a valid
  distinct count at any grain). A description's "non-additive" note is a
  **pre-aggregation rollup** property, NOT a query-time-grain hazard; don't let
  it read as "unsafe to drop a dimension." The real drop-a-dimension trap is
  **semantic**: measures that recompute mathematically but are meaningful only
  within a comparable scope (`avg_scale_score` / `avg_percent_correct` pooled
  across incompatible assessment sources). Give such scope-bound measures a
  leading `Grain: ... meaningful only within {scope} ... silent-failure trap`
  clause in `description:` (#4476). No schema field enforces this — a
  `reaggregatable` boolean was rejected because "scope-bound" isn't
  machine-detectable; it's a review-checked convention.
- **Folders group dimensions only.** Cube Cloud separates measures natively;
  don't list measures under `members:`.
- **Folder member naming.** Bare for top-cube members; `<prefix>_<member>` for
  `prefix: true` joins, where `<prefix>` is the last `join_path` segment — so
  `regions_region_name` for
  `student_days.student_school_enrollments.locations.regions`.
- **Branch schema validation is manual.** Cube Cloud Staging Environments don't
  auto-create from pushes. Open Cube Cloud → Data Model → Dev Mode → add branch
  by name to spin up a per-branch staging instance.
- **Partitioned pre-aggregations need explicit `build_range_start` /
  `build_range_end`.** Without them Cube derives the range from the
  `time_dimension` min/max — and a `dates.date_day` anchor routes through
  `dim_dates` (calendar spine to 9999), so the refresh worker enumerates ~8,000
  empty yearly partitions on the post-merge prod redeploy (incident: #4460 →
  revert #4462 → bounded #4463). Bound to real data (`SELECT DATE('2015-07-01')`
  to `CURRENT_DATE`). Cube rebuilds a changed pre-agg on merge to `main`, so
  validate the build stays bounded on a branch staging deployment FIRST —
  confirm the partition count via `JOBS_BY_PROJECT` for
  `cube-cloud@teamster-332318`.
- **Measure Cube's own overhead before proposing a pre-aggregation.** It runs
  0.9s–1.5s per query on the student views (planning, Cube Store transport,
  connection) and exceeds BigQuery execution time on most of them, so a pre-agg
  removes the smaller half. Worst measured query on `student_days_view` at 29.6M
  rows: 3.62s wall, 2.17s of it BigQuery — a _perfect_ pre-agg buys ~2.1s of a
  55-second budget. Also check additivity first: `count_distinct` is
  non-additive as a **rollup** property, so a day-grain rollup serves day-grain
  queries and cannot reaggregate to month or year — you would need one pre-agg
  per grain, or `count_distinct_approx` (HLL, wrong for a reported headcount).
  Partitioning the underlying mart is usually the cheaper win; see the
  partition-pruning rule under Authoring conventions.
- **Custom granularities were evaluated and rejected.** `offset: -6 months` on
  `dates.date_day` does work on 1.7.14 and returns correct July-anchored
  buckets, but it costs 58.7 slot-seconds against the `academic_year`
  dimension's 31.1 for an identical answer (10,158 / 10,849 / 11,260), and the
  July bucketing already lives in `dim_dates`. `origin` is silently ignored —
  two different origin values both bucket on the calendar year, with no error.

## View access policies

Views own access entirely via `access_policy:` — RLS is Cube-native and
declarative, not injected server-side; `cube.js` carries none of it (see
`cube.js` security model below). Each policy matches one scope-specific group
emitted by `access.buildGroups`; a viewer holds exactly one group per domain
axis, so exactly one policy per view is ever active — no AND/OR combination to
reason about.

- **Student views are single, collapsed views** — each student domain
  (`student_days_view`, `student_periods_view`,
  `student_section_enrollments_view`, `student_assessment_scores_view`) exposes
  both row-level identifiers and aggregate-breakdown dimensions on the same
  view; there is no separate detail/summary pair. Three policies, one per
  non-`none` `student_location_scope` — `student-region` (`row_level` on the
  region key), `student-school` (`row_level` on the school abbreviation),
  `student-network` (no `row_level` — every location). All three use
  `member_level: { includes: "*" }` — any viewer holding one of these groups
  sees every field on every student view, including PII. `none` scope → no group
  → default-deny (zero rows).
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
- **No aggregate-demographics view yet.** A `staff_summary` view once exposed
  `gender_identity`/`race`/`is_hispanic` as open, unscoped aggregate breakdowns
  — removed because small-cell slices (e.g. location × race) can re-identify an
  individual, and suppression isn't built. Re-introduce only once
  [#4237](https://github.com/TEAMSchools/teamster/issues/4237) (small-cell
  suppression) ships; don't add demographic fields to `staff_directory` in the
  meantime as a workaround.
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
`operator: equals` + array value compiles to SQL `IN`. An **empty** array does
NOT compile to `IN ()`/zero rows — Cube (Tesseract) throws "Values required for
filter" and fails the query (fail-closed, but a hard error, not a clean deny;
verified empirically, #4269). `access.buildGroups` therefore does not emit a
staff-pii group whose remit/chain array resolved empty, so such a viewer takes
the no-group default-deny path instead of hitting that error.

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
access policies above). `cube.js` exports exactly `driverFactory`,
`contextToGroups`, `checkAuth`, `checkSqlAuth`, and `canSwitchSqlUser`.

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
  resolves to the empty default-deny context. **It runs in developer mode too**
  (verified on Cube 1.6.59 and 1.7.14) — so the local REST Playground resolves a
  pasted `{"email": ...}`; do not assume `NODE_ENV=production` is needed.
  `jwt.verify` also enforces `maxAge: "12h"` derived from `iat`, which rejects a
  stale cached Playground token and any token with no `iat` at all. Cube Cloud's
  `iss: "cubecloud"` context never reaches `jwt.verify` — it bypasses
  `checkAuth` entirely and is handled in `contextToGroups` (#4526). **Every 403
  names the failed check** via `jwtRejectionReason` (too-old-from-`iat` with the
  re-mint step / expired past `exp` / bad signature pointing at this
  deployment's `CUBEJS_API_SECRET` / missing `iat`); a bare "Invalid token" for
  all of them is what made the `maxAge` cap read as an access bug. Keep them
  distinguishable.
- **`checkSqlAuth` (SQL API)** returns
  `{ password: process.env.CUBEJS_SQL_PASSWORD, securityContext }` — Cube
  validates the presented password against the RETURNED one, so returning `null`
  rejects every connection. Identity is resolved from the connecting `user` (or
  `CUBE_SQL_DEV_EMAIL` outside prod); the presented `password` is not compared
  and is absent entirely on `SET USER` re-auth flows.
- **`contextToGroups` owns the Cube Cloud path** (#4526). Cube Cloud bypasses
  `checkAuth`, so this hook re-derives the context from `cubeCloud.username` and
  **overwrites** it. **Cube Cloud MERGES a pasted Security Context into the TOP
  LEVEL**, so every top-level value there is caller-supplied: pasting
  `{"groups": ["staff-pii-all_in_scope"], "allowed_abbreviations": [...]}` was
  honored verbatim before the overwrite landed. Never reintroduce a
  `!securityContext.groups` guard here — that guard IS the bypass. The branch
  gates on the presence of the top-level `cubeCloud` key, not on
  `cubeCloud.username` being truthy: a REST/MCP context (no `cubeCloud` key at
  all) skips the block entirely and is passed through untouched, since
  `checkAuth` already resolved it. A Cube Cloud request (`cubeCloud` key
  present) whose `username` is missing still enters the block and resolves to
  the empty default-deny context via `resolveAccess` — a missing `username` is a
  DENY, not a pass-through.
- **Gating on the `cubeCloud` key assumes a paste cannot REPLACE that key.**
  Cube Cloud must apply its own block after the merged paste; if a paste could
  win, pasting `{"cubeCloud": {"username": "<anyone>"}}` would resolve that
  person's real context and collapse the design, not merely the gate. Tested on
  a Dev Mode deployment: a network-scoped caller pasting a school-scoped
  viewer's email as `cubeCloud.username` still got their own four-region scope,
  so the injected block wins. It wins against a FALSY paste too: pasting
  `{"cubeCloud": null, "groups": ["student-region"], "region_key": "<a region>"}`
  returned the caller's own four-region scope rather than the single pasted
  region, so the gate still fired AND the pasted `groups` / `region_key` were
  both overwritten. The merge order is therefore
  `{...paste, cubeCloud: realBlock}`, which makes the pasted value irrelevant.
  Empirical, not guaranteed — Cube Cloud's merge is closed-source and the OSS
  tree has no `cubeCloud` reference — so re-confirm after a Cube Cloud upgrade.
- **Every securityContext field a policy interpolates MUST be returned by
  `access.buildSecurityContext`.** This is what makes the overwrite above a
  COMPLETE one, and it is the load-bearing assumption of the paste fix — not a
  style preference. Add a policy-read field anywhere else (computed in a hook,
  spread in from elsewhere) and `Object.assign` will not overwrite a pasted
  value for it, reopening the Cube Cloud paste vector for that field alone,
  silently and only on that surface. When adding a `row_level` filter that
  interpolates a new `securityContext.*` value, add the field to
  `buildSecurityContext`'s return in the same change.
- **Emulation gate, both surfaces**: caller is the signed `email` claim on
  REST/MCP and `cubeCloud.username` on Cube Cloud; target is `act_as` on REST
  and a pasted top-level `email` (mirrored at `cubeCloud.userAttributes.email`)
  on Cube Cloud. `access.resolveEmulationTarget` decides, from the caller's
  identity only, so a non-impersonator's target is ignored and they keep their
  own scope. Impersonators come from `CUBE_IMPERSONATORS`; unset means emulation
  is inert. Each real emulation logs one `cube_emulation` line (identities
  only). Case is preserved on the resolved email — `resolveAccess` matches
  `google_email` exactly and keys its cache on the raw string.
- **`CUBE_IMPERSONATORS` is a deployment control, not a local one.** Read from
  the environment per request, so nothing is committed to enable it. Locally it
  is self-asserted (the dotenv file is the developer's own) and grants nothing
  they could not already query directly, since running the server needs ADC
  access to `kipptaf_marts`. It only bites on Cube Cloud. **Selection rule:**
  prefer callers whose own scope already covers anything they could emulate
  (`network` student scope + `all_in_scope` staff PII) — for them emulation is a
  viewport change, not a grant. Anyone narrower gains real access and needs its
  own decision. Those emails are PII: deployment config only, never a commit.
- **Group taxonomy (`access.buildGroups`)**: `student-<student_location_scope>`
  (`student-region` / `student-school` / `student-network`); `staff-directory`
  (always, for any resolved row); `staff-pii-<staff_pii_scope>`
  (`staff-pii-all_in_scope` / `-reporting_chain` /
  `-reporting_chain_or_below_rank` / `-teaching_staff`); plus forward-compat
  flat `staff-compensation` / `-observations` / `-benefits` (emitted per
  non-`none` scope; no view consumes them yet). `none` on any axis → no group
  for that axis → default-deny on the views gated by it.
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

## Semi-additive / period-end snapshot measures

Period-end values (chronic absence, ADA tier, truancy rate) are materialized in
dbt at period grain, never computed at query time. Each value is a row in
`fct_student_periods`, read via `student_periods_view` filtering its
`period_type` dimension (`year` / `month` / `week`). Cube filters to the right
row and computes nothing.

**The two student attendance views split on weighting, not on time grain.**
`student_days_view` measures are day-weighted — ratios of summed day counts,
additive over any date range. `student_periods_view` measures are
student-weighted — counts of students past a cumulative threshold at period end,
non-additive across periods because `n_membership_days_ytd` accumulates from the
start of the academic year. Routing consequence: ADA and every attendance-rate
measure exist only on `student_days_view`; chronic absence, tier mix and truancy
exist only on `student_periods_view`; a question wanting both is two queries. A
day-weighted cumulative ADA on the periods cube would equal the daily view's ADA
at year grain and be wrong summed across month or week rows — 1.65M membership
days at year grain against 9.43M summing the eleven AY2025 month rows — which is
why it is not there. A student-weighted one diverges from the daily view's ADA
by 0.66 points (0.9141 against 0.9207, AY2025), so it must not reuse the name.

**Point-in-time enrollment headcount is a pinned date on `student_days_view`.**
The fact carries a row for every enrolled calendar day, break days included, so
any date resolves — no anchor flag, and none available. Pin `attendance_date`,
not `dates_date_day` (see the partition-pruning rule above).

Query-time **window functions** over the daily fact were measured and do not
scale: multi-stage `rank` timed out past 150s, and scoping to one month did not
help, which is what proved the cost structural rather than volume. A plain
additive aggregate by academic year ran 14.3s. Any query-time period-end
computation on this fact lands within a factor of the Cube MCP server's
55-second poll deadline — the same failure
[#4333](https://github.com/TEAMSchools/teamster/issues/4333) fixed for the
assessment cubes. Precompute in dbt instead.

**Multi-stage WITHOUT a window is a different story and is viable.**
`add_group_by` + `reduce_by` compiles to a two-level GROUP BY (no window
functions in the SQL) and is the only way to express a second aggregation level
— mean-of-school-rates, or a count of schools past a threshold — over a row the
periods fact already precomputed. Measured on `student_periods_view`, AY2025
year grain: identical bytes to the flat query, **22x the slot-seconds (1.9 →
42.8) but only 1.75s**, because the base is small. Nothing on either view
answers that question today. The catch is semantic, not performance: a
mean-of-school-rates measure beside the pooled `pct_chronically_absent` puts two
different network numbers on one view (26.09% vs 27.21% for AY2025), so it needs
a `description` naming which question each answers.

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

## School weeks vs ISO weeks

PowerSchool's per-school school week (`week_start_monday`) is NOT a clean
Monday-Sunday grid — weeks split at month/term boundaries (~14% of calendar days
diverge from ISO Monday). Both topline surfaces key on school weeks:
`int_topline__ada_running_weekly` (attendance) and
`int_extracts__student_enrollments_weeks` (enrollment) both group by
`week_start_monday`. Use `dim_dates.school_week_start_date` (same values, routed
cleanly via the join) rather than a raw fact column — Cube can throw "not found"
on a `DATE` fact column cast to `TIMESTAMP` in a BigQuery view.

**`student_periods.period_type = 'week'` is the PowerSchool school week, so
group its rows by `period_start_date` — never by a native `granularity: "week"`
(ISO) on a date dimension.** ISO bucketing compiles and runs, it does not throw,
and silently returns a meaningless breakdown. There is no query-time guard; the
caller has to group correctly.

**The same trap exists at year grain on `dates.date_day`**: a native
`granularity: "year"` buckets on the CALENDAR year and splits every academic
year across two buckets. Measured on `student_days_view` — 12,847 / 13,163 /
10,726 by year granularity against 10,158 / 10,849 / 11,260 by academic year.
Group by `dates_academic_year_label` for anything school-year-shaped.

## `prefix: true` join member names

A member inside a `prefix: true` includes block is exposed with the last
`join_path` segment prepended: `school_week_start_date` under
`join_path: student_days.dates` (prefix: true) surfaces as
`dates_school_week_start_date`. A same-named fact-level dimension alongside the
join creates ambiguity Cube can't resolve at query time. Route via the join when
`dim_dates` carries the same value — avoids the compile error and the redundant
fact column. **To test a model VARIANT without touching the repo tree, point
`CUBEJS_SCHEMA_PATH` at a copy** — `cp -r src/cube/model <scratch>/model-x`,
`sed` the `sql_table` redirect there, then run `npx cubejs-server` with cwd
`src/cube` (so the dotenv file still loads) and `CUBEJS_SCHEMA_PATH` set. No
`zz_` redirect in the working tree means no accidental commit, and two variants
can be compared by restarting against a different copy. Two traps:

- **The path must be RELATIVE.** Cube's `FileRepository` does
  `path.join(process.cwd(), schemaPath)`, and `path.join` does not reset on an
  absolute second argument, so an absolute path silently resolves under the cwd.
  Worse, `ensureDir` then CREATES the wrong directory and compiles an **empty
  schema**, whose symptom is `Table or CTE with name '<view>' not found` — the
  same string as an RLS denial. Count the `../` segments from `src/cube`.
- Set `CUBEJS_REFRESH_WORKER=false` or the refresh worker starts building the
  `student_assessment_scores` pre-agg off the ~14.2M-row fact.

**Cube caches a query result by its text, so a repeat run measures the cache**
(0.25s vs 2-4s). To time anything, append a unique never-matching predicate per
run (`AND academic_year <> <counter>`), seeded from the clock so a second
PROCESS does not replay the first one's values — that defeats BigQuery's 24-hour
results cache too. Confirm with `cache_hit = false` in `JOBS_BY_PROJECT`. Schema
compilation is per-process and lands on the first query (8s–22s): pay it with a
throwaway warmup query before timing.

**`src/cube/node_modules` can lag the lockfile.** Observed 1.7.14 installed
while `package-lock.json` pinned 1.7.30, which silently invalidates any "on
version X" claim from a local run. Check
`node -e "console.log(require('./node_modules/@cubejs-backend/server/package.json').version)"`
before attributing behaviour to a version; `npm ci` in `src/cube` closes the
gap.
