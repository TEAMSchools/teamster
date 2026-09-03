# Student-grain GPA goal definitions

Refs [#5097](https://github.com/TEAMSchools/teamster/issues/5097).

## Problem

The Cumulative GPA Monitor reads two Tableau data sources.
`rpt_tableau__gpa_cumulative_year` supplies student rows.
`rpt_tableau__gpa_goals` supplies goal rates. A Tableau filter belongs to one
data source, so nothing on the dashboard can filter both at once.

The two models name the same concepts differently. Grade level is `grade_level`
(integer) on one and `grade_band` (string) on the other. School is `school` on
one and `schoolid` on the other. A quick filter on either field moves half the
dashboard and leaves the rest describing a different cohort, with nothing on
screen to say so.

The build works around that in four places:

- Grade uses a parameter plus a matching `Grade filter` calculation on each data
  source, because no single filter can drive both.
- School has no workaround. `rpt_tableau__gpa_goals` carries `schoolid` but no
  `school`, so the workbook hard-codes three school ids in a `CASE`. The same
  `CASE` already exists in the workbook, commented `// MUST BE DEPRECATED`.
- Network-level goal rows carry a null `region`. A Tableau user filter on
  `region` drops every one of them, so both goal tiles go blank for every
  non-admin user. Tableau Desktop cannot reproduce that failure.
- The headline band mixes a rate the dashboard computes with a rate the goals
  model precomputed. The first responds to filters; the second does not.

Seven of the 50 calculated fields in the build exist only to bridge the two
sources: `Year filter`, `Grade`, `Grade sort`, `Grade filter`,
`Network or region row`, `School row` and `School (goals)`.

## What the dashboard needs

A student row that knows its own goal. Not the goal _rate_ — the goal
_definition_: the threshold a student must clear, and the target share of
students expected to clear it at each organizational rung.

Carrying precomputed rates instead would reintroduce the same class of bug in a
new place. `AVG(metric_rate_org)` does not respond to a school filter, because
the value was fixed upstream. It would read as a bug the first time anyone
filtered. A goal proportion is a target and is _supposed_ to hold still, so it
is safe to carry. The actual rate is computed in Tableau from the student rows
already on the view.

## Why this ships as a wrapper, not a change to the extract

The obvious design adds the goal columns to `rpt_tableau__gpa_cumulative_year`.
Three facts, discovered after that design was drafted, rule it out for now.

**The extract is a view.** `INFORMATION_SCHEMA` reports `table_type = VIEW`. It
deploys as `create or replace view`, so new logic is live the instant Dagster
materializes it. There is no prior copy to fall back on, and a data problem is
not catchable at build time the way it is for a table.

**Its uniqueness test only warns.** The project sets
`data_tests: +severity: warn` and the `dbt_utils.unique_combination_of_columns`
test on `(student_number, academic_year)` carries no override. A fan-out logs a
warning and the run continues.

**The published workbook asserts that uniqueness to Tableau.** The
`rpt_tableau__student_course_grades+` data source relates course grades to this
model on `student_number`, `academic_year` and `schoolid`, with the
`rpt_tableau__gpa_cumulative_year` endpoint declared `unique-key='true'`.
Tableau has been told that side cannot duplicate, so it skips the defensive
aggregation it would otherwise apply.

Together those mean a bad join key would swap a view in place, warn rather than
fail, and silently multiply student counts on the published Academic Health Home
and Academic Health Schools dashboards. Reverting the view is fast, but a
Tableau extract refresh inside the bad window bakes the inflated rows into the
published extract, where they survive the revert until the next successful
refresh.

The dashboard this design serves is new and unpublished. The models it would
modify are neither. So the goal columns land on a new wrapper that nothing
published reads, and the extract is left alone until the change can be made
behind proper controls.

`rpt_` models referencing other `rpt_` models are an established pattern in this
project — ten exist today, three of them inside `extracts/tableau/`
(`rpt_tableau__survey_completion` reads `rpt_tableau__survey_links`, which reads
`rpt_tableau__survey_responses`).

## Measured

Figures read 2026-09-01.

The goal definitions in `int_google_sheets__gpa_goals` cover two metrics at
three rungs, with one band per grade:

| Metric                      | Rungs present       | Grades        | Threshold | Direction |
| --------------------------- | ------------------- | ------------- | --------- | --------- |
| `cumulative_gpa_unweighted` | org, region, school | 9, 10, 11, 12 | 3         | `>=`      |
| `y1_gpa_weighted`           | org, school         | 9, 10, 11     | 3         | `>=`      |

`y1_gpa_weighted` has no region rung in either 2025 or 2026. That is the data,
not a gap to paper over. No grade band spans more than one grade today, so the
`grade_level between grade_low and grade_high` join matches at most one row per
rung.

`rpt_tableau__gpa_cumulative_year` holds 8,582 rows for 2026, with 8,582
distinct `student_number`. The model selects `rn_year = 1` enrollments, so
`student_number` plus `academic_year` is a unique key.

### Miami cannot reach either model

`kippmiami` has no powerschool package — its SIS moved to Focus (#4441).
`rpt_tableau__gpa_cumulative_year` contains only `kippnewark` and `kippcamden`
rows. `int_gpa__goal_student_metrics` joins `int_powerschool__gpa_term`, which
has no Miami rows either.

Miami opened a high school in 2026 with about 114 grade 9 students. They appear
in `int_gpa__goal_student_metrics` because that model has no region filter, and
land in `n_students_in_grain` with a null GPA. `metric_rate` divides by
`n_students_measured` and is unaffected.

Two consequences. The `region in ('Newark', 'Camden')` filter on
`rpt_tableau__gpa_cumulative_year` is redundant with its own source data;
removing it would add zero rows. And the population question that looked like
the hard part is not one — both sides bottom out in the same powerschool GPA
computation, which is why measured counts match exactly at every grade: 509,
491, 420, 410.

Miami's GPA pipeline is offline until at least Q2. This design adds no region
filter anywhere, so Miami appears on its own when that lands.

## New model 1 — `int_gpa__student_goal_definitions`

In `src/dbt/kipptaf/models/gpa/intermediate/`.

Grain: `student_number` by `academic_year` by `metric`.

| Column                   | Type    | Source                     |
| ------------------------ | ------- | -------------------------- |
| `academic_year`          | int64   | enrollments                |
| `student_number`         | int64   | enrollments                |
| `metric`                 | string  | org-rung goal              |
| `threshold`              | numeric | org-rung goal              |
| `direction`              | string  | org-rung goal              |
| `higher_is_better`       | boolean | org-rung goal              |
| `goal_proportion_org`    | numeric | org-rung goal              |
| `goal_proportion_region` | numeric | region-rung goal, nullable |
| `goal_proportion_school` | numeric | school-rung goal, nullable |

The model drives from `int_extracts__student_enrollments` at `rn_year = 1`. It
inner joins the org-rung goal on `academic_year` and
`grade_level between grade_low and grade_high`, then left joins the region and
school rungs on the same predicate plus `region` and `schoolid` respectively.

The inner join on the org rung is what scopes the population. A student in a
grade with no goal produces no row, so grades K through 8 drop out without a
`school_level` filter and without naming a region. The left joins are why
`y1_gpa_weighted` lands a null `goal_proportion_region`.

`threshold`, `direction` and `higher_is_better` come from the org rung. All
three are identical across rungs today. Reading them from one place keeps the
model from implying they can differ.

### Overlapping grade bands fail the build

Nothing in `int_google_sheets__gpa_goals` prevents a `9-12` band alongside an
`11-11` band. The between-join would then match two rows for one student at one
rung, and the uniqueness test fails at build time.

That is the intended behaviour. The alternative — a most-specific-band-wins
tie-break — would silently absorb a data entry mistake in a Google Sheet that
Ops edits directly, and produce a number nobody could trace. A build failure
names the problem.

### Tests

- `dbt_utils.unique_combination_of_columns` on `academic_year`,
  `student_number`, `metric`, at `severity: error`. This test is what makes the
  wrapper's join provably one-to-at-most-one, so the override is required, not
  stylistic.
- `not_null` on `academic_year`, `student_number` and `metric`, at
  `severity: error`. All three are join keys.
- A new singular test: no school-rung or region-rung goal exists without a
  matching org-rung goal at the same `academic_year`, `metric` and grade band.

The singular test guards the inner join. If a school-level goal is ever entered
without its org-level parent, those students vanish from this model with no
error. That is the one failure mode the design cannot detect on its own.

`goal_proportion_org` gets no `not_null` test. The inner join makes it
non-nullable by construction, and the repo forbids a test that cannot fail.

## New model 2 — `rpt_tableau__gpa_goal_progress`

In `src/dbt/kipptaf/models/extracts/tableau/`. Grain: `student_number` by
`academic_year`, matching `rpt_tableau__gpa_cumulative_year` exactly.

```sql
select
    <every column of rpt_tableau__gpa_cumulative_year, by name>,

    gd.threshold as gpa_goal_threshold,
    gd.goal_proportion_org as gpa_goal_proportion_org,
    gd.goal_proportion_region as gpa_goal_proportion_region,
    gd.goal_proportion_school as gpa_goal_proportion_school,
from {{ ref("rpt_tableau__gpa_cumulative_year") }} as cy
left join
    {{ ref("int_gpa__student_goal_definitions") }} as gd
    on cy.student_number = gd.student_number
    and cy.academic_year = gd.academic_year
    and gd.metric = 'cumulative_gpa_unweighted'
```

**Every passthrough column keeps its name exactly.** Tableau's Replace Data
Source only preserves calculated fields when field captions match, so any rename
here becomes hand-rebuilt calculations at merge time.

The four goal columns take the names they will carry on
`rpt_tableau__gpa_cumulative_year` after the merge, for the same reason.

Contract enforced, per the `extracts/` directory config. Uniqueness test on
`(student_number, academic_year)` at `severity: error`.

## Downstream impact

Nothing published changes. `rpt_tableau__gpa_cumulative_year`,
`rpt_tableau__gpa_goals` and `rpt_tableau__student_course_grades` are untouched,
so Academic Health Home and Academic Health Schools cannot be affected by this
work.

The Cumulative GPA Monitor reads `rpt_tableau__gpa_goal_progress` alone. It
drops all seven bridging calculations. Grade becomes a real filter. The
three-school `CASE` is deleted. The null-region user-filter trap disappears,
because the goals data source is no longer on the dashboard. The actual rate is
computed from student rows, so it responds to every filter.

`rpt_tableau__student_course_grades` can later join
`int_gpa__student_goal_definitions` filtered to `metric = 'y1_gpa_weighted'`.
That is why the intermediate carries `metric` as a row rather than widening the
column list per metric.

## Verification

- `dbt build --select int_gpa__student_goal_definitions+` passes, including both
  uniqueness tests and the new singular test.
- `int_gpa__student_goal_definitions` filtered to
  `metric = 'cumulative_gpa_unweighted'` has at most one row per
  `(student_number, academic_year)`. Assert this directly rather than inferring
  it from a row count.
- `rpt_tableau__gpa_goal_progress` and `rpt_tableau__gpa_cumulative_year` have
  identical row counts for every academic year, not only 2026.
- Every passthrough column name on `rpt_tableau__gpa_goal_progress` matches
  `rpt_tableau__gpa_cumulative_year` exactly. Compare column lists from
  `INFORMATION_SCHEMA.COLUMNS`, do not eyeball.
- For 2026, `gpa_goal_proportion_org` reproduces the published goals: 0.69 at
  grade 9, 0.64 at grade 10, 0.60 at grade 11, 0.56 at grade 12.
- Grades K through 8 have null goal columns, and no student-year row is lost.
- The share of students at or above `gpa_goal_threshold`, computed per grade,
  matches `metric_rate` in `rpt_tableau__gpa_goals` to within the rounding that
  model applies.

## The merge, later

Folding the wrapper into `rpt_tableau__gpa_cumulative_year` is a separate change
and is expected to happen. It requires, in order:

1. A standalone PR raising the extract's uniqueness test to `severity: error`.
   No other change in it. Merging it green proves the model is unique today and
   arms the alarm before anything risky lands.
2. Moving the left join into the extract and adding the four columns to its
   contract yml.
3. Pausing the `rpt_tableau__student_course_grades+` extract refresh for the
   deploy window, verifying row counts in BigQuery, then resuming. This is the
   only control that stops a bad view being baked into the published extract.
4. Tableau **Replace Data Source** on the Cumulative GPA Monitor.
5. Disabling `rpt_tableau__gpa_goal_progress` with `config: enabled: false`,
   including its tests. Retire, never delete. In the same change, repoint the
   `cumulative_gpa_monitor` exposure's `depends_on` back to
   `rpt_tableau__gpa_cumulative_year` — dbt errors when an exposure depends on a
   disabled node, so the disable and the repoint must land together.

Until then the wrapper carries a maintenance tax: a column added to
`rpt_tableau__gpa_cumulative_year` must be added to the wrapper's explicit
select list too, since the repo forbids `select *` in a final `rpt_` select.

## Out of scope

- Modifying `rpt_tableau__gpa_cumulative_year` in any way. Deferred to the merge
  above, deliberately.
- `n_students_in_grain` counting students the pipeline cannot measure. Real, but
  narrower, and nothing on the dashboard reads it.
- Adding `school` to `rpt_tableau__gpa_goals`. The Cumulative GPA Monitor stops
  needing it, but `GPA Goals - Y1` on Academic Health Home still reads that
  table and still carries the same hard-coded `CASE`. Worth doing separately.
- `gpa_gap_to_3_0` on the student row. A one-line addition, unrelated to goal
  definitions; ship it with the `school` change.
- Renaming `cumulative_y1_gpa_unweighted_as_of_today`, which reads as "including
  today's work" but means "from Y1 grades already posted".
- Any Tableau workbook change. The dashboard ships against the two-source design
  first; rebuilding it on one source is follow-on work.
