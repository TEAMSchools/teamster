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

Two consequences for this design. The `region in ('Newark', 'Camden')` filter on
`rpt_tableau__gpa_cumulative_year` is redundant with its own source data;
removing it would add zero rows. And the population question that looked like
the hard part is not one — both sides bottom out in the same powerschool GPA
computation, which is why measured counts match exactly at every grade: 509,
491, 420, 410.

Miami's GPA pipeline is offline until at least Q2. This design adds no region
filter anywhere, so Miami appears on its own when that lands.

## New model

`int_gpa__student_goal_definitions`, in
`src/dbt/kipptaf/models/gpa/intermediate/`.

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
  `student_number`, `metric`, at `severity: error`.
- `not_null` on `academic_year`, `student_number` and `metric`. All three are
  join keys.
- A new singular test: no school-rung or region-rung goal exists without a
  matching org-rung goal at the same `academic_year`, `metric` and grade band.

The singular test guards the inner join. If a school-level goal is ever entered
without its org-level parent, those students vanish from this model with no
error. That is the one failure mode the design cannot detect on its own.

`goal_proportion_org` gets no `not_null` test. The inner join makes it
non-nullable by construction, and the repo forbids a test that cannot fail.

## Extract change

`rpt_tableau__gpa_cumulative_year` gains one left join to
`int_gpa__student_goal_definitions` on `student_number` and `academic_year`,
filtered to `metric = 'cumulative_gpa_unweighted'`, projecting four columns:

- `gpa_goal_threshold`
- `gpa_goal_proportion_org`
- `gpa_goal_proportion_region`
- `gpa_goal_proportion_school`

Row count is unchanged. The join is one-to-at-most-one on a key that is unique
on both sides, and every existing column keeps its definition.

The `region in ('Newark', 'Camden')` filter stays. Removing it is a separate
decision with its own blast radius, and it adds no rows today.

## Downstream impact

The dashboard drops all seven bridging calculations. Grade becomes a real
filter. The three-school `CASE` is deleted. The null-region user-filter trap
disappears, because the goals data source is no longer on the dashboard. The
actual rate is computed from student rows, so it responds to every filter.

`rpt_tableau__gpa_goals` is unchanged and keeps serving Academic Health Home
through the `GPA Goals - Y1` data source. Nothing is deleted.

`rpt_tableau__student_course_grades` can later join the same model filtered to
`metric = 'y1_gpa_weighted'` and get its own goal columns. That is why the grain
carries `metric` as a row rather than widening the column list per metric.

## Verification

- `dbt build --select int_gpa__student_goal_definitions+` passes, including the
  uniqueness test and the new singular test.
- `rpt_tableau__gpa_cumulative_year` row count is identical before and after,
  for every academic year, not only 2026.
- For 2026, `goal_proportion_org` on the extract reproduces the published goals:
  0.69 at grade 9, 0.64 at grade 10, 0.60 at grade 11, 0.56 at grade 12.
- Grades K through 8 have null goal columns on the extract, and no student-year
  row is lost to the join.
- The share of students at or above `gpa_goal_threshold`, computed from extract
  rows per grade, matches `metric_rate` in `rpt_tableau__gpa_goals` to within
  the rounding that model applies.

## Out of scope

- `n_students_in_grain` counting students the pipeline cannot measure. Real, but
  narrower, and nothing on the dashboard reads it.
- Adding `school` to `rpt_tableau__gpa_goals`. This design removes the
  dashboard's need for it rather than fixing that model.
- The `region in ('Newark', 'Camden')` filter on the extract.
- Renaming `cumulative_y1_gpa_unweighted_as_of_today`, which reads as "including
  today's work" but means "from Y1 grades already posted".
- Any Tableau workbook change. The dashboard ships against the two-source design
  first; rebuilding it on one source is follow-on work.
