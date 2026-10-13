# PowerSchool Student Course Grades Package Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every PowerSchool-to-PowerSchool join behind
`rpt_tableau__student_course_grades` into one `powerschool` package model, read
through a kipptaf `union_relations` wrapper, with the extract row-identical to
prod for NJ.

**Architecture:** A new package model
`int_powerschool__student_course_grades_spine` at student x term x course x
category for the current and prior academic year, built from the consumer's
existing course-grain CTEs moved verbatim minus the cross-region plumbing. A
kipptaf wrapper unions the 3 NJ districts. The consumer keeps its student-grain
roster CTEs and left-joins the wrapper once, then the 2 kipptaf enrichment joins
that used to sit inside its `course_enrollments` CTE.

**Tech Stack:** dbt 1.x on BigQuery, `dbt_utils.union_relations`,
`dbt_utils.deduplicate`, `dbt_utils.unique_combination_of_columns`. Spec:
`docs/superpowers/specs/2026-09-14-powerschool-student-course-grades-design.md`.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package`,
  branch `cbini/refactor/claude-student-course-grades-package`. Every git call
  is `git -C <worktree>`; every path is under the worktree. See
  `.claude/rules/worktrees.md`.
- Open every file under `src/dbt/` with the Read tool, never `cat`.
- Package model years: `{{ var("current_academic_year") - 1 }}` through
  `{{ var("current_academic_year") }}`, in the package, not kipptaf.
- No `_dbt_source_project` or `_dbt_source_relation` inside the package model.
  One project is one region there.
- `section_or_period` stays in kipptaf. The package exports `section_number` and
  `external_expression` only (spec, "section_or_period stays in kipptaf").
- The consumer's select list, column order, and contract do not change.
- Uniqueness tests at `severity: warn` with the `TODO(#3915)` comment; the
  prior-year storedgrades double-write duplicates move with the data.
- No Miami. The wrapper unions `kippnewark_powerschool`,
  `kippcamden_powerschool`, `kipppaterson_powerschool` only.
- Verification runs against production relations only. No dev build, no `zz_stg`
  comparison.
- `dbt build --target staging` is a shared write. It needs the user's direct
  authorization in the turn before each call, one district per call, one call
  per Bash invocation with nothing chained.
- Lint before every push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.
- Commit messages via `.claude/scratch/commit-msg.txt` and `git commit -F`,
  ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File map

| Action | Path                                                                                                          | Responsibility                               |
| ------ | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| Create | `src/dbt/powerschool/models/sis/intermediate/int_powerschool__student_course_grades_spine.sql`                | every PowerSchool-internal course-grain join |
| Create | `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__student_course_grades_spine.yml`     | grain test, column descriptions              |
| Modify | `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml`                                                   | add the source table entry                   |
| Modify | `src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml`                                                   | add the source table entry                   |
| Modify | `src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml`                                                 | add the source table entry                   |
| Create | `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__student_course_grades_spine.sql`            | bare `union_relations` wrapper               |
| Create | `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__student_course_grades_spine.yml` | PII tag, 6-column grain test                 |
| Modify | `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`                              | roster plus wrapper plus 2 enrichment joins  |

---

### Task 1: The package model

**Files:**

- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__student_course_grades_spine.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__student_course_grades_spine.yml`
- Read for reference (do not modify):
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`
  lines 369 to 883, the CTEs being moved.

**Interfaces:**

- Consumes: package refs `base_powerschool__course_enrollments`,
  `base_powerschool__final_grades`, `stg_powerschool__storedgrades`,
  `int_powerschool__category_grades`, `int_powerschool__gradescaleitem_lookup`,
  `int_powerschool__terms`.
- Produces: relation `int_powerschool__student_course_grades_spine` in each NJ
  district's `kipp<district>_powerschool` dataset, grain
  `(studentid, yearid, quarter, course_number, category_name_code)`, columns
  listed in step 3. Tasks 2 and 3 depend on these exact column names.

- [ ] **Step 1: Confirm the package term spine yields Q1 to Q4 per school-year**

Run via the BigQuery MCP:

```sql
select term, count(distinct concat(schoolid, '-', yearid)) as n_school_years
from `teamster-332318`.`kippnewark_powerschool`.`int_powerschool__terms`
where yearid >= 35
group by term
order by term
```

Expected: rows for `Q1`, `Q2`, `Q3`, `Q4` with equal counts. If a fifth
storecode appears (an `E1` or `T1`), note it: the spine CTE in step 2 filters
`term like 'Q%'`, so it will be excluded, matching the consumer's
`int_students__terms` which carries quarters only.

- [ ] **Step 2: Write the package model SQL**

Create
`src/dbt/powerschool/models/sis/intermediate/int_powerschool__student_course_grades_spine.sql`:

```sql
with
    course_enrollments as (
        select
            cc_studentid as studentid,
            cc_yearid as yearid,
            cc_academic_year as academic_year,
            cc_schoolid as schoolid,
            cc_course_number as course_number,
            cc_sectionid as sectionid,
            cc_dateenrolled as date_enrolled,
            sections_dcid,
            sections_section_number as section_number,
            sections_external_expression as external_expression,
            courses_credittype as credit_type,
            courses_course_name as course_name,
            courses_excludefromgpa as exclude_from_gpa,
            teachernumber as teacher_number,
            teacher_lastfirst as teacher_name,
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            cc_academic_year >= {{ var("current_academic_year") - 1 }}
            and cc_academic_year <= {{ var("current_academic_year") }}
            and rn_course_number_year = 1
            and cc_sectionid > 0
            and cc_course_number not in (
                'LOG100',  -- Lunch
                'LOG1010',  -- Lunch
                'LOG11',  -- Lunch
                'LOG12',  -- Lunch
                'LOG20',  -- Early Dismissal
                'LOG22999XL',  -- Lunch
                'LOG300',  -- Study Hall
                'LOG9',  -- Lunch
                'SEM22106G1',  -- Advisory
                'SEM22106S1'  -- Not in SY24-25 yet
            )
    ),

    term_spine as (
        /* grain projection, not dup-masking: (schoolid, yearid, term) */
        select distinct schoolid, yearid, term as `quarter`,
        from {{ ref("int_powerschool__terms") }}
        where term like 'Q%'

        union all

        /* grain projection, not dup-masking: (schoolid, yearid) */
        select distinct schoolid, yearid, 'Y1' as `quarter`,
        from {{ ref("int_powerschool__terms") }}
    ),

    y1_final_grades as (
        select
            studentid,
            yearid,
            course_number,
            storecode,

            cast(`percent` as float64) as y1_course_final_percent_grade_adjusted,

            grade as y1_course_final_letter_grade_adjusted,
            earnedcrhrs as y1_course_final_earned_credits,
            potentialcrhrs as y1_course_final_potential_credit_hours,
            gpa_points as y1_course_final_grade_points,
        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode = 'Y1' and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    backfill_quarter_running as (
        /* TODO(#4687): TEMPORARY. Delete this CTE, backfill_course_anchored,
           backfill_running_course, and their use in quarter_grades branch 3
           once the dashboard runs on current-year data. Tracked in Asana under
           GPA and Gradebook Dashboard v3, Phase 4.

           Reconstructs a running year-to-date course percent for the prior
           year, which PowerSchool never stored. Q1 is exact by definition;
           Q2 and Q3 are approximations; Q4 is replaced by the stored Y1 value
           below so it matches exactly. Simple rather than credit-weighted
           average because the two agree to within half a point on 97.0 percent
           of courses. */
        select
            studentid,
            yearid,
            course_number,
            storecode,
            gradescale_name_unweighted,

            avg(`percent`) over (
                partition by studentid, yearid, course_number order by storecode
            ) as running_percent,
        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode in ('Q1', 'Q2', 'Q3', 'Q4')
            and academic_year = {{ var("current_academic_year") - 1 }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    backfill_y1_stored_raw as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running. */
        select
            studentid,
            yearid,
            course_number,
            gradescale_name_unweighted,
            dcid,

            `percent` as y1_stored_percent,
        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode = 'Y1' and academic_year = {{ var("current_academic_year") - 1 }}
    ),

    backfill_y1_stored as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running.

           dbt_utils.deduplicate guards the pre-existing #3915 storedgrades
           double-write, confirmed present on academic_year 2025 Y1 rows with
           genuinely conflicting percents rather than harmless repeats. Left
           un-deduplicated, this CTE's grain becomes a join key in
           backfill_course_anchored below, so one duplicate would multiply
           every quarter row for the course, not just the Y1 row it
           originated on. Highest dcid wins: sampled duplicate pairs cluster
           in two distinct dcid ranges, consistent with a later corrective
           re-import superseding an earlier one. */
        {{
            dbt_utils.deduplicate(
                relation="backfill_y1_stored_raw",
                partition_by="studentid, yearid, course_number",
                order_by="dcid desc",
            )
        }}
    ),

    backfill_course_anchored as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running.

           Q4 takes the stored Y1 percent verbatim so the reconstruction lands
           exactly on the year grade. The Y1 storecode row is unioned in
           carrying the same value, so the Y1 marking period and Q4 agree. */
        select
            r.studentid,
            r.yearid,
            r.course_number,
            r.storecode,
            r.gradescale_name_unweighted,

            if(
                r.storecode = 'Q4', y1.y1_stored_percent, r.running_percent
            ) as anchored_percent,
        from backfill_quarter_running as r
        left join
            backfill_y1_stored as y1
            on r.studentid = y1.studentid
            and r.yearid = y1.yearid
            and r.course_number = y1.course_number

        union all

        select
            studentid,
            yearid,
            course_number,

            'Y1' as storecode,

            gradescale_name_unweighted,
            y1_stored_percent as anchored_percent,
        from backfill_y1_stored
    ),

    backfill_running_course as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running.

           Bands the reconstructed percent back to a letter on the course's own
           scale. Joins on gradescale_name rather than gradescaleid, the pattern
           int_powerschool__gpa_term and rpt_deanslist__transcript_gpas already
           use for storedgrades. */
        select
            a.studentid,
            a.yearid,
            a.course_number,
            a.storecode,
            a.anchored_percent,

            gsi.letter_grade as anchored_letter_grade,
        from backfill_course_anchored as a
        left join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as gsi
            on a.gradescale_name_unweighted = gsi.gradescale_name
            and a.anchored_percent
            between gsi.min_cutoffpercentage and gsi.max_cutoffpercentage
    ),

    quarter_grades as (
        /* current year: live gradebook */
        select
            studentid,
            yearid,
            course_number,

            storecode as `quarter`,

            term_percent_grade_adjusted as quarter_course_percent_grade,
            term_letter_grade_adjusted as quarter_course_letter_grade,
            term_grade_points as quarter_course_grade_points,
            y1_percent_grade_adjusted as y1_course_in_progress_percent_grade_adjusted,
            y1_letter_grade_adjusted as y1_course_in_progress_letter_grade_adjusted,
            y1_grade_points as y1_course_in_progress_grade_points,
            y1_grade_points_unweighted as y1_course_in_progress_grade_points_unweighted,

            need_60,
            need_70,
            need_80,
            need_90,

            courses_gradescaleid,

        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and not is_dropped_section
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')

        union all

        /* current year: in-progress Y1 row */
        select
            studentid,
            yearid,
            course_number,

            'Y1' as `quarter`,

            y1_percent_grade_adjusted as quarter_course_percent_grade,
            y1_letter_grade_adjusted as quarter_course_letter_grade,
            y1_grade_points as quarter_course_grade_points,
            y1_percent_grade_adjusted as y1_course_in_progress_percent_grade_adjusted,
            y1_letter_grade_adjusted as y1_course_in_progress_letter_grade_adjusted,
            y1_grade_points as y1_course_in_progress_grade_points,
            y1_grade_points_unweighted as y1_course_in_progress_grade_points_unweighted,

            need_60,
            need_70,
            need_80,
            need_90,

            courses_gradescaleid,

        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and termbin_is_current
            and not is_dropped_section

        union all

        /* prior year: stored grades (Q1-Q4 term rows plus the stored Y1 row,
           which fills the quarter columns on Y1 rows like the in-progress
           branch does for the current year) */
        select
            sg.studentid,
            sg.yearid,
            sg.course_number,

            sg.storecode as `quarter`,

            cast(sg.`percent` as float64) as quarter_course_percent_grade,
            sg.grade as quarter_course_letter_grade,
            sg.gpa_points as quarter_course_grade_points,

            bfc.anchored_percent as y1_course_in_progress_percent_grade_adjusted,
            bfc.anchored_letter_grade as y1_course_in_progress_letter_grade_adjusted,
            cast(null as float64) as y1_course_in_progress_grade_points,
            cast(null as float64) as y1_course_in_progress_grade_points_unweighted,

            cast(null as float64) as need_60,
            cast(null as float64) as need_70,
            cast(null as float64) as need_80,
            cast(null as float64) as need_90,

            cast(null as int64) as courses_gradescaleid,

        from {{ ref("stg_powerschool__storedgrades") }} as sg
        left join
            backfill_running_course as bfc
            on sg.studentid = bfc.studentid
            and sg.yearid = bfc.yearid
            and sg.course_number = bfc.course_number
            and sg.storecode = bfc.storecode
        where
            sg.storecode in ('Q1', 'Q2', 'Q3', 'Q4', 'Y1')
            and sg.academic_year = {{ var("current_academic_year") - 1 }}
    ),

    grade_scale_rungs as (
        /* Whole-letter rungs only, no plus-minus, taken from each course's OWN
           scale — so the cutoffs genuinely differ. A D is 63 on KIPP NJ 2019
           but 60 on KIPP NJ 2016, which carries no D+/D-, and NCA 2011 has no
           A-. A hardcoded 60/70/80/90 ladder is wrong for roughly one Newark
           row in seven.

           Bands are recomputed here rather than reusing the lookup's own
           max_cutoffpercentage, which is unusable for this: that window
           partitions by scale id alone, so a scale carrying two items at one
           cutoff makes lead() repeat the value and collapses the band to
           max = min - 0.1 (119 of 976 rows). Restricting to whole letters
           leaves no duplicate cutoffs at all. */
        select
            gradescaleid,
            min_cutoffpercentage,

            row_number() over (
                partition by gradescaleid order by min_cutoffpercentage
            ) as rung_number,

            lead(letter_grade) over (
                partition by gradescaleid order by min_cutoffpercentage
            ) as need_next_letter_grade,

            lead(min_cutoffpercentage) over (
                partition by gradescaleid order by min_cutoffpercentage
            ) as need_next_cutoff_percent,

            lead(min_cutoffpercentage, 1, 1000) over (
                partition by gradescaleid order by min_cutoffpercentage
            )
            - 0.1 as rung_ceiling,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        where letter_grade in ('A', 'B', 'C', 'D', 'F')
    ),

    grade_scale_ladder as (
        /* the bottom rung floors at 0 so a percent below the F cutoff — the F*
           range on scales that split the two — still lands on a rung */
        select
            gradescaleid,
            need_next_letter_grade,
            need_next_cutoff_percent,
            rung_ceiling,

            if(rung_number = 1, 0, min_cutoffpercentage) as rung_floor,
        from grade_scale_rungs
    ),

    category_grades as (
        select
            yearid,
            schoolid,
            studentid,
            course_number,
            sectionid,
            storecode_type as category_name_code,
            storecode as category_quarter_code,
            percent_grade as category_quarter_percent_grade,
            percent_grade_y1_running as category_y1_percent_grade_running,

            concat('Q', storecode_order) as term,

            avg(if(is_current, percent_grade_y1_running, null)) over (
                partition by studentid, yearid, course_number, storecode_type
            ) as category_y1_percent_grade_current,

            round(
                avg(percent_grade) over (partition by yearid, studentid, storecode),
                2
            ) as category_quarter_average_all_courses,

        from {{ ref("int_powerschool__category_grades") }}
        where
            yearid >= {{ var("current_academic_year") - 1991 }}
            and not is_dropped_section
            and storecode_type not in ('Q')
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')
    ),

    category_ranked as (
        /* Ranking input for the lowest-category drivers. Rows where BOTH
           percents are null are excluded so a term that exists but carries no
           usable value cannot win rn_latest_term and blank out both drivers.

           (percent is null) asc leads each order by because BigQuery sorts
           NULLS FIRST ascending, which would otherwise hand "lowest" to a null.
           category_name_code is the final tiebreaker so the pick is
           reproducible across rebuilds. */
        select
            studentid,
            yearid,
            sectionid,
            category_name_code,
            category_quarter_percent_grade,
            category_y1_percent_grade_running,

            dense_rank() over (
                partition by studentid, yearid, sectionid order by term desc
            ) as rn_latest_term,

            row_number() over (
                partition by studentid, yearid, sectionid, term
                order by
                    (category_y1_percent_grade_running is null) asc,
                    category_y1_percent_grade_running asc,
                    category_name_code asc
            ) as rn_lowest_y1,

            row_number() over (
                partition by studentid, yearid, sectionid, term
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

    category_drivers as (
        /* One row per student-section-year, so the join below cannot fan out.
           Both drivers are read from the SAME latest term, so they describe one
           moment rather than two. */
        select
            studentid,
            yearid,
            sectionid,

            max(
                if(
                    rn_lowest_y1 = 1 and category_y1_percent_grade_running is not null,
                    category_name_code,
                    null
                )
            ) as lowest_category_y1_name,

            max(
                if(rn_lowest_y1 = 1, category_y1_percent_grade_running, null)
            ) as lowest_category_y1_percent,

            max(
                if(
                    rn_lowest_quarter = 1
                    and category_quarter_percent_grade is not null,
                    category_name_code,
                    null
                )
            ) as lowest_category_recent_term_name,

            max(
                if(rn_lowest_quarter = 1, category_quarter_percent_grade, null)
            ) as lowest_category_recent_term_percent,
        from category_ranked
        where rn_latest_term = 1
        group by studentid, yearid, sectionid
    ),

    course_priority as (
        /* No (x is null) asc guard, unlike category_ranked above — the
           filter removes nulls before the window runs, so an ungraded course
           takes no rank and the left join at the foot of the model is what
           nulls the column. */
        select
            studentid,
            yearid,
            `quarter`,
            course_number,

            row_number() over (
                partition by studentid, yearid, `quarter`
                order by quarter_course_percent_grade asc, course_number asc
            ) as office_hours_priority_rank,
        from quarter_grades
        where quarter_course_percent_grade is not null
    )

select
    ce.studentid,
    ce.yearid,
    ce.academic_year,
    ce.sectionid,
    ce.sections_dcid,
    ce.section_number,
    ce.external_expression,
    ce.date_enrolled,
    ce.credit_type,
    ce.course_number,
    ce.course_name,
    ce.exclude_from_gpa,
    ce.teacher_number,
    ce.teacher_name,

    ts.`quarter`,

    y1f.y1_course_final_percent_grade_adjusted,
    y1f.y1_course_final_letter_grade_adjusted,
    y1f.y1_course_final_earned_credits,
    y1f.y1_course_final_potential_credit_hours,
    y1f.y1_course_final_grade_points,

    qg.quarter_course_percent_grade,
    qg.quarter_course_letter_grade,
    qg.quarter_course_grade_points,
    qg.y1_course_in_progress_percent_grade_adjusted,
    qg.y1_course_in_progress_letter_grade_adjusted,
    qg.y1_course_in_progress_grade_points,
    qg.y1_course_in_progress_grade_points_unweighted,
    qg.need_60,
    qg.need_70,
    qg.need_80,
    qg.need_90,
    qg.courses_gradescaleid,

    c.category_name_code,
    c.category_quarter_code,
    c.category_quarter_percent_grade,
    c.category_y1_percent_grade_running,
    c.category_y1_percent_grade_current,
    c.category_quarter_average_all_courses,

    cd.lowest_category_y1_name,
    cd.lowest_category_y1_percent,
    cd.lowest_category_recent_term_name,
    cd.lowest_category_recent_term_percent,

    gsl.need_next_letter_grade,
    gsl.need_next_cutoff_percent,

    cp.office_hours_priority_rank,

    /* need_* is affine in the target percent — it is
       (points_still_needed * target - points_banked) / (term_points / 100), and
       the three non-target terms are row constants — so the need for ANY target
       is exactly recoverable from two of the four existing columns.
       Reduces to need_60 + (target - 60) / 10 * (need_70 - need_60); at target
       70 it returns need_70 identically, by construction.

       Like the four it is derived from, this is the percent required IN THE
       CURRENT TERM to land the YEAR-TO-DATE grade on the next rung — not what
       is needed for that letter this quarter. */
    qg.need_60
    + (gsl.need_next_cutoff_percent - 60) / 10 * (qg.need_70 - qg.need_60) as need_next,
from course_enrollments as ce
inner join
    term_spine as ts on ce.schoolid = ts.schoolid and ce.yearid = ts.yearid
left join
    y1_final_grades as y1f
    on ce.studentid = y1f.studentid
    and ce.yearid = y1f.yearid
    and ce.course_number = y1f.course_number
    and ts.`quarter` = y1f.storecode
left join
    quarter_grades as qg
    on ce.studentid = qg.studentid
    and ce.yearid = qg.yearid
    and ce.course_number = qg.course_number
    and ts.`quarter` = qg.`quarter`
left join
    category_grades as c
    on ce.studentid = c.studentid
    and ce.yearid = c.yearid
    and ce.sectionid = c.sectionid
    and ts.`quarter` = c.term
left join
    grade_scale_ladder as gsl
    on qg.courses_gradescaleid = gsl.gradescaleid
    and qg.y1_course_in_progress_percent_grade_adjusted
    between gsl.rung_floor and gsl.rung_ceiling
left join
    category_drivers as cd
    on ce.studentid = cd.studentid
    and ce.yearid = cd.yearid
    and ce.sectionid = cd.sectionid
left join
    course_priority as cp
    on ce.studentid = cp.studentid
    and ce.yearid = cp.yearid
    and ce.course_number = cp.course_number
    and ts.`quarter` = cp.`quarter`
```

Two things differ from the consumer on purpose. First, the spine: the consumer
gets its quarters from the kipptaf cross-SIS `int_students__terms` keyed on the
roster's school; the package fans each enrollment over `int_powerschool__terms`
keyed on the section's school. Both yield Q1 to Q4 plus Y1 for every NJ
school-year, and the kipptaf left join on `quarter` discards any package row the
roster spine lacks, so an extra package quarter is harmless and a missing one
would show as a diff in Task 4. Second, `teacher_number` and `teacher_name` are
aliased here rather than in kipptaf, so the consumer's select list keeps its
column names unchanged. The spec names them `teachernumber` and
`teacher_lastfirst`; this plan supersedes that detail.

- [ ] **Step 3: Write the properties yml**

Create
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__student_course_grades_spine.yml`:

```yaml
models:
  - name: int_powerschool__student_course_grades_spine
    description: >-
      One row per student, term, course, and gradebook category for the current
      and prior academic year, joining every PowerSchool-internal course-grade
      source in one place. Terms are Q1 to Q4 plus a Y1 year row; Y1 rows carry
      a null category. Current-year rows read the live gradebook through
      base_powerschool__final_grades; prior-year rows read stored grades, with a
      reconstructed running year-to-date percent that is exact at Q1 and Q4 and
      approximate at Q2 and Q3. Drives from course enrollments, so an enrollment
      with no grade posted survives with null grade columns. Filters out lunch,
      study hall, early dismissal, and advisory course numbers, and keeps one
      enrollment per student, course, and year.
    data_tests:
      # TODO(#3915): returns to error when the storedgrades double-write cleanup
      # completes. All duplicates are prior-year storedgrades rows; current-year
      # branches are structurally disjoint (base_powerschool__final_grades holds
      # only Q/E storecodes, so the explicit Y1 branch is the sole Y1 emitter,
      # and E rows never match the term spine).
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - studentid
              - yearid
              - quarter
              - course_number
              - category_name_code
    columns:
      - name: studentid
        data_type: int64
        description:
          The internal number and ID of the associated Students record.
      - name: yearid
        data_type: int64
        description: PowerSchool year id (academic year minus 1990).
      - name: academic_year
        data_type: int64
        description: Academic year, start-year convention (2025 = SY25-26).
      - name: sectionid
        data_type: int64
        description: PowerSchool section id of the course enrollment.
      - name: sections_dcid
        data_type: int64
        description: PowerSchool sections DCID.
      - name: section_number
        data_type: string
        description: Section number.
      - name: external_expression
        data_type: string
        description: Section period expression (HS scheduling).
      - name: date_enrolled
        data_type: date
        description: Course enrollment start date.
      - name: credit_type
        data_type: string
        description: Course credit type (subject area).
      - name: course_number
        data_type: string
        description: Course number.
      - name: course_name
        data_type: string
        description: Course name.
      - name: exclude_from_gpa
        data_type: int64
        description: Course excluded from GPA (1) or included (0).
      - name: teacher_number
        data_type: string
        description: Teacher number of the section's teacher.
        config:
          meta:
            contains_pii: true
      - name: teacher_name
        data_type: string
        description: Teacher name (last, first).
        config:
          meta:
            contains_pii: true
      - name: quarter
        data_type: string
        quote: true
        description: Reporting term (Q1-Q4) or Y1 for the year row.
      - name: y1_course_final_percent_grade_adjusted
        data_type: float64
        description: Final stored Y1 percent grade (Y1 rows only).
        config:
          meta:
            contains_pii: true
      - name: y1_course_final_letter_grade_adjusted
        data_type: string
        description: Final stored Y1 letter grade (Y1 rows only).
        config:
          meta:
            contains_pii: true
      - name: y1_course_final_earned_credits
        data_type: float64
        description: Credits earned for the course (Y1 rows only).
        config:
          meta:
            contains_pii: true
      - name: y1_course_final_potential_credit_hours
        data_type: float64
        description: Potential credit hours for the course (Y1 rows only).
      - name: y1_course_final_grade_points
        data_type: float64
        description: Final stored Y1 grade points (Y1 rows only).
        config:
          meta:
            contains_pii: true
      - name: quarter_course_percent_grade
        data_type: float64
        description: >-
          Course percent grade for the row's term. Y1 rows carry the in-progress
          (current year) or stored (prior year) Y1 percent.
        config:
          meta:
            contains_pii: true
      - name: quarter_course_letter_grade
        data_type: string
        description: Course letter grade for the row's term.
        config:
          meta:
            contains_pii: true
      - name: quarter_course_grade_points
        data_type: float64
        description: Course grade points for the row's term.
        config:
          meta:
            contains_pii: true
      - name: y1_course_in_progress_percent_grade_adjusted
        data_type: float64
        description: >-
          Year-to-date course percent as of the row's marking period. For the
          year in progress this is the real running value from the gradebook.
          For the prior year it is RECONSTRUCTED from stored quarter grades — Q1
          is exact, Q4 is anchored to the stored Y1 percent and is exact, Q2 and
          Q3 are approximations that agree with the year value to within half a
          point on 97.0 percent of courses. The reconstruction is temporary; see
          TODO(#4687) in the model.
        config:
          meta:
            contains_pii: true
      - name: y1_course_in_progress_letter_grade_adjusted
        data_type: string
        description: >-
          Year-to-date course letter as of the row's marking period. For the
          year in progress this comes from the gradebook. For the prior year it
          is RECONSTRUCTED by banding the reconstructed percent back through the
          course's own grade scale, so it inherits that percent's accuracy — Q1
          and Q4 exact, Q2 and Q3 approximate. Carries F and F* on the same
          prefix rule as quarter_course_letter_grade. Temporary; see TODO(#4687)
          in the model.
        config:
          meta:
            contains_pii: true
      - name: y1_course_in_progress_grade_points
        data_type: float64
        description: In-progress Y1 grade points (current-year rows only).
        config:
          meta:
            contains_pii: true
      - name: y1_course_in_progress_grade_points_unweighted
        data_type: float64
        description: >-
          In-progress unweighted Y1 grade points (current-year rows only).
        config:
          meta:
            contains_pii: true
      - name: need_60
        data_type: float64
        description: >-
          Percent needed on remaining work to reach a 60 course grade
          (current-year rows only).
      - name: need_70
        data_type: float64
        description: Percent needed to reach a 70 (current-year rows only).
      - name: need_80
        data_type: float64
        description: Percent needed to reach an 80 (current-year rows only).
      - name: need_90
        data_type: float64
        description: Percent needed to reach a 90 (current-year rows only).
      - name: courses_gradescaleid
        data_type: int64
        description: >-
          Grade scale id of the course, carried so the whole-letter ladder can
          be joined inside the model. Current-year rows only.
      - name: category_name_code
        data_type: string
        description: Gradebook category code (e.g. F/S/W; NULL on Y1 rows).
      - name: category_quarter_code
        data_type: string
        description: Category term code (e.g. Q1).
      - name: category_quarter_percent_grade
        data_type: float64
        description: Category percent grade for the term.
        config:
          meta:
            contains_pii: true
      - name: category_y1_percent_grade_running
        data_type: float64
        description: Running Y1 category percent grade through the term.
        config:
          meta:
            contains_pii: true
      - name: category_y1_percent_grade_current
        data_type: float64
        description: >-
          Y1 running category percent as of the current term (current-year rows
          only).
        config:
          meta:
            contains_pii: true
      - name: category_quarter_average_all_courses
        data_type: float64
        description: >-
          Student's average percent across all courses for the category-term.
        config:
          meta:
            contains_pii: true
      - name: lowest_category_y1_name
        data_type: string
        description: >-
          Gradebook category code with the lowest year-running percent for this
          course, read from the latest term that holds category data. Null when
          that term has no category with a non-null year-running percent.
          Present on every row including Y1.
      - name: lowest_category_y1_percent
        data_type: float64
        description: >-
          The year-running percent belonging to lowest_category_y1_name. Null
          exactly when that column is null.
        config:
          meta:
            contains_pii: true
      - name: lowest_category_recent_term_name
        data_type: string
        description: >-
          Gradebook category code with the lowest single-quarter percent in the
          most recent term holding any usable category percent for this course.
          Null when that term has no quarter-level percent.
      - name: lowest_category_recent_term_percent
        data_type: float64
        description: >-
          The single-quarter percent belonging to
          lowest_category_recent_term_name. Null exactly when that column is
          null.
        config:
          meta:
            contains_pii: true
      - name: need_next_letter_grade
        data_type: string
        description: >-
          The next WHOLE letter grade above where the student's in-progress Y1
          grade currently sits — one of A, B, C, D or F. Plus and minus rungs
          are excluded. NULL once the student is at the top whole letter, and
          NULL on courses whose grade scale has no letter ladder. Read from the
          course's OWN grade scale, so the same letter means different cutoffs
          across courses. Not a pass or fail signal.
      - name: need_next_cutoff_percent
        data_type: float64
        description: >-
          The percent cutoff for need_next_letter_grade on that course's grade
          scale. Varies by scale and will not generally match the 60/70/80/90
          targets behind need_60 through need_90.
      - name: office_hours_priority_rank
        data_type: int64
        description: >-
          Rank of this course among the student's courses for the same term, 1
          being the lowest percent grade. Null whenever
          quarter_course_percent_grade is null. Unique within the partition,
          ties broken by course_number.
      - name: need_next
        data_type: float64
        description: >-
          Percent required in the CURRENT term for the student's YEAR-TO-DATE
          course grade to reach need_next_cutoff_percent. Exact, derived from
          need_60 and need_70, which are linear in their target. Can be negative
          or exceed 100. NULL when need_60 is null (every prior-year row) or
          when there is no next rung.
```

- [ ] **Step 4: Compile the package model against prod in Newark**

Run from the main cwd:

```bash
cd /workspaces/teamster && uv run dbt compile --select int_powerschool__student_course_grades_spine --target prod --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package/src/dbt/kippnewark
```

Expected: `Done.` with 1 model compiled, no errors. Compiled SQL lands at
`<worktree>/src/dbt/kippnewark/target/compiled/powerschool/models/sis/intermediate/int_powerschool__student_course_grades_spine.sql`.
If dbt reports a missing package, run
`uv run dbt deps --project-dir <that project-dir>` once and compile again.

- [ ] **Step 5: Run the compiled SQL against prod as a row-count and grain
      check**

Read the compiled file with the Read tool, wrap it as a CTE, and run via the
BigQuery MCP:

```sql
with pkg as (
  -- paste the compiled SQL here, verbatim
)
select
  count(*) as n_rows,
  count(distinct format('%T|%T|%T|%T|%T', studentid, yearid, `quarter`, course_number, category_name_code)) as n_keys,
  countif(academic_year = 2025) as n_prior_year,
  countif(academic_year = 2026) as n_current_year
from pkg
```

Expected: `n_rows` in the low millions for Newark; `n_rows - n_keys` is the
duplicate count and must equal the consumer's own duplicate count for Newark,
measured in Task 4 step 3. Record `n_rows` and the job's slot time from
`INFORMATION_SCHEMA.JOBS_BY_PROJECT` for the PR body.

- [ ] **Step 6: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/powerschool/models/sis/intermediate/int_powerschool__student_course_grades_spine.sql src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__student_course_grades_spine.yml </dev/null
```

Expected: `No issues`. If sqlfluff ST06 flags the final select, the `ts.quarter`
plain ref sits between two table groups and is correct; check the flagged line
before changing order.

- [ ] **Step 7: Commit**

Write `.claude/scratch/commit-msg.txt`:

```text
feat(powerschool): add int_powerschool__student_course_grades_spine

One row per student, term, course, and gradebook category for the
current and prior year, joining course enrollments, live and stored
grades, category grades and drivers, the whole-letter ladder, and the
office-hours rank inside the package. Moved verbatim from
rpt_tableau__student_course_grades minus the cross-region plumbing.

Refs #5285

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package && git -C "$wt" add src/dbt/powerschool/models/sis/intermediate/int_powerschool__student_course_grades_spine.sql src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__student_course_grades_spine.yml && git -C "$wt" commit -q -F /workspaces/teamster/.claude/scratch/commit-msg.txt && git -C "$wt" log -1 --format='%h %s'
```

---

### Task 2: Source entries and the kipptaf wrapper

**Files:**

- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml` (after the
  `int_powerschool__gradebook_assignments_scores` entry, near line 817)
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml` (after the
  same entry, near line 817)
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml` (after
  the same entry, near line 799)
- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__student_course_grades_spine.sql`
- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__student_course_grades_spine.yml`

**Interfaces:**

- Consumes: the Task 1 relation, by name, in each of 3 district datasets.
- Produces: kipptaf model `int_powerschool__student_course_grades_spine` with
  every Task 1 column plus `_dbt_source_relation` and `_dbt_source_project`.
  Task 3 joins on `studentid`, `yearid`, `quarter`, `_dbt_source_project`.

- [ ] **Step 1: Add the source entry to each NJ source file**

In each of the 3 files, directly after the
`int_powerschool__gradebook_assignments_scores` table block, insert (replace
`<district>` with `kippnewark`, `kippcamden`, or `kipppaterson` to match the
file):

```yaml
- name: int_powerschool__student_course_grades_spine
  config:
    meta:
      dagster:
        group: powerschool
        asset_key:
          - <district>
          - powerschool
          - int_powerschool__student_course_grades_spine
```

The `schema:` at the top of each file already carries the `dev` and `staging`
branches, so no schema edit is needed.

- [ ] **Step 2: Write the wrapper SQL**

Create
`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__student_course_grades_spine.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kipppaterson_powerschool", model.name),
                ]
            )
        }}
    )

select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,

from union_relations as ur
```

- [ ] **Step 3: Write the wrapper properties yml**

Create
`src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__student_course_grades_spine.yml`:

```yaml
models:
  - name: int_powerschool__student_course_grades_spine
    description: >-
      Union of the per-region PowerSchool student course grade models. One row
      per student, term, course, and gradebook category for the current and
      prior academic year.


      NJ-only by design: this unions the district PowerSchool packages, and
      Miami's gradebook is in Focus, not PowerSchool. Ratified on #4996.


      Every column except _dbt_source_relation and _dbt_source_project comes
      through unchanged from the package model of the same name, which is where
      the authoritative column descriptions live.
    config:
      meta:
        contains_pii: true
    data_tests:
      # TODO(#3915): returns to error when the storedgrades double-write cleanup
      # completes. All duplicates are prior-year storedgrades rows.
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - _dbt_source_project
              - studentid
              - yearid
              - quarter
              - course_number
              - category_name_code
    columns:
      - name: _dbt_source_relation
        data_type: string
        description: Source relation identifier from dbt_utils.union_relations.
      - name: _dbt_source_project
        data_type: string
        description: District code location derived from _dbt_source_relation.
      - name: quarter
        data_type: string
        quote: true
        description: Reporting term (Q1-Q4) or Y1 for the year row.
```

- [ ] **Step 4: Parse kipptaf to prove the source and wrapper resolve**

```bash
cd /workspaces/teamster && uv run dbt parse --no-partial-parse --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package/src/dbt/kipptaf 2>&1 | tail -5
```

Expected: no `Compilation Error`. A `dbt compile --target staging` of the
wrapper will expand to an empty column list until the `zz_stg_*` copies exist
(Task 5), so parse is the check here, not compile.

- [ ] **Step 5: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__student_course_grades_spine.sql src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__student_course_grades_spine.yml </dev/null
```

Expected: `No issues`.

- [ ] **Step 6: Commit**

Write `.claude/scratch/commit-msg.txt`:

```text
feat(kipptaf): union wrapper for int_powerschool__student_course_grades_spine

Bare union_relations over the 3 NJ PowerSchool packages plus the 3
source entries. PII tag re-declared at model level since it does not
travel through source().

Refs #5285

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package && git -C "$wt" add -u && git -C "$wt" add src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__student_course_grades_spine.sql src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__student_course_grades_spine.yml && git -C "$wt" commit -q -F /workspaces/teamster/.claude/scratch/commit-msg.txt && git -C "$wt" log -1 --format='%h %s'
```

---

### Task 3: The consumer rewrite

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`

**Interfaces:**

- Consumes: the Task 2 wrapper columns, as `g.<column>`.
- Produces: the same contract as today.
  `properties/rpt_tableau__student_course_grades.yml` is not modified.

- [ ] **Step 1: Delete the moved CTEs**

Read the file. Delete every CTE from `course_enrollments as (` (line 369 on
`main`) through the closing of `course_priority` (line 883, the `)` before the
final `select`). Fourteen CTEs go: `course_enrollments`, `y1_final_grades`,
`backfill_quarter_running`, `backfill_y1_stored_raw`, `backfill_y1_stored`,
`backfill_course_anchored`, `backfill_running_course`, `quarter_grades`,
`grade_scale_rungs`, `grade_scale_ladder`, `category_grades`, `category_ranked`,
`category_drivers`, `course_priority`. The `student_roster` CTE that precedes
them now ends the `with` block, so its closing `)` must not be followed by a
comma.

- [ ] **Step 2: Rewrite the final select's `from` block**

Replace everything from the current `from student_roster as s` (line 1076 on
`main`) to the end of the file with:

```sql
from student_roster as s
left join
    {{ ref("int_powerschool__student_course_grades_spine") }} as g
    on s.studentid = g.studentid
    and s.yearid = g.yearid
    and s.`quarter` = g.`quarter`
    and s._dbt_source_project = g._dbt_source_project
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as f
    on g.studentid = f.studentid
    and g.academic_year = f.academic_year
    and g.credit_type = f.powerschool_credittype
    and g._dbt_source_project = f._dbt_source_project
    and f.rn_year = 1
left join
    {{ ref("int_people__staff_roster") }} as r
    on g.teacher_number = r.powerschool_teacher_number
where s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
```

- [ ] **Step 3: Re-point the select list aliases**

In the final select list (lines 885 to 1074 on `main`), change the alias
prefixes and nothing else. Every `ce.`, `y1f.`, `qg.`, `c.`, `cd.`, `gsl.`, and
`cp.` reference becomes `g.`. The 3 columns that came from the enrichment joins
keep their aliases: `ce.tutoring_nj` becomes `f.is_tutoring as tutoring_nj`,
`ce.nj_student_tier` becomes `f.nj_student_tier`, `ce.teacher_tableau_username`
becomes `r.sam_account_name as teacher_tableau_username`, `ce.manager` becomes
`r.reports_to_formatted_name as manager`, and `ce.report_to_sam_account_name`
becomes `r.reports_to_sam_account_name as report_to_sam_account_name`. The
`need_next` expression, which used `qg.need_60`, `gsl.need_next_cutoff_percent`,
and `qg.need_70`, becomes a plain `g.need_next`; delete its 11-line comment
block, which now lives in the package model. The `s.` columns are untouched.

The resulting select list, from the `ce.` group onward:

```sql
    g.sectionid,
    g.sections_dcid,
    g.section_number,
    g.external_expression,
    g.date_enrolled,
    g.credit_type,
    g.course_number,
    g.course_name,
    g.exclude_from_gpa,
    g.teacher_number,
    g.teacher_name,

    r.sam_account_name as teacher_tableau_username,
    r.reports_to_formatted_name as manager,
    r.reports_to_sam_account_name as report_to_sam_account_name,

    f.is_tutoring as tutoring_nj,
    f.nj_student_tier,

    g.y1_course_final_percent_grade_adjusted,
    g.y1_course_final_letter_grade_adjusted,
    g.y1_course_final_earned_credits,
    g.y1_course_final_potential_credit_hours,
    g.y1_course_final_grade_points,

    g.quarter_course_percent_grade,
    g.quarter_course_letter_grade,
    g.quarter_course_grade_points,
    g.y1_course_in_progress_percent_grade_adjusted,
    g.y1_course_in_progress_letter_grade_adjusted,
    g.y1_course_in_progress_grade_points,
    g.y1_course_in_progress_grade_points_unweighted,
    g.need_60,
    g.need_70,
    g.need_80,
    g.need_90,

    g.category_name_code,
    g.category_quarter_code,
    g.category_quarter_percent_grade,
    g.category_y1_percent_grade_running,
    g.category_y1_percent_grade_current,
    g.category_quarter_average_all_courses,

    g.lowest_category_y1_name,
    g.lowest_category_y1_percent,
    g.lowest_category_recent_term_name,
    g.lowest_category_recent_term_percent,

    g.need_next_letter_grade,
    g.need_next_cutoff_percent,

    g.office_hours_priority_rank,
    g.need_next,

    /* signed, so negative means the projection sits below last year's actual.
       Both inputs are student-grain, so these repeat across every quarter row
       and the Y1 row for a student, which is what makes them filterable at any
       marking period. */
    s.cumulative_y1_gpa_projected_unweighted
    - s.cumulative_y1_gpa_unweighted_prior_year
    as cumulative_y1_gpa_unweighted_change_from_prior_year,

    s.gpa_band_projected_unweighted
    - s.gpa_band_unweighted_prior_year as gpa_band_change_from_prior_year,

    coalesce(
        g.y1_course_final_letter_grade_adjusted,
        g.y1_course_in_progress_letter_grade_adjusted
    ) as y1_course_letter_grade_adjusted,

    if(
        s.grade_level < 9, g.section_number, g.external_expression
    ) as section_or_period,

    /* NULL rather than false when either side is missing — an unbanded student
       is unknown, not known-to-be-holding-steady */
    s.gpa_band_projected_unweighted
    <= s.gpa_band_unweighted_prior_year - 1 as is_gpa_band_slide,

    /* prefix match, not = 'F', because the failing domain is F and F*. F* is
       not a PowerSchool grade — stg_powerschool__pgfinalgrades manufactures it
       alongside the 50% floor (if percent < 0.5 then 'F*'), so an exact-equality
       test silently drops every floored failure, roughly a third of them. This
       matches the canonical rule the warehouse already uses for n_failing_y1.

       NULL, not false, on an ungraded enrolment — no grade posted is unknown,
       not known-to-be-passing. Consumers computing a failure rate should divide
       by the count of non-null quarter_course_letter_grade, not by all rows.

       The Y1 row carries the Y1 letter grade in this same column, so one flag
       covers Q1-Q4 and Y1 with no marking-period branching. */
    g.quarter_course_letter_grade like 'F%' as is_quarter_course_failing,
```

The `ce.` group in the original select list sat in join order after the `s.`
group and before `y1f.`; because `f` and `r` are now joined after `g`, their
columns move to their own groups after the `g.` enrollment columns. sqlfluff
ST06 requires plain refs grouped by table in join order, so this reorder within
the select is required. The output column set is unchanged; the contract matches
by name.

- [ ] **Step 4: Compile the consumer against prod**

```bash
cd /workspaces/teamster && uv run dbt compile --select rpt_tableau__student_course_grades --target prod --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package/src/dbt/kipptaf 2>&1 | tail -5
```

Expected: `Done.` with no errors. The compiled SQL references
`kipptaf_powerschool.int_powerschool__student_course_grades_spine`, which does
not exist in prod yet; compile does not execute, so that is fine. It is used in
Task 4.

- [ ] **Step 5: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql </dev/null
```

Expected: `No issues`.

- [ ] **Step 6: Commit**

Write `.claude/scratch/commit-msg.txt`:

```text
refactor(kipptaf): read course grades from the package wrapper

rpt_tableau__student_course_grades keeps its student-grain roster CTEs
and left-joins int_powerschool__student_course_grades_spine once, then the
subjects and staff-roster enrichment. Fourteen course-grain CTEs deleted;
they live in the powerschool package now. Contract unchanged.

Refs #5285

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package && git -C "$wt" add -u && git -C "$wt" commit -q -F /workspaces/teamster/.claude/scratch/commit-msg.txt && git -C "$wt" log -1 --format='%h %s'
```

---

### Task 4: Verification against production

**Files:**

- Read:
  `<worktree>/src/dbt/kipp{newark,camden,paterson}/target/compiled/powerschool/models/sis/intermediate/int_powerschool__student_course_grades_spine.sql`
  (Task 1 step 4 produced Newark; compile Camden and Paterson the same way)
- Read:
  `<worktree>/src/dbt/kipptaf/target/compiled/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`
- Write: `.claude/scratch/verify-scg.sql` (scratch, not committed)

**Interfaces:**

- Consumes: the 3 compiled package SQLs and the compiled consumer SQL.
- Produces: the numbers for the PR body in Task 5.

- [ ] **Step 1: Compile the package model for Camden and Paterson**

```bash
cd /workspaces/teamster && for d in kippcamden kipppaterson; do uv run dbt compile --select int_powerschool__student_course_grades_spine --target prod --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package/src/dbt/$d 2>&1 | tail -2; done
```

Expected: `Done.` twice.

- [ ] **Step 2: Assemble the comparison SQL**

Write `.claude/scratch/verify-scg.sql` with this shape. The 3 `pkg_*` CTEs are
the compiled package SQLs pasted verbatim. `new_consumer` is the compiled
consumer SQL with its one reference to
`` `teamster-332318`.`kipptaf_powerschool`.`int_powerschool__student_course_grades_spine` ``
replaced by `wrapper`.

```sql
with
pkg_kippnewark as (
  -- compiled Newark package SQL
),
pkg_kippcamden as (
  -- compiled Camden package SQL
),
pkg_kipppaterson as (
  -- compiled Paterson package SQL
),
wrapper as (
  select *, '`teamster-332318`.`kippnewark_powerschool`.`int_powerschool__student_course_grades_spine`' as _dbt_source_relation, 'kippnewark' as _dbt_source_project from pkg_kippnewark
  union all
  select *, '`teamster-332318`.`kippcamden_powerschool`.`int_powerschool__student_course_grades_spine`', 'kippcamden' from pkg_kippcamden
  union all
  select *, '`teamster-332318`.`kipppaterson_powerschool`.`int_powerschool__student_course_grades_spine`', 'kipppaterson' from pkg_kipppaterson
),
new_consumer as (
  -- compiled consumer SQL, with the wrapper relation replaced by `wrapper`
),
prod as (
  select * from `teamster-332318`.`kipptaf_tableau`.`rpt_tableau__student_course_grades`
),
new_only as (select * from new_consumer except distinct select * from prod),
prod_only as (select * from prod except distinct select * from new_consumer)
select
  'new' as side, _dbt_source_project, academic_year, count(*) as n
from new_only group by 1, 2, 3
union all
select
  'prod', _dbt_source_project, academic_year, count(*)
from prod_only group by 1, 2, 3
order by 1, 2, 3
```

Run it via the BigQuery MCP. If the query exceeds BigQuery's complexity limit,
split it: run one district at a time by filtering `prod` and `new_consumer` on
`_dbt_source_project` and using only that district's `pkg_*` CTE.

Expected: either 0 rows, or symmetric `new` and `prod` counts confined to
`academic_year = 2025` with `is_stored`-style tie-break as the cause (step 4).

- [ ] **Step 3: Row counts and duplicate counts per district**

Against the same CTEs:

```sql
select
  _dbt_source_project,
  count(*) as n_rows,
  count(*) - count(distinct format('%T|%T|%T|%T|%T|%T', _dbt_source_relation, studentid, academic_year, `quarter`, course_number, category_name_code)) as n_dups
from new_consumer
group by 1
union all
select
  concat('prod_', _dbt_source_project),
  count(*),
  count(*) - count(distinct format('%T|%T|%T|%T|%T|%T', _dbt_source_relation, studentid, academic_year, `quarter`, course_number, category_name_code))
from prod
group by 1
order by 1
```

Expected: `n_rows` and `n_dups` equal per district between `new_consumer` and
`prod`.

- [ ] **Step 4: Prove any residual diff is the #3915 tie-break**

If step 2 returned rows, run:

```sql
with diff_keys as (
  select distinct student_number, academic_year, course_number from new_only
  union distinct
  select distinct student_number, academic_year, course_number from prod_only
),
stored as (
  select s.student_number, sg.academic_year, sg.course_number, sg.storecode,
    count(*) as n_rows,
    count(distinct format('%T|%T|%T', sg.`percent`, sg.grade, sg.gpa_points)) as n_values
  from `teamster-332318`.`kipptaf_powerschool`.`stg_powerschool__storedgrades` as sg
  inner join `teamster-332318`.`kipptaf_powerschool`.`stg_powerschool__students` as s
    on sg.studentid = s.id and sg._dbt_source_project = s._dbt_source_project
  group by 1, 2, 3, 4
)
select
  count(*) as n_diff_keys,
  countif(exists (
    select 1 from stored st
    where st.student_number = d.student_number
      and st.academic_year = d.academic_year
      and st.course_number = d.course_number
      and st.n_rows > 1 and st.n_values > 1
  )) as n_explained_by_tie
from diff_keys as d
```

Expected: `n_diff_keys = n_explained_by_tie`. Any unexplained key is a real
regression; stop and diagnose before Task 5.

- [ ] **Step 5: Named checks from the spec**

`section_or_period` and the enrichment columns, on rows with no grade:

```sql
select
  countif(n.section_or_period is distinct from p.section_or_period) as n_section_or_period_diff,
  countif(n.quarter_course_percent_grade is null and (
    n.tutoring_nj is distinct from p.tutoring_nj
    or n.nj_student_tier is distinct from p.nj_student_tier
    or n.manager is distinct from p.manager
    or n.teacher_tableau_username is distinct from p.teacher_tableau_username
  )) as n_enrichment_diff_on_ungraded
from new_consumer as n
inner join prod as p
  on n._dbt_source_relation = p._dbt_source_relation
  and n.studentid = p.studentid
  and n.academic_year = p.academic_year
  and n.`quarter` = p.`quarter`
  and n.course_number = p.course_number
  and n.category_name_code is not distinct from p.category_name_code
```

Expected: both 0.

- [ ] **Step 6: Record slot time**

```sql
select destination_table.table_id, total_slot_ms / 1000 / 3600 as slot_hours, total_bytes_billed / pow(1024, 3) as gib_billed
from `teamster-332318`.`region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
where creation_time >= timestamp_sub(current_timestamp(), interval 2 hour)
  and regexp_contains(query, 'pkg_kippnewark')
order by creation_time desc
limit 5
```

Record the largest `slot_hours` and `gib_billed` for the PR body.

No commit for this task; the scratch SQL is not committed.

---

### Task 5: Seed CI, push, open the PR

**Files:**

- Write: `.claude/scratch/pr-body.md`
- Read: `.github/pull_request_template.md`

**Interfaces:**

- Consumes: the Task 4 numbers.
- Produces: the PR.

- [ ] **Step 1: Ask the user to authorize the 3 staging seeds**

Say, in plain text: "The next 3 commands each write a shared
`zz_stg_<district>_powerschool.int_powerschool__student_course_grades_spine`
table that CI reads. Authorize each?" Wait for a yes before each.

- [ ] **Step 2: Seed Newark**

After the user's yes, restate in plain text that they authorized the Newark
staging build, then run this alone in one Bash call:

```bash
cd /workspaces/teamster && uv run dbt build --select int_powerschool__student_course_grades_spine --target staging --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package/src/dbt/kippnewark
```

Expected: 1 model created, 1 test warn (the #3915 duplicates), 0 errors.

- [ ] **Step 3: Seed Camden**

Same as step 2 with `kippcamden`, after its own yes.

- [ ] **Step 4: Seed Paterson**

Same as step 2 with `kipppaterson`, after its own yes.

- [ ] **Step 5: Compile the wrapper against staging to prove the columns list**

```bash
cd /workspaces/teamster && uv run dbt compile --select int_powerschool__student_course_grades_spine --target staging --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package/src/dbt/kipptaf 2>&1 | tail -3 && grep -c "cast(" /workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package/src/dbt/kipptaf/target/compiled/kipptaf/models/powerschool/intermediate/int_powerschool__student_course_grades_spine.sql
```

Expected: `Done.` and a `cast(` count of 0. Any `cast(null as ...)` means a
district's `zz_stg` copy lacks a column the others have; rebuild that district.

- [ ] **Step 6: Push**

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-student-course-grades-package && git -C "$wt" push -q -u origin cbini/refactor/claude-student-course-grades-package && git -C "$wt" log -3 --format='%h %s'
```

- [ ] **Step 7: Write the PR body**

Read `.github/pull_request_template.md`. Write `.claude/scratch/pr-body.md`
following its sections. Summary: "When merged, this pull request will move every
PowerSchool-to-PowerSchool join behind `rpt_tableau__student_course_grades` into
a new `powerschool` package model,
`int_powerschool__student_course_grades_spine`, read through a kipptaf union
wrapper. Closes row 1 of #5285; row 2 shipped in #5306." Reviewer Notes: the
term spine change (section school, not roster school), the `teacher_number` and
`teacher_name` alias placement, the `section_or_period` decision, and the Task 4
numbers. For Claude fold-out: the spec path, the verification tables, the slot
time, and the 3 seeded staging tables. End with
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`. No PII values
anywhere in the body.

- [ ] **Step 8: Open the PR**

Use `mcp__github__create_pull_request` with `owner: TEAMSchools`,
`repo: teamster`, `head: cbini/refactor/claude-student-course-grades-package`,
`base: main`, title
`refactor(dbt): move the student course grade joins into the powerschool package`,
and the body from step 7. Then confirm the stored title and first body line
with:

```bash
gh api repos/TEAMSchools/teamster/pulls/<n> --jq '.title, (.body | split("\n") | .[0])'
```

- [ ] **Step 9: Watch CI and process review**

Arm a Monitor on `gh pr checks <n> --json name,bucket,state`, 30-minute timeout,
emitting each non-pending check once and exiting when all settle. When
`claude-review` posts, invoke `superpowers:receiving-code-review`, verify each
finding against the checkout, and post a per-finding verdict comment.

---

## Self-review

**Spec coverage.** Package model at the consumer's grain, 2 years, all 14 CTEs
moved: Task 1. `section_or_period` stays in kipptaf and the package exports
`section_number` and `external_expression`: Task 1 step 2 and Task 3 step 3.
Wrapper, PII tag, 6-column test, 3 source entries: Task 2. Consumer reduced to
roster plus wrapper plus 2 enrichment joins, contract unchanged: Task 3.
Verification against prod with `except distinct`, tie-break proof, the 2 named
checks, slot time: Task 4. Staging seeds with per-call authorization, one PR, no
Miami: Task 5. Documentation: the package yml carries every column description;
the consumer yml is untouched.

**Placeholder scan.** None. Every code step carries the full text.

**Type consistency.** `quarter` is backticked in every SQL and `quote: true` in
both ymls. `teacher_number` and `teacher_name` are aliased in the package select
and read as `g.teacher_number` and `g.teacher_name` in Task 3. `academic_year`
is projected from `cc_academic_year` in Task 1 and joined as `g.academic_year`
in Task 3. `_dbt_source_project` is produced by the Task 2 wrapper and consumed
by the Task 3 join.
