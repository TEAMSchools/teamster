with
    powerschool_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            studentid,
            schoolid,
            yearid,
            academic_year,
            term_name,
            semester,
            gpa_term,
            gpa_y1,
            gpa_y1_unweighted,
            gpa_semester,
            n_failing_y1,
            total_credit_hours_term,
            total_credit_hours_y1,
            grade_avg_term,
            grade_avg_y1,
            cumulative_y1_gpa,
            cumulative_y1_gpa_unweighted,
            cumulative_y1_gpa_projected,
            earned_credits_cum,
            potential_credits_cum,
            students_student_number as student_number,

            -- The PowerSchool GPA chain does not produce class rank at all.
            cast(null as int64) as class_rank,
        from {{ ref("int_powerschool__gpa") }}
    ),

    focus_conformed as (
        select
            g._dbt_source_relation,
            g._dbt_source_project,

            g.syear as academic_year,

            g.class_rank,

            st.student_number,
            loc.powerschool_school_id as schoolid,

            -- Derived so the reporting-terms join in fct_grades_gpa keeps
            -- working for both branches, even though no Focus row resolves a
            -- term.
            g.syear - 1990 as yearid,

            cast(null as int64) as studentid,

            -- Focus's student_gpa_calculated is course-history GPA only: every
            -- row carries marking_period_id = -1 and there is no term-grained
            -- row in the table. So no term, semester or year-to-date measure has
            -- a Focus analog. Null rather than copied from the cumulative value:
            -- a term GPA that silently equals the cumulative one reads as a real
            -- term measure and is not one.
            cast(null as string) as term_name,
            cast(null as string) as semester,
            cast(null as float64) as gpa_term,
            cast(null as float64) as gpa_y1,
            cast(null as float64) as gpa_y1_unweighted,
            cast(null as float64) as gpa_semester,
            cast(null as int64) as n_failing_y1,
            cast(null as float64) as total_credit_hours_term,
            cast(null as float64) as total_credit_hours_y1,
            cast(null as float64) as grade_avg_term,
            cast(null as float64) as grade_avg_y1,

            -- PowerSchool's cumulative_y1_gpa is the weighted measure and
            -- cumulative_y1_gpa_unweighted the unweighted one, so the two Focus
            -- columns map across that way round rather than by name.
            cast(g.cumulative_weighted_gpa as float64) as cumulative_y1_gpa,
            cast(g.cumulative_gpa as float64) as cumulative_y1_gpa_unweighted,
            cast(g.cumulative_credits as float64) as earned_credits_cum,

            -- Focus projects neither a year-end GPA nor potential credits.
            cast(null as float64) as cumulative_y1_gpa_projected,
            cast(null as float64) as potential_credits_cum,

        from {{ ref("stg_focus__student_gpa_calculated") }} as g
        inner join
            {{ ref("int_focus__students") }} as st on g.student_id = st.student_id
        inner join {{ ref("int_focus__schools") }} as fs on g.school_id = fs.id
        left join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on fs.school_number = loc.focus_school_id
        -- The archive branch above owns Miami's years before the cutover, so
        -- admit only rows at or after it — the same boundary, applied from the
        -- other side. One row. See int_students__sis_cutover for why the
        -- boundary is a floor and why it is derived from recorded attendance
        -- rather than row presence.
        cross join {{ ref("int_students__sis_cutover") }} as sc
        where g.syear >= sc.focus_start_academic_year
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
