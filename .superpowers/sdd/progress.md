# Cube `access_policy` Pivot — SDD Progress Ledger

Plan: docs/superpowers/plans/2026-07-07-cube-access-policy-pivot.md
Spec: docs/superpowers/specs/2026-06-25-cube-access-reviewer-guide.md
Branch: cristinabaldor/feat/claude-cube-security-redesign

Goal: move Cube RLS out of `cube.js` `queryRewrite` into per-view
`access_policy` driven by a server-enriched `securityContext`. Delete the RLS
half of `queryRewrite`; keep the snapshot-anchor block (removed by Track 1).

## Superseded predecessor

The two-scope plan (2026-06-24) landed on this branch: dbt models
`dim_staff_cube_access` + `dim_staff_reporting_chain`, scope enums, and
`member_level` field gating are DONE and are unchanged by this plan.

## Completed (this plan)

- Task 1: access_policy spike (controller-driven, live SQL API). Verdict in
  plan §"Task 1 Verdict". KEY FINDINGS: array-IN + nested or/and + truthy
  conditions.if + default-deny all WORK; but `==` in conditions.if does NOT
  compile (Python-expr parser), and multi-policy combines by OR/union not AND.
  Resolved (user sign-off): canonical GROUP-BASED design — see "Design decisions
  locked" below.

- Task 2: complete (commits 44274499e..583eed5fc, review clean). access.js:
  buildGroups emits scope-specific groups (student-<scope>, staff-pii-<scope>);
  buildSecurityContext added; row-filter builders + their tests deleted. 10/10
  tests pass.
- Task 3: complete (commits 92dab23b4..6e5fa17e6, re-review clean + live
  validated). cube.js: resolveAccess (fail-closed try/catch), checkAuth (now
  verifies+decodes HS256 JWT via jsonwebtoken — a Critical review fix; raw-string
  bug), checkSqlAuth (returns server password), contextToGroups one-liner,
  queryRewrite RLS branch REMOVED (folded-in Task 6, snapshot loop kept).
  jsonwebtoken added to src/cube/package.json. LIVE: REST /meta 200 + 28 cubes
  for a real JWT; REST /load real data (staff_work_history=4638) → full auth
  path works.

- Task 4: complete (commits 06471ada2..5de6d907d, review clean after 1 fix,
  live validated). Split staff_detail → staff_directory (open, no PII) +
  staff_pii (6 PII + identity + Task-5 remit members: staff_key,
  job_function_level, job_function_code, department_group, locations_abbreviation,
  locations_region_key; interim fail-closed placeholder policy group "staff-pii").
  staff_detail deleted. Live /meta: split confirmed, no PII leak, region_key
  resolves. Fix: foldered is_primary_position/status_name.
  Minor deferred: staff_directory "Staff" folder omits job_function_* /
  department_group (PRE-EXISTING, carried from staff_detail); CLAUDE.md "View
  access policies" still describes old staff_detail (→ Task 7 docs).

VALIDATION STRATEGY CHANGE (Task 3 live finding):
- SQL API + Tesseract (CUBEJS_TESSERACT_SQL_PLANNER=true) FAILS on every JOINED
  view with "Failed to deserialize ... JoinDefinitionStatic" — uniform, not
  auth, not view-specific (spike worked only because it had no joins).
  Pre-existing Track 1 (Tesseract) issue. REST /load WORKS. => Task 5/7 validate
  via REST /load (JWT-authed), NOT psycopg2 SQL API. Plan updated.
- Minor (final review): checkAuth garbage token → HTTP 500 not 401/403 (raw
  jwt.verify throw; a cleaner impl maps to CubejsHandlerError 401).

Design decisions locked (Task 1 verdict + user sign-off):
- Canonical GROUP-BASED RLS: buildGroups emits student-<scope> / staff-pii-<scope>;
  each Task 5 policy matches one group with its own member_level + row_level. No
  conditions.if (== won't compile). No queryRewrite residual.
- Task 6 (queryRewrite RLS removal) FOLDED INTO Task 3 — RLS briefly absent on
  intermediate branch commits (never deployed). Task 3 checkSqlAuth must return
  the server-known password, NOT null.
- Still open: Cube Cloud userAttributes-vs-securityContext interpolation
  (untestable on local Core; verify on Cloud Dev Mode/staging).

Minor findings for FINAL review (not fixed, deferred):
- access.js:3-14 + :34-35 header/comment describe deleted row-filter arch (stale).
- src/cube/CLAUDE.md security-model section stale (updated in Task 7).
- buildSecurityContext tests assert a subset, not full deepStrictEqual (per brief).

TASK 5 DESIGN — Option 3 (precompute allow-lists), user-approved. Remit is
shared by ALL 4 sensitive staff domains (pii + forward-compat comp/obs/benefits);
only staff_pii implemented now (YAGNI). Split into 5a (machinery) + 5b (views):

5a — access.js + cube.js precompute (reopens Task 2/3 additively):
  - access.js pure helpers (unit-tested):
    computeAllowedAbbreviations(locationScope, regionKey, locationAbbreviation, universe)
      network→all abbrevs; region→abbrevs where region_key===regionKey;
      school→[locationAbbreviation]; none→[].  (universe = [{abbreviation,region_key}])
    computeAllowedDepartmentGroups(deptScope, departmentGroup, deptUniverse)
      all→deptUniverse; own_group→[departmentGroup]; none→[].
    buildSecurityContext gains args allowedAbbreviations, allowedDepartmentGroups
      → fields allowed_abbreviations, allowed_department_groups (default []).
    Uses staff_location_scope + staff_department_scope (NOT exposed before — read
    from row inside resolveAccess, passed to the helpers).
  - cube.js resolveAccess: fetch+cache GLOBALLY (once, not per-email) two
    universes: locations = SELECT abbreviation,region_key FROM
    kipptaf_marts.dim_locations; deptGroups = SELECT DISTINCT department_group
    FROM kipptaf_marts.dim_staff_cube_access. Compute the two allow-lists via the
    helpers from the viewer row's staff_location_scope/staff_department_scope,
    pass to buildSecurityContext. Dev CUBE_GROUP_MAP bypass → empty lists.
5b — view access_policy (validate via REST /load):
  - student views: 3 policies matching groups student-region /-school /-network:
    region→locations.region_key equals {region_key}; school→locations.abbreviation
    equals {location_abbreviation}; network→no row_level. (single-value equals)
  - staff_pii.yml: replace interim placeholder with 4 policies (group
    staff-pii-<pii_scope>), member_level includes "*", row_level (equals+array = IN):
    all_in_scope: AND(locations.abbreviation IN {allowed_abbreviations},
                      staff.department_group IN {allowed_department_groups})
    teaching_staff: above AND staff.job_function_code IN ['TEACH','TIR']
    reporting_chain: staff.staff_key IN {reportee_staff_keys}
    reporting_chain_or_below_rank: OR(AND(abbrev IN, dept IN,
      staff.job_function_level gt {job_function_level}), staff.staff_key IN chain)
    none → no group → default-deny (no policy).
  - member refs are cube.members (locations.abbreviation, staff.department_group,
    staff.job_function_code/level/staff_key) — all exposed by staff_pii (Task 4).
  - array interpolation form: values: "{ securityContext.allowed_abbreviations }"
    (unbracketed); single value: values: ["{ securityContext.region_key }"].

## Remaining (this plan)
- Task 5a: precompute allow-lists in access.js + cube.js (unit-tested).
- Task 5b: row_level access_policy on student + staff_pii views (REST /load val).
- Task 6: FOLDED INTO TASK 3.
- Task 7: validation matrix + docs.
