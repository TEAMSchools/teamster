with
    course_enrollments as (
        select
            _dbt_source_project,
            cc_dcid,
            cc_studentid,
            cc_abs_sectionid,
            cc_yearid,
            cc_academic_year,
            cc_schoolid,
            sections_dcid,
            students_student_number,
            is_dropped_section,
            region,
        from {{ ref("int_students__course_enrollments") }}
    ),

    powerschool_conformed as (
        select
            cg._dbt_source_project,
            ce.cc_dcid,
            ce.region,
            cg.schoolid,
            cg.yearid,
            cg.academic_year,
            cg.storecode,
            cg.storecode_type,
            cg.storecode_order,
            cg.reporting_term,
            cg.quarter,
            cg.percent_grade,
            cg.citizenship_grade,
            cg.percent_grade_y1_running,
            cg.is_current,
        from {{ ref("int_powerschool__category_grades") }} as cg
        -- not is_dropped_section is the correction this model makes.
        -- fct_grades_category never filtered it, so it over-counts: when a
        -- student leaves a section PowerSchool writes a second cc row with a
        -- negated sectionid, cc_abs_sectionid is the absolute value, and this
        -- join therefore matches the dropped stint alongside the live one.
        -- With the filter Camden is exactly 1:1 -- 242,070 category rows in,
        -- 242,070 out. fct_grades_assignments has always filtered it; this
        -- brings the two facts into line. Do NOT substitute a dedupe.
        inner join
            course_enrollments as ce
            on cg.studentid = ce.cc_studentid
            and cg.sectionid = ce.cc_abs_sectionid
            and cg.yearid = ce.cc_yearid
            and cg._dbt_source_project = ce._dbt_source_project
            and not ce.is_dropped_section
    ),

    -- PowerSchool category storecodes are per-quarter, so a Focus score
    -- against a semester/year/progress-period marking period has no quarter
    -- storecode analog. mp.type = 'quarter' alone still carries short_names
    -- outside the Q<digits> shape (1NW/2NW/3NW/4NW, bare numbers, SS1), which
    -- an unanchored digit-suffix match would turn into a NULL storecode
    -- (colliding every such row together in the grain test) or a
    -- nonsense/duplicate order (PP11 -> '11', SS1 -> '1' colliding with
    -- Q1 -> '1'). Scoping to the anchored Q<digits> form here, once, keeps a
    -- non-quarter marking period out of the output entirely instead of
    -- producing a NULL or nonsense storecode.
    focus_quarter_marking_periods as (
        select
            marking_period_id,
            short_name,
            start_date,
            end_date,
            regexp_extract(short_name, r'^Q(\d+)$') as quarter_number,
        from {{ ref("stg_focus__marking_periods") }}
        where type = 'quarter'
    ),

    -- Focus posts no category grade of its own -- there is no
    -- student_gradebook_category_grades table -- so the category percent is
    -- computed from the scores that make it up.
    focus_conformed as (
        select
            asg._dbt_source_project,
            ce.cc_dcid,
            ce.region,
            ce.cc_schoolid as schoolid,

            asg.academic_year,

            -- PowerSchool's yearid is academic_year - 1990. Deriving it keeps
            -- fct_grades_category's reporting-terms join working on both
            -- branches, matching int_students__final_grades.
            asg.academic_year - 1990 as yearid,

            asg.category_code as storecode_type,

            mp.quarter_number as storecode_order,

            concat(asg.category_code, mp.quarter_number) as storecode,

            concat('RT', mp.quarter_number) as reporting_term,

            mp.short_name as `quarter`,

            -- Weighted by points possible, and scored rows only: a not-yet-
            -- graded score (the -1 sentinel, already nulled upstream) must not
            -- drag the average toward zero.
            round(
                safe_divide(
                    sum(asg.points_earned),
                    sum(if(asg.points_earned is not null, asg.totalpointvalue, null))
                )
                * 100,
                2
            ) as percent_grade,

            -- Focus has no citizenship grade and no year-to-date rollup.
            cast(null as string) as citizenship_grade,
            cast(null as float64) as percent_grade_y1_running,

            current_date('{{ var("local_timezone") }}')
            between mp.start_date and mp.end_date as is_current,

        from {{ ref("int_students__gradebook_assignments_scores") }} as asg
        inner join
            focus_quarter_marking_periods as mp
            on asg.marking_period_id = mp.marking_period_id
            and mp.quarter_number is not null
        inner join
            course_enrollments as ce
            on asg.student_number = ce.students_student_number
            and asg.sectionsdcid = ce.sections_dcid
            and asg.academic_year = ce.cc_academic_year
            and asg._dbt_source_project = ce._dbt_source_project
            and not ce.is_dropped_section
        -- marking_period_id is null on every PowerSchool row, so the join above
        -- already restricts this branch to Focus. Stated explicitly so the
        -- scope survives a future PowerSchool marking-period backfill.
        where asg._dbt_source_project = 'kippmiami'
        group by
            asg._dbt_source_project,
            ce.cc_dcid,
            ce.region,
            ce.cc_schoolid,
            asg.academic_year,
            asg.category_code,
            mp.quarter_number,
            mp.short_name,
            mp.start_date,
            mp.end_date
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
