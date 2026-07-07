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

## Remaining (this plan)
- Task 4: split staff_detail into staff_directory + staff_pii.
- Task 5: row_level access_policy on all gated views (+ default-deny validation).
- Task 6: FOLDED INTO TASK 3.
- Task 7: validation matrix + docs.
