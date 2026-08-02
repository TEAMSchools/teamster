# Category drivers at Y1, and a temporary prior-year running-grade backfill

Design for [#4687](https://github.com/TEAMSchools/teamster/issues/4687). Two
changes to `rpt_tableau__student_course_grades`, shipping in one PR, with
deliberately different lifespans.

## Context

The GPA drill-down dashboard (`Academic Health Schools`) is driven by a
`p_Marking_Period` parameter. Two separate problems make it behave badly at the
marking periods people actually use.

**`Category Driving Gap` reads `not available` at Y1.** Y1 is the primary
viewing level, so the column is effectively dead. Asking users to switch to a
quarter to see it is a real block on adoption.

**Adopting the running course grade would blank the prior year.** The columns
that carry a genuine year-to-date grade — `y1_course_in_progress_*` — are
populated only for the year in progress. AY2026 has no posted grades yet, so
summer stakeholder training runs on AY2025, where those columns are entirely
null.

### Verified facts this design rests on

All measured 2026-08-01 against production.

| Fact                                                        | Evidence                                                                                                                           |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Y1 rows carry no category data at all                       | `category_name_code` null on all 38,281 AY2025 Y1 rows                                                                             |
| A year-level category percent already exists                | `category_y1_percent_grade_running` populated on quarter rows; at Q4 it equals `category_y1_percent_grade_current` at 116,011 rows |
| Attaching categories to Y1 would fan out                    | 38,281 Y1 rows against 149,423 Q4 rows, roughly 3.9x                                                                               |
| `y1_course_in_progress_*` is null for prior years           | 0 populated rows across every AY2025 marking period                                                                                |
| Course reconstruction is close                              | Simple four-quarter average lands within 0.5 points of the stored Y1 for 20,884 of 21,533 Newark full-year courses, 97.0 percent   |
| GPA reconstruction is close in aggregate, loose per student | Distribution within a few points; 222 to 748 students cross the 3.0 line depending on quarter                                      |

The prior-year flatness is structural, not a defect. `int_powerschool__gpa_term`
builds historical quarters by starting from the single Y1 storedgrades row and
doing `cross join unnest(["Q1", "Q2", "Q3", "Q4"])`. PowerSchool never stored an
as-of-Q1 year value, so it cannot be recovered — noted upstream as
[#4382](https://github.com/TEAMSchools/teamster/issues/4382).

## Change A — category drivers at Y1

Permanent. Fixes a real defect.

### Columns

Four columns at student-course grain, present on **every** row including Y1.

| Column                                | Type      | Meaning                                                               |
| ------------------------------------- | --------- | --------------------------------------------------------------------- |
| `lowest_category_y1_name`             | `string`  | category code with the lowest year-running percent                    |
| `lowest_category_y1_percent`          | `float64` | that percent                                                          |
| `lowest_category_recent_term_name`    | `string`  | category code with the lowest percent in the latest term holding data |
| `lowest_category_recent_term_percent` | `float64` | that percent                                                          |

Both drivers are read from the **same** latest term, so they describe one
moment. On a completed year that is Q4; on a live year, whichever quarter last
posted.

"Latest term holding data" means precisely: the highest `term` among category
rows where **at least one** of `category_quarter_percent_grade` or
`category_y1_percent_grade_running` is non-null. Rows with both null are
excluded from the ranking input entirely, so a term that exists but carries no
usable percent cannot win and blank out both drivers. One rule, applied once, so
the two drivers cannot land on different terms.

Two columns rather than one because the questions differ. The year-running
driver answers "across the year, what dragged this course down" and matches what
a Y1 view claims to show. The latest-quarter driver answers "what is the problem
right now" and is the intervention question.

### Construction

A ranking CTE computes three window functions over the category data, and the
next CTE filters and pivots. Window in one CTE, filtered by `WHERE` in the next
— no `QUALIFY`, per the SQL conventions.

```sql
category_ranked as (
    select
        studentid,
        _dbt_source_project,
        sectionid,
        yearid,
        category_name_code,
        category_quarter_percent_grade,
        category_y1_percent_grade_running,

        dense_rank() over (
            partition by studentid, _dbt_source_project, sectionid, yearid
            order by term desc
        ) as rn_latest_term,

        row_number() over (
            partition by studentid, _dbt_source_project, sectionid, yearid, term
            order by
                (category_y1_percent_grade_running is null) asc,
                category_y1_percent_grade_running asc,
                category_name_code asc
        ) as rn_lowest_y1,

        row_number() over (
            partition by studentid, _dbt_source_project, sectionid, yearid, term
            order by
                (category_quarter_percent_grade is null) asc,
                category_quarter_percent_grade asc,
                category_name_code asc
        ) as rn_lowest_quarter,
    from category_grades
    where
        category_quarter_percent_grade is not null
        or category_y1_percent_grade_running is not null
),
```

Then one row per student-section-year by conditional aggregation over
`where rn_latest_term = 1`.

Two details that would otherwise be wrong:

- **Null ordering.** BigQuery sorts `NULLS FIRST` ascending, so a category with
  a null percent would win "lowest" outright. The `(col is null) asc` leading
  term prevents that. Same idiom the repo prescribes for
  `dbt_utils.deduplicate`.
- **Ties.** `category_name_code` as the final tiebreaker makes the pick
  reproducible across rebuilds. The Tableau calc being replaced is not.

### Join

Joined on `(studentid, _dbt_source_project, sectionid, yearid)` — **without**
the term predicate. That omission is the whole point: it is what lets the
columns land on Y1 rows, where the existing `category_grades` join
(`s.quarter = c.term`) finds nothing.

The CTE emits one row per join key, so the join cannot change the row count.

### Tableau

Two calcs deleted outright:

- `Lowest Category % (course)`, a `FIXED` LOD
- `Category Driving Gap`, a `MIN(IF ...)` over categories

`Category Driving Gap` becomes a plain field reference. No LOD, no
marking-period dependency, no `not available` at Y1.

Genuine absence still reads as unavailable — a course with no gradebook
categories, or the current year before grades post. The difference is that it
now means "there is no category data" rather than "you picked the wrong marking
period".

## Change B — prior-year running backfill

**Temporary.** Must be removed. See _Removal_ below.

### Guiding principle

Set by the requester and load-bearing for every decision here: **the live year
must be correct; the backfill only has to exist and be labelled.** Strict
accuracy on prior years is explicitly not the goal. Stakeholders will be told in
training not to rely on these figures.

### Where it goes

Branch 3 of the `quarter_grades` CTE — the prior-year storedgrades branch.
Branches 1 and 2 read the live gradebook and are untouched, which is what makes
this incapable of corrupting current-year data and makes removal a revert of one
block.

Replaces:

```sql
cast(null as float64) as y1_course_in_progress_percent_grade_adjusted,
cast(null as string) as y1_course_in_progress_letter_grade_adjusted,
```

### Course grades — anchored

Running average of stored quarter percents, partitioned by student-course,
ordered `Q1` through `Q4`, with the `Q4` value overridden by the stored `Y1`
percent.

- `Q1` exact by definition — running through Q1 is Q1.
- `Q4` exact by anchoring.
- `Q2` and `Q3` approximate.

Simple rather than credit-weighted average. The live-year calculation is
weighted, but the 97.0 percent agreement measured above shows the weights are
effectively uniform, so weighting adds complexity without accuracy.

The **letter** is the real work. The reconstructed percent has to be mapped back
through the course's grade scale. Storedgrades carries no
`courses_gradescaleid`, so this joins on `gradescale_name` — the pattern
`int_powerschool__gpa_term` and `rpt_deanslist__transcript_gpas` already use —
plus `_dbt_source_project`, because scale identifiers collide across districts.

This needs the **full** scale, not the whole-letter subset used by `need_next`.
The full scale is where the 119 degenerate bands live
(`max_cutoffpercentage = min_cutoffpercentage - 0.1`, produced by two items
sharing a cutoff). Those rows match nothing, so the risk is a coverage gap
rather than a fan-out — but full-scale coverage and uniqueness have **not** been
verified. That is a gating check, not an assumption.

### GPA — deliberately not anchored

Running from the per-term components already exposed on
`int_powerschool__gpa_term`:

```text
running_gpa(Qn) = sum(weighted_gpa_points_term through Qn)
                  / sum(total_credit_hours_term through Qn)
```

Anchoring `Q4` to the stored value was considered and **rejected**. The
reconstruction sits systematically below the stored Y1, because PowerSchool's
year letter grades are more generous than a running average of quarter points.
Unanchored, AY2025 high school reads:

```text
45.1  ->  46.7  ->  46.6  ->  48.2      stored Y1: 48.9
```

A rising trajectory that stops slightly short of the year value. Anchoring would
replace that final 48.2 with 48.9, inserting a step at Q4 that the underlying
data does not produce. The step is small at high-school grain — 0.7 points — and
larger across all students, where the same comparison runs 52.9, 54.2, 53.7,
56.1 against a stored 58.8. Either way it is an artifact of the anchor rather
than anything a student did, and a step at the last marking period is precisely
what a stakeholder builds a narrative around.

**Correction, recorded deliberately.** An earlier draft of this section cited
`50.1 -> 48.4 -> 46.1 -> 47.7` against `50.4` and argued the reconstruction
showed a year-long decline. Those were **AY2024** figures, produced by querying
`int_powerschool__gpa_term` at `yearid = 34`; the convention is
`yearid = academic_year - 1990`, so AY2025 is 35. The corrected AY2025 data
rises rather than declines. The decision not to anchor was re-confirmed against
these corrected numbers and stands, but the original justification was wrong and
is not preserved.

**This makes course grades and GPA asymmetric on purpose.** Course grades anchor
because the anchor is exact and free. GPA does not, because its anchor inserts a
step the data does not contain. Do not "fix" the inconsistency.

### Isolation from the current year — mandatory, and not automatic

The two halves of this backfill do **not** have the same protection, and the
difference is the single most important implementation constraint here.

**Course grades are structurally isolated.** `quarter_grades` branch 3 filters
`academic_year = current_academic_year - 1` while branches 1 and 2 filter
`= current_academic_year`. The branches are disjoint by `WHERE`, so a change
confined to branch 3 cannot reach a current-year row. No extra guard needed.

**GPA is not.** `gpa_y1` is assembled inside `student_roster` as
`if(term.quarter = 'Y1', gty.gpa_y1, gtq.gpa_y1)`, and the `gtq` join has no
year predicate — it joins for every academic year. A backfill written as a
conditional inside that expression would be only as safe as the condition.

**Required approach.** Put the reconstruction in its own CTE and gate the join
in the `ON` clause:

```sql
left join
    backfill_running_gpa as bfc
    on enr.studentid = bfc.studentid
    and enr.yearid = bfc.yearid
    and enr.schoolid = bfc.schoolid
    and enr._dbt_source_project = bfc._dbt_source_project
    and term.quarter = bfc.term_name
    and enr.academic_year = {{ var("current_academic_year") - 1 }}
```

Every current-year row then gets `NULL` from `pyr` by construction, and the
selection becomes a `coalesce` that falls through to the existing expression
untouched. This is the same gating pattern the model already applies to the
`gc`, `lb` and `gpq` joins, which each carry
`and enr.academic_year = {{ var("current_academic_year") }}` in `ON` so
prior-year rows keep their NULLs.

Isolation is a **verification requirement**, not just a coding style: every
current-year value of `gpa_y1`, `gpa_for_quarter` and `gpa_n_failing_y1` must be
byte-identical before and after. See _Verification_.

### Not backfilling `gpa_n_failing_y1`

It is flat on prior years, but the only sheets reading it are the landing-page
BANs, which carry no `MP Filter` and sit on a dashboard that does not expose
`p_Marking_Period`. Nothing would see it move.

## Verification

Four hard invariants. These must return zero, not "mostly".

| Check                      | Requirement                                                                                                                                                 |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Current-year isolation** | every current-year value of `gpa_y1`, `gpa_for_quarter`, `gpa_n_failing_y1` and `y1_course_in_progress_*` byte-identical before and after, zero rows differ |
| Q4 course anchor           | reconstructed percent equals the stored Y1 percent, zero exceptions                                                                                         |
| Q1 exactness               | running-through-Q1 equals Q1's own stored percent, zero exceptions                                                                                          |
| Letter coverage            | every reconstructed percent matches exactly one full-scale row, zero gaps and zero doubles                                                                  |

Isolation is listed first deliberately. The course-grade half inherits it from
the branch structure; the GPA half has it only from the `ON`-clause gate, so it
must be proven rather than assumed. Compare current-year rows between the dev
build and prod across those columns — any non-zero difference means the gate
leaked and the change does not ship.

Supporting checks:

- Population moves off zero for `y1_course_in_progress_*` on prior-year rows,
  and for all four category driver columns on Y1 rows.
- **No fan-out** — dev and prod return identical row counts and identical
  distinct composite-key counts. Both changes add joins; both must be neutral.
- The existing composite uniqueness test still warns at 12, the pre-existing
  `#3915` storedgrades count.
- **Regression check on the category driver** — at Q4 on a completed year,
  `lowest_category_recent_term_name` reproduces what the current
  `Category Driving Gap` calc already produces. Free ground truth from behaviour
  known to work.
- No row picked a null-percent category over a populated one.
- Course reconstruction accuracy re-characterised network-wide, not Newark-only.

## Removal

Change A is permanent. **Change B is not**, and the two ship together, so the
boundary has to be explicit or someone will remove the wrong one.

- Inline `TODO(#4687)` at the backfill block naming the Asana task.
- Asana task in `GPA and Gradebook Dashboard v3`, Phase 4.
- Column descriptions state that prior-year values are reconstructed and that Q2
  and Q3 are approximate.

No feature flag. Considered and rejected: the course-grade half lives in a
branch that cannot touch current-year data, so it never becomes actively wrong,
only unnecessary. The long-term fix is operational rather than code — next year
the dashboard falls into the normal pattern of refreshes being frozen at the end
of the academic year, at which point the prior year stops needing reconstruction
at all.

## Out of scope

- Moving the `F`/`S`/`H`/`W` category decode into the model. The workbook's
  `Category Label` calc keeps doing it; duplicating the mapping in SQL would
  create two places to maintain. Reasonable follow-up.
- The as-of versus period-only labelling work on M1, tracked separately in
  Asana.
- Any change to `src/dbt/powerschool/`. Both changes are achievable in kipptaf
  because `weighted_gpa_points_term`, `total_credit_hours_term` and
  `category_y1_percent_grade_running` are all already exposed.
