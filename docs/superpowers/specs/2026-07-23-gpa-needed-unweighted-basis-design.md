# Needed-Y1 GPA and Attainability on an Unweighted Basis — Design

Issue: [#4528](https://github.com/TEAMSchools/teamster/issues/4528)

## Problem

`int_powerschool__gpa_cumulative` exposes `gpa_needed_for_cumulative_3_0` (the
current-year Y1 GPA a student needs to reach a cumulative 3.0) and
`is_cumulative_3_0_attainable`. Both are computed on a **weighted** basis — they
target a _weighted_ cumulative 3.0.

The GPA cohort-goal work targets an **unweighted** cumulative 3.0
(stakeholder-defined: 10th 49%, 11th 45%, by EOY). Because weighted cumulative
is always at or above unweighted cumulative, the weighted columns set an easier
bar: `gpa_needed_for_cumulative_3_0` comes out too low and
`is_cumulative_3_0_attainable` reads too generous relative to the stated goal.
The column names say `cumulative_3_0`, not `cumulative_3_0_weighted`, so the
weighted basis is effectively a latent defect against the goal these columns are
meant to serve.

## What already exists (verified, not assumed)

Two things scoped the original issue as harder than it is:

1. **The cohort rollup metric is already buildable.** The kipptaf wrapper
   `int_powerschool__gpa_cumulative` already derives
   `cumulative_y1_gpa_projected_unweighted_band` (= 4 when projected EOY
   unweighted cumulative is at or above 3.0), off
   `cumulative_y1_gpa_projected_unweighted` which is already surfaced in the
   extract. So _"% of cohort projected to reach unweighted cumulative 3.0"_ —
   the goal metric — needs no new column. This work is **not** the rollup; it is
   the per-student target-setting layer (advisor coaching numbers, cohort-target
   inversion, the attainability flag).

1. **Both inputs for the correction already exist.** The issue flagged the
   unweighted gradescale ceiling as an unknown to resolve at build time. It is
   not unknown:

   - `unweighted_points` already exists per row in the `with_weighted_points`
     CTE and already feeds `cumulative_y1_gpa_unweighted`. Summing it for prior
     years is a one-line aggregation.
   - The unweighted ceiling is a second join of the existing `gradescale_max`
     CTE onto `courses_gradescaleid_unweighted` — a column
     `base_powerschool__final_grades` already carries and already uses for
     `y1_grade_points_unweighted`.

   No new plumbing, no upstream change. Credit denominators (`cr_prior`,
   `cr_current`) are weighting-agnostic and unchanged; only the prior-points
   numerator and the ceiling differ between bases.

## Design

### Change A — correct `int_powerschool__gpa_cumulative` in place (value-only)

Redefine both `gpa_needed_for_cumulative_3_0` and `is_cumulative_3_0_attainable`
from weighted to unweighted basis. **Both halves flip together** — a needed
computed on unweighted prior points compared against a weighted ceiling would
mix bases and produce a nonsense attainability flag. Column names and types are
unchanged, so this is a value-only edit.

The internal weighted needed/attainability chain — `weighted_points_prior`, the
per-row `gpa_points_projected_max`, and its
`weighted_points_projected_max_current` / `potentialcrhrs_current_max_known`
rollups — is used **only** by these two output columns (verified by grep). So it
is **repointed** to unweighted, not duplicated: repointing avoids leaving dead
CTE columns behind. The unweighted per-row points (`unweighted_points`) and the
unweighted gradescale id (`courses_gradescaleid_unweighted`) already exist;
nothing new is plumbed.

Edits:

1. **`grades_union`** — repoint the max-ceiling column to the unweighted scale
   and rename it `gpa_points_projected_max_unweighted`:

   - Branch 1 (stored): source the locked max from the unweighted lookup already
     joined as `su` — `if(sg.excludefromgpa = 0, su.grade_points, null)` (an
     already-stored grade's max achievable is its actual points).
   - Branch 2 (projected current): repoint the `gradescale_max` join from
     `fg.courses_gradescaleid` to `fg.courses_gradescaleid_unweighted` (alias
     `gsm_u`), then
     `if(fg.y1_letter_grade is null, null, gsm_u.max_grade_points)`.
   - Branch 3: `null`.

1. **`with_weighted_points`** — rename the per-row product to the unweighted
   source:
   `potentialcrhrs_projected * gpa_points_projected_max_unweighted as unweighted_points_projected_max`.

1. **`points_rollup`** — replace the weighted prior/max rollups with unweighted
   ones (the existing all-years `sum(unweighted_points) as unweighted_points`
   stays — it feeds `cumulative_y1_gpa_unweighted`; these are prior/current
   splits):

   ```text
   sum(if(academic_year < current, unweighted_points, null))
       as unweighted_points_prior
   sum(if(academic_year = current, unweighted_points_projected_max, null))
       as unweighted_points_projected_max_current
   sum(if(academic_year = current
          and unweighted_points_projected_max is not null,
          potentialcrhrs_projected, null))
       as potentialcrhrs_current_max_known_unweighted
   ```

1. **`needed_gpa`** — repoint both derivations to the unweighted inputs:

   ```text
   gpa_needed_raw = safe_divide(
       3.0 * (coalesce(potentialcrhrs_prior, 0) + potentialcrhrs_current)
       - coalesce(unweighted_points_prior, 0),
       potentialcrhrs_current)

   gpa_max_current_raw = if(
       coalesce(potentialcrhrs_current_max_known_unweighted, 0)
           = coalesce(potentialcrhrs_current, 0),
       safe_divide(unweighted_points_projected_max_current,
                   potentialcrhrs_current),
       null)
   ```

   The `_max_known` guard (null the ceiling when a course's gradescale max is
   unresolvable, rather than understate it) is preserved — just evaluated
   against the unweighted join.

Other weighted columns (`cumulative_y1_gpa`, `weighted_points_projected`, etc.)
are untouched — only the needed/attainability chain moves to unweighted.

### Change B — add per-student display columns to `rpt_tableau__student_course_grades`

Two new columns, computed in the extract from columns already present (Change A
makes `gpa_needed_for_cumulative_3_0` unweighted, so no new powerschool column
is needed for B):

1. **`gpa_y1_weighted_target`** (the A-prime bar — the weighted Y1 to show a
   student, since stakeholders speak in weighted-Y1 terms):

   ```text
   gpa_y1_weighted_target =
       gpa_needed_for_cumulative_3_0 + (gpa_y1 - gpa_y1_unweighted)
   ```

1. **`is_on_pace_cumulative_3_0`** (the rollup atom):

   ```text
   is_on_pace_cumulative_3_0 =
       gpa_y1_unweighted >= gpa_needed_for_cumulative_3_0
   ```

The spread `gpa_y1 - gpa_y1_unweighted` cancels at the on-pace test, so
`gpa_y1 >= gpa_y1_weighted_target` is algebraically identical to
`gpa_y1_unweighted >= gpa_needed_for_cumulative_3_0`. Aggregating
`is_on_pace_cumulative_3_0` at any grain gives the true projected cumulative-3.0
rate through each student's real path.

## Sequencing

Two PRs, because the corrected values must be materialized in each district's
prod before the extract reads them:

1. **PR 1 (Change A)** — the powerschool package model. Value-only, so kipptaf
   dbt Cloud CI compiles unchanged; the correction is exercised by Dagster's
   district prod rebuild, not dbt Cloud CI. No external-source staging needed.
1. **PR 2 (Change B)** — the kipptaf extract, opened after PR 1 lands and the
   district `int_powerschool__gpa_cumulative` tables rebuild in prod, so
   `gpa_y1_weighted_target` reads corrected `gpa_needed_for_cumulative_3_0`
   values.

## Contract, tests, descriptions

- **Descriptions** — update the YAML `description` of both corrected columns to
  state the unweighted basis explicitly, so the meaning is unambiguous for any
  consumer.
- **Unit test** — `unit_gpa_cumulative_needed_gpa` asserts
  `gpa_needed_for_cumulative_3_0` / `is_cumulative_3_0_attainable`; recompute
  its expected values on the unweighted basis.
- **Extract contract** — add `gpa_y1_weighted_target` (float64) and
  `is_on_pace_cumulative_3_0` (boolean) to the
  `rpt_tableau__student_course_grades` properties/contract with descriptions.
- **Verification** — build `int_powerschool__gpa_cumulative` (via a consuming
  district project-dir with `--defer` to prod) and confirm the corrected
  `needed` rises and `attainable` tightens versus the weighted values; tie out
  `is_on_pace_cumulative_3_0` against `gpa_y1_unweighted` versus
  `gpa_needed_for_cumulative_3_0` on a backtest year.

## Caveats

- **`gpa_y1_weighted_target` needs a realized current-year Y1.** The spread
  `gpa_y1 - gpa_y1_unweighted` is undefined before current-year grades exist, so
  the A-prime bar activates with SY26-27 data alongside the rest of the
  current-year columns.

## Out of scope

- The cohort-goal rollup and target-setting math (already covered by
  `cumulative_y1_gpa_projected_unweighted`; documented in the `gpa-cohort-goals`
  scratch framing).
- Deprecating the weighted basis: it is being corrected, not duplicated, so
  there is no leftover weighted pair to retire.
