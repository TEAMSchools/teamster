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
  DESIGN CHANGE (needs user sign-off before Task 2): move enum→bool comparison
  into buildSecurityContext, emit mutually-exclusive boolean scope flags, gate
  Task 5 policies on truthy flags. No queryRewrite residual. Cloud
  userAttributes-vs-securityContext still unverified.

## Remaining (this plan)

- Task 2: access.js `buildSecurityContext` (pure, unit-tested) — REVISED to emit
  boolean scope flags (pending user sign-off).
- Task 3: cube.js resolve identity in checkAuth + checkSqlAuth.
- Task 4: split staff_detail into staff_directory + staff_pii.
- Task 5: row_level access_policy on all gated views.
- Task 6: delete queryRewrite RLS half.
- Task 7: validation matrix + docs.
