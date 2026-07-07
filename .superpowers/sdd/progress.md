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

- Task 5a: complete (commit 9ba944f86, review clean, live /load OK). access.js
  computeAllowedAbbreviations + computeAllowedDepartmentGroups (pure, tested);
  buildSecurityContext emits allowed_abbreviations/allowed_department_groups;
  cube.js resolveAccess fetches+caches (global, midnight) locations +
  department_group universes inside the fail-closed try, computes allow-lists.
  21/21 tests. Minor (final review): add null-row comment; no integration test
  for loadUniverses cache/fail branch.

5b view files (6 student + staff_pii; staff_directory/summary unchanged):
  students/student_enrollments_{detail,summary}.yml
  student_attendance/student_attendance_{detail,summary}.yml
  student_assessments/student_assessment_scores_{detail,summary}.yml
  staff/staff_pii.yml (replace interim placeholder → 4 pii_scope policies)

- Task 5b: complete (commit 01b71aad0, review clean — 1 Minor). Student views
  3-group location policies; staff_pii 4 pii_scope policies (uniform IN via
  allowed_abbreviations/allowed_department_groups). Policy correctness reviewed;
  member paths verified via join graph. LIVE viewer-matrix BLOCKED (see below).

## BLOCKER — upstream dbt/sheet migration incomplete (prereq, out of plan scope)
The branch's "single student tier" refactor (commit a7413f9df) migrated the dbt
CONTRACTS (.yml), downstream dim_staff_cube_access.sql, sources-external.yml
column decls, AND all the Cube code — but the google_sheets EXTERNAL TABLES (and
possibly the underlying Sheets) still carry the OLD two-tier columns
(student_summary_location_scope, student_detail_location_scope, student_pii_scope,
department_type). So the 3 stg_google_sheets__people__cube_access_* models FAIL
their enforced contracts (`select *` from stale external → old cols; contract
expects student_location_scope), dim_staff_cube_access can't build, and NO schema
(prod/staging/dev) has the correct single-tier access table. The Cube server
always fail-closes → live RLS validation impossible until fixed.
Prod also lacks dim_staff_reporting_chain entirely. Unrelated: stg_adp..workers
fails on `religioncode` (ADP source drift; only hit by the `+` ancestor build).
FIX (user/Ops, classifier-blocked for Claude): confirm/update the Sheets to the
single-tier columns → stage_external_sources --target dev ext_full_refresh:true
for the 3 cube_access sheets → rebuild stg_* + dim_staff_cube_access to dev →
then redirect Cube server to dev + run viewer-matrix.

- Task 5 COMPLETE + LIVE-VALIDATED 8/8 (5a: commit 9ba944f86; 5b: 01b71aad0
  + fix 748d7240b). REST /load viewer-matrix against a dev-schema build:
  network=all (10721 students/1443 staff), Newark viewer=6648 (==gt slice),
  Royalty viewer=693 (==gt slice), none/unresolved denied. Harness:
  .claude/scratch/access_policy_validation.py.

KEY LESSONS (for Task 7 docs + final review + future validation):
- View access_policy row_level `member:` MUST be the FLAT view-member name
  (locations_abbreviation, department_group, staff_key, job_function_code/level),
  NOT a cube path (locations.abbreviation) — paths fail at compile ("Paths aren't
  allowed in the accessPolicy policy"). Member name depends on the join prefix:
  enrollment/attendance views join locations prefix:true → locations_abbreviation
  / locations_region_key; assessment views prefix:false → bare abbreviation /
  region_key. region_key had to be exposed in the student views for the region
  policy. (The plan's Task 5 examples show cube-path form — STALE; update in docs.)
- LIVE VALIDATION ENV (all hard-won, for Task 7 / re-runs):
  * prod kipptaf_marts has the OLD dim_staff_cube_access schema + NO
    dim_staff_reporting_chain. The branch's models were only in dev/staging.
    Rebuild to dev: dbt build --defer --select the 3 changed identity models.
  * cube_access google_sheets externals were STALE — user must re-stage:
    stage_external_sources --target dev ext_full_refresh (classifier-blocked for
    Claude). Sheet already had single-tier columns; only the external was stale.
  * SURGICAL redirect (UNCOMMITTED; git checkout to revert): ONLY
    dim_staff_cube_access + dim_staff_reporting_chain → dev schema. Keep
    dim_work_assignment_jobs on PROD (staff cube reads job_function_code from
    ca=dim_staff_cube_access, not wj; redirecting wj broke the wj↔swa key join).
  * SQL API + Tesseract fails on JOINED views (JoinDefinitionStatic) → use REST /load.
  * CUBEJS_DEV_MODE=true DISABLES REST checkAuth (auth off) → run NODE_ENV=production
    (dev mode off) so checkAuth/resolveAccess runs.
  * .env had CUBE_GROUP_MAP copied from .env.example (placeholder groups
    cube-network-detail/cube-access-student-data) → dev-bypass overrode real
    resolution → deny-all. Comment it out.
  * count_students on student_enrollments is snapshot-anchored (is_current_record
    → 0 in summer); validate student RLS with student_attendance count_students
    (additive, date-range).

## Remaining (this plan)
- Task 7: docs (src/cube/CLAUDE.md + reviewer guide) — harness done (5b). Update
  the plan's stale cube-path Task 5 examples too. Optionally re-review 5b fix
  (live 8/8 is strong evidence).
- Cleanup: user should restart the dev server back to prod refs (working tree
  already reverted; redirect+DBG only lived in the running process).
- Task 6: FOLDED INTO TASK 3.
- Task 7: validation matrix + docs.
