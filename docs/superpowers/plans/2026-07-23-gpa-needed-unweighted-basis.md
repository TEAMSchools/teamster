# Needed-Y1 GPA and Attainability on an Unweighted Basis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct `gpa_needed_for_cumulative_3_0` and
`is_cumulative_3_0_attainable` in `int_powerschool__gpa_cumulative` from a
weighted to an unweighted basis, then surface a per-student weighted display
target and an on-pace flag in `rpt_tableau__student_course_grades`.

**Architecture:** The needed/attainability chain in
`int_powerschool__gpa_cumulative` is repointed from weighted inputs
(`weighted_points_prior`, the weighted gradescale ceiling) to unweighted inputs
(`unweighted_points`, the unweighted gradescale ceiling via
`courses_gradescaleid_unweighted`). Column names and types are unchanged, so
this is a value-only package change. The extract then derives
`gpa_y1_weighted_target = needed + (gpa_y1 - gpa_y1_unweighted)` and
`is_on_pace_cumulative_3_0 = gpa_y1_unweighted >= needed` from the corrected
column plus existing spread fields.

**Tech Stack:** dbt (BigQuery dialect), dbt unit tests, powerschool source
package consumed by district projects and kipptaf via `source()`.

## Global Constraints

- `int_powerschool__gpa_cumulative` lives in the powerschool **package**; build
  and test it through a consuming district project-dir (`kippnewark`) — never
  standalone. Reference: `src/dbt/CLAUDE.md` → "Building a source-system package
  model locally".
- Worktree:
  `/workspaces/teamster/.worktrees/anthonygwalters-feat-claude-gpa-needed-unweighted-basis`.
  Every `git` uses `git -C <worktree>`; every `dbt` uses
  `--project-dir <worktree>/src/dbt/<project>`. `--state` must be the
  **absolute** main-repo prod manifest path.
- Fresh worktree has no `dbt_packages/` — run `dbt deps` once per project-dir
  before any build/test.
- dbt unit-test fixtures: dict scalars UNQUOTED; leading-zero strings QUOTED;
  every `expect` row lists the SAME columns. yamllint (88-char) fires at CI, not
  the pre-commit fmt hook — match the existing one-key-per-line brace layout.
- SQL guide (`src/dbt/CLAUDE.md`): max 1 level of function nesting; no
  `ORDER BY` / `QUALIFY` / `SELECT *` in `rpt_`; ST06 column ordering;
  sqlfluff/sqlfmt via trunk. `trunk check --force` the changed `.sql`/`.yml`
  from inside the worktree before pushing (binary
  `/workspaces/teamster/.trunk/tools/trunk`).
- `--target prod` dbt runs and `git push origin main` are user-only.
  Feature-branch pushes are fine.
- Spec:
  `docs/superpowers/specs/2026-07-23-gpa-needed-unweighted-basis-design.md`.
  Issue: #4528.

---

## PR 1 — correct the powerschool model (executable now)

### Task 1: Repoint needed/attainability to unweighted basis (model + unit test + descriptions)

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml`
  (unit test + descriptions)

**Interfaces:**

- Consumes: `stg_powerschool__storedgrades`,
  `int_powerschool__gradescaleitem_lookup`, `base_powerschool__final_grades`
  (already exposes `courses_gradescaleid_unweighted`),
  `base_powerschool__student_enrollments`.
- Produces: unchanged output columns `gpa_needed_for_cumulative_3_0` (float64)
  and `is_cumulative_3_0_attainable` (boolean), now on an unweighted basis.

- [ ] **Step 1: Rewrite the unit test to the unweighted basis (the failing
      test)**

Replace the entire `unit_tests:` block in
`.../properties/int_powerschool__gpa_cumulative.yml` with the block below. Keep
the existing one-key-per-line brace layout the file already uses (shown compact
here for readability — expand each row so yamllint's 88-char limit passes; run
trunk to confirm). Values are final.

Fixtures (`given`):

```text
stg_powerschool__storedgrades (all prior years; percent drives the unweighted grade):
  S1  ay2022  C1  Y1  potentialcrhrs 35.0  earnedcrhrs 35.0  gpa_points 4.5  percent 95  gradescale_name_unweighted "UT Unweighted"  excludefromgpa 0  excludefromgraduation 0  schoolid 101
  S1  ay2023  C1  Y1  potentialcrhrs 35.0  earnedcrhrs 35.0  gpa_points 4.5  percent 95  gradescale_name_unweighted "UT Unweighted"  excludefromgpa 0  excludefromgraduation 0  schoolid 101
  S1  ay2024  C1  Y1  potentialcrhrs 35.0  earnedcrhrs 0.0   gpa_points 0.0  percent 50  gradescale_name_unweighted "UT Unweighted"  excludefromgpa 0  excludefromgraduation 0  schoolid 101
  S3  ay2021  C1  Y1  potentialcrhrs 35.0  earnedcrhrs 35.0  gpa_points 4.5  percent 95  gradescale_name_unweighted "UT Unweighted"  excludefromgpa 0  excludefromgraduation 0  schoolid 101
  S3  ay2022  C1  Y1  potentialcrhrs 35.0  earnedcrhrs 35.0  gpa_points 4.5  percent 95  gradescale_name_unweighted "UT Unweighted"  excludefromgpa 0  excludefromgraduation 0  schoolid 101
  S3  ay2023  C1  Y1  potentialcrhrs 35.0  earnedcrhrs 35.0  gpa_points 4.5  percent 95  gradescale_name_unweighted "UT Unweighted"  excludefromgpa 0  excludefromgraduation 0  schoolid 101
  S3  ay2024  C1  Y1  potentialcrhrs 35.0  earnedcrhrs 35.0  gpa_points 4.5  percent 95  gradescale_name_unweighted "UT Unweighted"  excludefromgpa 0  excludefromgraduation 0  schoolid 101
  S4  ay2024  C1  Y1  potentialcrhrs 35.0  earnedcrhrs 0.0   gpa_points 0.0  percent 50  gradescale_name_unweighted "UT Unweighted"  excludefromgpa 0  excludefromgraduation 0  schoolid 101
  S5  ay2024  C1  Y1  potentialcrhrs 35.0  earnedcrhrs 35.0  gpa_points 3.0  percent 85  gradescale_name_unweighted "UT Unweighted"  excludefromgpa 0  excludefromgraduation 0  schoolid 101

int_powerschool__gradescaleitem_lookup (unchanged from current fixture):
  gsid 10 "UT Weighted"   A 4.5  min 90 max 100
  gsid 10 "UT Weighted"   B 3.0  min 80 max 89.9
  gsid 10 "UT Weighted"   F 0.0  min 0  max 79.9
  gsid 20 "UT Unweighted" A 4.0  min 90 max 100
  gsid 20 "UT Unweighted" B 3.0  min 80 max 89.9
  gsid 20 "UT Unweighted" F 0.0  min 0  max 79.9

base_powerschool__final_grades (current in-progress; NOTE courses_gradescaleid_unweighted):
  S1  yearid 35  C1  Q4  potential_credit_hours 35.0  y1_letter_grade B  y1_grade_points 3.0  y1_grade_points_unweighted 3.0  courses_gradescaleid 10  courses_gradescaleid_unweighted 20  exclude_from_gpa 0  termbin_start_date 2000-01-01  termbin_end_date 9999-12-31
  S2  yearid 35  C1  Q4  potential_credit_hours 35.0  y1_letter_grade B  y1_grade_points 3.0  y1_grade_points_unweighted 3.0  courses_gradescaleid 10  courses_gradescaleid_unweighted 20  exclude_from_gpa 0  termbin_start_date 2000-01-01  termbin_end_date 9999-12-31
  S3  yearid 35  C1  Q4  potential_credit_hours 35.0  y1_letter_grade B  y1_grade_points 3.0  y1_grade_points_unweighted 3.0  courses_gradescaleid 10  courses_gradescaleid_unweighted 20  exclude_from_gpa 0  termbin_start_date 2000-01-01  termbin_end_date 9999-12-31
  S4  yearid 35  C1  Q4  potential_credit_hours 35.0  y1_letter_grade B  y1_grade_points 3.0  y1_grade_points_unweighted 3.0  courses_gradescaleid 10  courses_gradescaleid_unweighted 20  exclude_from_gpa 0  termbin_start_date 2000-01-01  termbin_end_date 9999-12-31
  S6  yearid 35  C1  Q4  potential_credit_hours 35.0  y1_letter_grade B  y1_grade_points 3.0  y1_grade_points_unweighted 3.0  courses_gradescaleid 10  courses_gradescaleid_unweighted 20  exclude_from_gpa 0  termbin_start_date 2000-01-01  termbin_end_date 9999-12-31
  S6  yearid 35  C2  Q4  potential_credit_hours 35.0  y1_letter_grade B  y1_grade_points 3.0  y1_grade_points_unweighted 3.0  courses_gradescaleid 10  courses_gradescaleid_unweighted 99  exclude_from_gpa 0  termbin_start_date 2000-01-01  termbin_end_date 9999-12-31

base_powerschool__student_enrollments (rn_year 1, ay2025, schoolid 101):
  S1, S2, S3, S4, S6   (S5 intentionally absent — no current enrollment)
```

Expected (`expect`, every row lists the same three asserted columns):

```text
  S1  potential_gpa_credits_current_year 35.0  gpa_needed_for_cumulative_3_0  4.0  is_cumulative_3_0_attainable true
  S2  potential_gpa_credits_current_year 35.0  gpa_needed_for_cumulative_3_0  3.0  is_cumulative_3_0_attainable true
  S3  potential_gpa_credits_current_year 35.0  gpa_needed_for_cumulative_3_0 -1.0  is_cumulative_3_0_attainable true
  S4  potential_gpa_credits_current_year 35.0  gpa_needed_for_cumulative_3_0  6.0  is_cumulative_3_0_attainable false
  S5  potential_gpa_credits_current_year null  gpa_needed_for_cumulative_3_0 null  is_cumulative_3_0_attainable null
  S6  potential_gpa_credits_current_year 70.0  gpa_needed_for_cumulative_3_0  3.0  is_cumulative_3_0_attainable null
```

Replace the unit-test `description` with:

```text
Needed-GPA algebra and attainability flag on an unweighted basis. Student 1
(junior, prior two A-years and one F-year over 105 credits, 35 current credits)
needs a 4.0 this year — exactly the unweighted scale max, so attainable. Student
2 (freshman, no prior years) needs exactly 3.0. Student 3 (prior four A-years
over 140 credits) needs -1.0 — already guaranteed, still attainable. Student 4
(prior one F-year over 35 credits) needs 6.0 — above the 4.0 unweighted scale
max, not attainable. Student 5 has no current-year enrollment — needed and flag
are NULL. Student 6 has one current course on an unresolvable unweighted grade
scale (orphaned gradescaleid) — needed is still computed but the flag is NULL
because the max attainable unweighted GPA is unknowable.
```

The math each row verifies (needed = (3.0 x (cr_prior + cr_current) − unweighted
prior points) / cr_current; ceiling = credit-weighted max unweighted grade
points across current courses):

```text
S1: (3.0*(105+35) - (140+140+0)) / 35 = 140/35 = 4.0 ; ceiling 4.0 -> attainable
S2: (3.0*(0+35)   - 0)          / 35 = 105/35 = 3.0 ; ceiling 4.0 -> attainable
S3: (3.0*(140+35) - 560)        / 35 = -35/35 = -1.0; ceiling 4.0 -> attainable
S4: (3.0*(35+35)  - 0)          / 35 = 210/35 = 6.0 ; ceiling 4.0 -> NOT attainable
S6: (3.0*(0+70)   - 0)          / 70 = 210/70 = 3.0 ; C2 unweighted scale unresolvable -> flag NULL
```

- [ ] **Step 2: Run the unit test — confirm it FAILS**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters-feat-claude-gpa-needed-unweighted-basis
uv run dbt deps --project-dir src/dbt/kippnewark
uv run dbt test --select unit_gpa_cumulative_needed_gpa \
  --project-dir src/dbt/kippnewark \
  --defer --state /workspaces/teamster/src/dbt/kippnewark/target/prod \
  --favor-state --target dev
```

Expected: FAIL — the model still computes the weighted basis, so S1/S3/S4/S6
expects don't match. (If the selector matches nothing, fall back to
`dbt build --select int_powerschool__gpa_cumulative ...` with the same flags.)

- [ ] **Step 3: Apply the six model edits**

In `int_powerschool__gpa_cumulative.sql`:

Edit 1 — `grades_union` branch 1 (the `where sg.storecode = 'Y1'` branch), the
`gpa_points_projected_max` line:

```text
-- before
if(sg.excludefromgpa = 0, sg.gpa_points, null) as gpa_points_projected_max,
-- after
if(sg.excludefromgpa = 0, su.grade_points, null) as gpa_points_projected_max_unweighted,
```

Edit 2 — `grades_union` branch 2 (the `base_powerschool__final_grades` branch):
the max-points expression and its join.

```text
-- before (expression)
if(
    fg.y1_letter_grade is null, null, gsm.max_grade_points
) as gpa_points_projected_max,
-- after
if(
    fg.y1_letter_grade is null, null, gsm_u.max_grade_points
) as gpa_points_projected_max_unweighted,

-- before (join)
left join gradescale_max as gsm on fg.courses_gradescaleid = gsm.gradescaleid
-- after
left join gradescale_max as gsm_u
    on fg.courses_gradescaleid_unweighted = gsm_u.gradescaleid
```

Edit 3 — `grades_union` branch 3 (the `storecode = 'Q2'` semester-1 branch):

```text
-- before
null as gpa_points_projected_max,
-- after
null as gpa_points_projected_max_unweighted,
```

Edit 4 — `with_weighted_points`:

```text
-- before
(
    potentialcrhrs_projected * gpa_points_projected_max
) as weighted_points_projected_max,
-- after
(
    potentialcrhrs_projected * gpa_points_projected_max_unweighted
) as unweighted_points_projected_max,
```

Edit 5 — `points_rollup`: replace the `weighted_points_prior`,
`weighted_points_projected_max_current`, and `potentialcrhrs_current_max_known`
sums with unweighted equivalents (leave the all-years
`sum(unweighted_points) as unweighted_points` untouched — it feeds
`cumulative_y1_gpa_unweighted`):

```text
-- weighted_points_prior  ->  unweighted_points_prior
sum(
    if(
        academic_year < {{ var("current_academic_year") }},
        unweighted_points,
        null
    )
) as unweighted_points_prior,

-- weighted_points_projected_max_current  ->  unweighted_points_projected_max_current
sum(
    if(
        academic_year = {{ var("current_academic_year") }},
        unweighted_points_projected_max,
        null
    )
) as unweighted_points_projected_max_current,

-- potentialcrhrs_current_max_known  ->  potentialcrhrs_current_max_known_unweighted
sum(
    if(
        academic_year = {{ var("current_academic_year") }}
        and unweighted_points_projected_max is not null,
        potentialcrhrs_projected,
        null
    )
) as potentialcrhrs_current_max_known_unweighted,
```

Edit 6 — `needed_gpa`: repoint both derivations.

```text
safe_divide(
    (3.0 * (coalesce(potentialcrhrs_prior, 0) + potentialcrhrs_current))
    - coalesce(unweighted_points_prior, 0),
    potentialcrhrs_current
) as gpa_needed_raw,

if(
    coalesce(potentialcrhrs_current_max_known_unweighted, 0)
    = coalesce(potentialcrhrs_current, 0),
    safe_divide(
        unweighted_points_projected_max_current, potentialcrhrs_current
    ),
    null
) as gpa_max_current_raw,
```

After these edits, `weighted_points_prior`, `gpa_points_projected_max`,
`weighted_points_projected_max`, `weighted_points_projected_max_current`, and
`potentialcrhrs_current_max_known` should have zero remaining references.
Verify:

```bash
grep -nE '\bweighted_points_(prior|projected_max)|\bgpa_points_projected_max\b|\bpotentialcrhrs_current_max_known\b' \
  src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql
```

Expected: no matches. Boundary rules differ per name: the leading `\b` on
`weighted_points_*` blocks matching inside `unweighted_points_*` (the `un`
prefix is a word char, so no boundary), and the group has no trailing anchor so
it still catches `weighted_points_projected_max_current`; the trailing `\b` on
the other two blocks matching their new `..._unweighted` suffixed names.

- [ ] **Step 4: Update the two column descriptions + the model description**

In `.../properties/int_powerschool__gpa_cumulative.yml`:

`gpa_needed_for_cumulative_3_0` description:

```text
Unweighted Y1 GPA the student must average across all current-year GPA credits
to finish with a projected cumulative Y1 GPA (unweighted) of exactly 3.00.
Computed as (3.0 x (prior credits + current credits) - prior unweighted points)
/ current credits. Assumes the current credit denominator stays fixed — course
adds/drops move the target. Negative values mean 3.00 is already guaranteed;
values above the student's unweighted scale maximum are not attainable this year.
NULL when the student has no current-year GPA credits.
```

`is_cumulative_3_0_attainable` description:

```text
True when `gpa_needed_for_cumulative_3_0` is less than or equal to the
credit-weighted maximum unweighted GPA achievable across the student's
current-year courses (each in-progress course capped at the max grade points of
its unweighted grade scale; already-stored current-year grades locked at their
actual unweighted points). NULL when the needed value is NULL, or when any
in-progress course's unweighted grade scale cannot be resolved — the max is then
unknowable, so the flag reads unknown rather than a misstated false.
```

Model-level description: change the closing clause "the needed-GPA /
attainability pair for finishing with a 3.00 cumulative" to "the needed-GPA /
attainability pair for finishing with a 3.00 unweighted cumulative."

- [ ] **Step 5: Run the unit test — confirm it PASSES**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters-feat-claude-gpa-needed-unweighted-basis
uv run dbt test --select unit_gpa_cumulative_needed_gpa \
  --project-dir src/dbt/kippnewark \
  --defer --state /workspaces/teamster/src/dbt/kippnewark/target/prod \
  --favor-state --target dev
```

Expected: PASS (1 of 1). If a row mismatches, re-check the arithmetic block in
Step 1 against the model output before touching expects.

- [ ] **Step 6: Build the model + run its data tests on real data**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters-feat-claude-gpa-needed-unweighted-basis
uv run dbt build --select int_powerschool__gpa_cumulative \
  --project-dir src/dbt/kippnewark \
  --defer --state /workspaces/teamster/src/dbt/kippnewark/target/prod \
  --favor-state --target dev
```

Expected: model builds; `dbt_utils.unique_combination_of_columns` (studentid,
schoolid) and the `not_null` (where `gpa_needed_for_cumulative_3_0 is not null`)
on `is_cumulative_3_0_attainable` pass.

- [ ] **Step 7: Lint the changed files**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters-feat-claude-gpa-needed-unweighted-basis
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml </dev/null
```

Expected: no issues (or only auto-fixable fmt, which the pre-commit hook
applies).

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters-feat-claude-gpa-needed-unweighted-basis \
  add src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql \
      src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml
git -C /workspaces/teamster/.worktrees/anthonygwalters-feat-claude-gpa-needed-unweighted-basis \
  commit -m "feat(powerschool): unweighted basis for needed-Y1 GPA and attainability

Refs #4528"
```

### Task 2: Real-data smoke validation (no code change)

**Files:** none (validation only).

- [ ] **Step 1: Build a backtest against completed AY2025**

`current_academic_year` defaults to 2026 (no data yet), so exercise the logic
against the completed year with a var override:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters-feat-claude-gpa-needed-unweighted-basis
uv run dbt build --select int_powerschool__gpa_cumulative \
  --project-dir src/dbt/kippnewark \
  --defer --state /workspaces/teamster/src/dbt/kippnewark/target/prod \
  --favor-state --target dev --vars '{current_academic_year: 2025}'
```

Note: for a completed year the in-progress branch (branch 2) is empty, so
current-year credits come from stored 2025 Y1 grades (branch 1, ceiling locked
at actual). The unit test covers the in-progress ceiling path; this covers the
real-data stored path.

- [ ] **Step 2: Sanity-check the distribution**

Query the dev table (find schema via
`INFORMATION_SCHEMA.SCHEMATA like '%kippnewark%'`; build lands in
`zz_<user>_kippnewark`). Confirm: `gpa_needed_for_cumulative_3_0` is populated
and mostly in a plausible range; `is_cumulative_3_0_attainable` is a sensible
mix of true/false/null; every row with `is_cumulative_3_0_attainable = false`
has `gpa_needed_for_cumulative_3_0` above the unweighted scale max (~4.0+).
Record the counts in the task report — do not paste student-level PII.

### Task 3: Push and open PR 1

- [ ] **Step 1: Lint-gate and push the branch**

Confirm dbt Cloud CI is not mid-run for this branch, then:

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters-feat-claude-gpa-needed-unweighted-basis push -u origin anthonygwalters/feat/claude-gpa-needed-unweighted-basis
```

- [ ] **Step 2: Open the PR**

Use `.github/pull_request_template.md` as the body; reference the spec and
`Refs #4528`. Note in the body: value-only package change (kipptaf dbt Cloud CI
is a trivial no-op; the correction is exercised by Dagster's district prod
rebuild), and that PR 2 (the extract columns) follows once this rebuilds in
prod.

---

## PR 2 — extract display columns (GATED: do not start until PR 1 is merged and the district `int_powerschool__gpa_cumulative` tables have rebuilt in prod)

PR 2 reads the corrected `gpa_needed_for_cumulative_3_0` from prod, so it cannot
be validated until PR 1's values land. When starting PR 2, first
`git fetch origin main && git merge origin/main` in a fresh worktree, then
**re-read the current `rpt_tableau__student_course_grades.sql`** — line numbers
below are from the pre-PR-1 state and may drift.

### Task 4: Add `gpa_y1_weighted_target` and `is_on_pace_cumulative_3_0`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml`

**Interfaces:**

- Consumes (already in the model): `s.gpa_needed_for_cumulative_3_0` (from the
  `gc` join, now unweighted), `s.gpa_y1`, `s.gpa_y1_unweighted`.
- Produces: `gpa_y1_weighted_target` (float64), `is_on_pace_cumulative_3_0`
  (boolean).

- [ ] **Step 1: Derive both columns in the CTE that already computes `gpa_y1` /
      `gpa_y1_unweighted`**

Per the SQL guide (derive in a CTE, reference plain downstream; max 1 level
nesting), compute in the CTE where `gpa_y1` and `gpa_y1_unweighted` are named:

```text
gpa_needed_for_cumulative_3_0 + (gpa_y1 - gpa_y1_unweighted) as gpa_y1_weighted_target,
gpa_y1_unweighted >= gpa_needed_for_cumulative_3_0 as is_on_pace_cumulative_3_0,
```

Then project both in the final `SELECT`, honoring ST06 ordering
(`gpa_y1_weighted_target` in the nested-function/arithmetic group,
`is_on_pace_cumulative_3_0` in the logicals group).

- [ ] **Step 2: Add both to the contract/properties with descriptions**

`gpa_y1_weighted_target` (float64): "Weighted Y1 GPA to show the student as this
year's target — the unweighted Y1 they need (`gpa_needed_for_cumulative_3_0`)
plus their realized weighting spread (`gpa_y1 - gpa_y1_unweighted`). Meeting it
in weighted terms is equivalent to reaching the unweighted cumulative 3.0.
Undefined until current-year grades exist."

`is_on_pace_cumulative_3_0` (boolean): "True when the student's unweighted Y1
(`gpa_y1_unweighted`) is at or above the unweighted Y1 they need
(`gpa_needed_for_cumulative_3_0`) — i.e., on pace for an unweighted cumulative
3.0. Aggregates to the cohort on-pace rate."

- [ ] **Step 3: Update any extract unit test**

If `rpt_tableau__student_course_grades` has a unit test, add both columns to its
`expect` rows (every row must list the same columns). Run the directory's unit
tests (`--select "test_type:unit,extracts.tableau"`).

- [ ] **Step 4: Build, tie out, lint, commit, push, open PR 2**

Build the extract
(`dbt build --select rpt_tableau__student_course_grades --project-dir src/dbt/kipptaf --defer --state <abs prod manifest> --favor-state --target dev`).
Tie-out on real data: for populated rows, `is_on_pace_cumulative_3_0` equals
`gpa_y1 >= gpa_y1_weighted_target` (spread cancels) and equals
`gpa_y1_unweighted >= gpa_needed_for_cumulative_3_0`. Lint, commit
(`Refs #4528`), push, open PR 2.
