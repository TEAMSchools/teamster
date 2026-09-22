with
    powerschool_conformed as (
        select
            g._dbt_source_relation,
            g._dbt_source_project,
            g.studentid,
            g.schoolid,
            g.yearid,
            g.academic_year,
            g.term_name,
            g.semester,
            g.gpa_term,
            g.gpa_y1,
            g.gpa_y1_unweighted,
            g.gpa_semester,
            g.n_failing_y1,
            g.total_credit_hours_term,
            g.total_credit_hours_y1,
            g.grade_avg_term,
            g.grade_avg_y1,
            g.students_student_number as student_number,

            -- int_powerschool__gpa carries only five of these ten measures, so
            -- all ten come from one relation.
            gc.cumulative_y1_gpa,
            gc.cumulative_y1_gpa_unweighted,
            gc.cumulative_y1_gpa_projected,
            gc.earned_credits_cum,
            gc.potential_credits_cum,
            gc.cumulative_y1_gpa_projected_unweighted,
            gc.cumulative_y1_gpa_projected_s1,
            gc.cumulative_y1_gpa_projected_s1_unweighted,
            gc.core_cumulative_y1_gpa,
            gc.earned_credits_cum_projected,

            -- The PowerSchool GPA chain does not produce class rank at all.
            cast(null as int64) as class_rank,
        from {{ ref("int_powerschool__gpa") }} as g
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on g.studentid = gc.studentid
            and g.schoolid = gc.schoolid
            and g._dbt_source_project = gc._dbt_source_project
    ),

    focus_conformed as (
        select
            g._dbt_source_relation,
            g._dbt_source_project,

            g.syear as academic_year,

            g.class_rank,

            st.student_number,
            loc.powerschool_school_id as schoolid,

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

            -- Focus projects neither a year-end GPA nor potential credits, and
            -- computes no core-course GPA.
            cast(null as float64) as cumulative_y1_gpa_projected,
            cast(null as float64) as potential_credits_cum,
            cast(null as float64) as cumulative_y1_gpa_projected_unweighted,
            cast(null as float64) as cumulative_y1_gpa_projected_s1,
            cast(null as float64) as cumulative_y1_gpa_projected_s1_unweighted,
            cast(null as float64) as core_cumulative_y1_gpa,
            cast(null as float64) as earned_credits_cum_projected,

            -- Derived so the reporting-terms join in fct_grades_gpa keeps
            -- working for both branches, even though no Focus row resolves a
            -- term.
            g.syear - 1990 as yearid,

        from {{ ref("stg_focus__student_gpa_calculated") }} as g
        inner join
            {{ ref("int_focus__students") }} as st on g.student_id = st.student_id
        inner join {{ ref("int_focus__schools") }} as fs on g.school_id = fs.id
        left join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on fs.school_number = loc.focus_school_id
        -- The archive branch above owns Miami's years before the cutover, so
        -- admit only rows at or after it — the same boundary, applied from the
        -- other side. A floor rather than a set of Focus years: a Focus year
        -- that recorded nothing must not fall back to an archive holding
        -- nothing for it either.
        where g.syear >= 2026
    ),

    unioned as (
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
            cumulative_y1_gpa_projected_unweighted,
            cumulative_y1_gpa_projected_s1,
            cumulative_y1_gpa_projected_s1_unweighted,
            core_cumulative_y1_gpa,
            earned_credits_cum,
            earned_credits_cum_projected,
            potential_credits_cum,
            student_number,
            class_rank,
        from powerschool_conformed

        union all

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
            cumulative_y1_gpa_projected_unweighted,
            cumulative_y1_gpa_projected_s1,
            cumulative_y1_gpa_projected_s1_unweighted,
            core_cumulative_y1_gpa,
            earned_credits_cum,
            earned_credits_cum_projected,
            potential_credits_cum,
            student_number,
            class_rank,
        from focus_conformed
    )

select
    *,

    case
        when cumulative_y1_gpa_unweighted >= 3.00
        then 4
        when cumulative_y1_gpa_unweighted >= 2.50
        then 3
        when cumulative_y1_gpa_unweighted >= 2.00
        then 2
        when cumulative_y1_gpa_unweighted < 2.00
        then 1
    end as cumulative_y1_gpa_unweighted_band,

    case
        when cumulative_y1_gpa_projected_unweighted >= 3.00
        then 4
        when cumulative_y1_gpa_projected_unweighted >= 2.50
        then 3
        when cumulative_y1_gpa_projected_unweighted >= 2.00
        then 2
        when cumulative_y1_gpa_projected_unweighted < 2.00
        then 1
    end as cumulative_y1_gpa_projected_unweighted_band,
from unioned
