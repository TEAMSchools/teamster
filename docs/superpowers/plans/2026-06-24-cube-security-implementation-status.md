# Cube Security Redesign — Implementation Status / Handoff

**Date:** 2026-06-24 **Branch:**
`cristinabaldor/feat/claude-cube-security-redesign` (not yet a PR) **Issues:**
[#4102](https://github.com/TEAMSchools/teamster/issues/4102) (redesign),
[#4092](https://github.com/TEAMSchools/teamster/issues/4092) (reporting-chain
gate), [#4260](https://github.com/TEAMSchools/teamster/issues/4260)
(data-quality deny population) **Spec:**
[`docs/superpowers/specs/2026-06-03-cube-security-redesign.md`](../specs/2026-06-03-cube-security-redesign.md)
(authoritative design — read it first)

## Done & committed (dbt layer complete + validated)

| Commit      | Contents                                                                                              |
| ----------- | ----------------------------------------------------------------------------------------------------- |
| `f9dd839ed` | `dim_staff_reporting_chain` + `job_function_code` on `dim_work_assignment_jobs` + spec reconciliation |
| `c231d58c5` | `dim_staff_cube_access` + 3 Google Sheets crosswalk sources/staging + `exposures/cube.yml`            |
| `5532304c9` | CLAUDE.md session learnings                                                                           |

Validation (dev, `--favor-state`): `dim_staff_reporting_chain` = 8,041 pairs
(max depth 7, 0 orphans); `dim_staff_cube_access` = 1,495 active staff, 1:1 on
`staff_key`, 1,436 with access, 59 deny. All tests pass.

Crosswalk Google Sheet:
`https://docs.google.com/spreadsheets/d/1TuH7e2AuxP-_dUImtHrWCXJ_S_KD_eYCRqWhbGcD2V4`
— named ranges `cube_access_role`, `cube_access_department_override`,
`cube_access_department_rollup`.

## Remaining work (Cube-side — issue #4102 core)

1. **View `access_policy` tiers** on
   `src/cube/model/views/staff/staff_{detail,summary}.yml` (and student views) —
   resolve to **one composite block per viewer** (avoids the `member_level`
   intersection bug).
2. **Rewrite `src/cube/cube.js`** — `contextToGroups` reads
   `kipptaf_marts.dim_staff_cube_access` (by `google_email`) +
   `dim_staff_reporting_chain` (by `manager_staff_key`), cached to midnight ET,
   no Directory API; `queryRewrite` applies the Layer-1 scope filter + the
   **Layer-2 OR detail gate** (per `staff_access_level`: `detail_below_rank` =
   `job_function_level >` viewer **OR** in downline; `detail_reporting_chain` =
   downline only; `detail` = ungated) + row-conditional column gating; add
   `isStaffMember`; drop `STUDENT_CUBES`/`STAFF_CUBES` arrays. Staff cube/detail
   view must expose `staff_key` and `job_function_level`.
3. **`tests/cube/test_cube_schema.py`** — no `dim_`/`fct_` cube names.
4. **Docs** — `src/cube/CLAUDE.md` + staff view YAML documenting the gate
   (#4092).
5. **Validate in Cube Dev Mode** per tier (network/region/school, summary-only,
   manager-with-reportees, special-access dept, no-access; confirm a pii+comp
   viewer sees both columns). This needs the user's environment.
6. After live + validated: retire the `cube-*` Google Workspace groups.

## Operational notes for PR time

- ~~Stage the new externals to shared staging before dbt Cloud CI~~ **DONE
  2026-06-24** — all three `src_google_sheets__people__cube_access_*` created in
  `zz_stg_kipptaf_google_sheets`. Re-run if the `zz_stg` tables get reset:
  `uv run dbt run-operation stage_external_sources --args 'select: google_sheets.src_google_sheets__people__cube_access_role google_sheets.src_google_sheets__people__cube_access_department_override google_sheets.src_google_sheets__people__cube_access_department_rollup' --target staging --project-dir src/dbt/kipptaf`.
- **Add #4260 to project board #4** (Codespace token lacks `project` scope):
  `gh project item-add 4 --owner TEAMSchools --url https://github.com/TEAMSchools/teamster/issues/4260`.
- **Active-set gap:** marts current-primary = 1,495 vs roster active-primary
  ~1,526 (hire/term timing). Tracked in #4260.
- **`department_type` in the rollup sheet** drives only MGDIR/DIR/KTRGS role
  resolution; confirm the data team has filled it before relying on
  director-tier access.

## Key decisions / gotchas (now also in CLAUDE.md)

- Built **from marts** (intra-mart refs), not `int_people__staff_roster` —
  `marts/CLAUDE.md` forbids ref-into-marts.
- Layer-2 detail gate is **OR** (below-rank OR downline), not AND — leadership
  sees everyone below in scope; same-level peers hidden unless they report in;
  same-level reports (Dean→Teacher) stay visible. See spec § Access model.
- `WITH RECURSIVE` → `contract: enforced: false` (contract wraps SQL in a
  subquery). `--favor-state` beats stale-dev-shadow. `dim_staff` is all-time,
  not active-only. `entity` from `business_unit_name`. (All in
  `src/dbt/CLAUDE.md` / `src/dbt/kipptaf/CLAUDE.md`.)

## How to resume

Merge `main`, then read the spec + this doc. The dbt layer is done; start at
"Remaining work" item 1 (or 2 — `cube.js` is the big piece). Re-validate models
with
`uv run dbt build --select dim_staff_cube_access dim_staff_reporting_chain dim_work_assignment_jobs --target dev --defer --favor-state --state target/prod --project-dir src/dbt/kipptaf`.
