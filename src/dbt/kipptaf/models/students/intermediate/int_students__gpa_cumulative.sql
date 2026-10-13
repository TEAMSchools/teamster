with
    focus_conformed as (
        select
            g._dbt_source_relation,
            g._dbt_source_project,

            g.syear as calculated_academic_year,

            g.class_rank,

            st.student_number,
            loc.powerschool_school_id as schoolid,

            cast(null as int64) as studentid,

            -- PowerSchool's cumulative_y1_gpa is the weighted measure and
            -- cumulative_y1_gpa_unweighted the unweighted one, so the two Focus
            -- columns map across that way round rather than by name.
            cast(g.cumulative_weighted_gpa as float64) as cumulative_y1_gpa,
            cast(g.cumulative_gpa as float64) as cumulative_y1_gpa_unweighted,
            cast(g.cumulative_credits as float64) as earned_credits_cum,

            -- Focus projects neither a year-end GPA nor potential credits, and
            -- computes no core-course GPA.
            cast(null as float64) as cumulative_y1_gpa_projected,
            cast(null as float64) as cumulative_y1_gpa_projected_unweighted,
            cast(null as float64) as cumulative_y1_gpa_projected_s1,
            cast(null as float64) as cumulative_y1_gpa_projected_s1_unweighted,
            cast(null as float64) as core_cumulative_y1_gpa,
            cast(null as float64) as earned_credits_cum_projected,
            cast(null as float64) as potential_credits_cum,
        from {{ ref("stg_focus__student_gpa_calculated") }} as g
        inner join
            {{ ref("int_focus__students") }} as st on g.student_id = st.student_id
        inner join {{ ref("int_focus__schools") }} as fs on g.school_id = fs.id
        left join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on fs.school_number = loc.focus_school_id
        where g.syear >= 2026
    ),

    powerschool_conformed as (
        select
            gc._dbt_source_relation,
            gc._dbt_source_project,
            gc.studentid,
            gc.schoolid,
            gc.cumulative_y1_gpa,
            gc.cumulative_y1_gpa_unweighted,
            gc.cumulative_y1_gpa_projected,
            gc.cumulative_y1_gpa_projected_unweighted,
            gc.cumulative_y1_gpa_projected_s1,
            gc.cumulative_y1_gpa_projected_s1_unweighted,
            gc.core_cumulative_y1_gpa,
            gc.earned_credits_cum,
            gc.earned_credits_cum_projected,
            gc.potential_credits_cum,
            gc.students_student_number as student_number,

            -- The PowerSchool GPA chain does not produce class rank at all.
            cast(null as int64) as class_rank,
            -- PowerSchool stores only the current value per student and school.
            cast(null as int64) as calculated_academic_year,
        from {{ ref("int_powerschool__gpa_cumulative") }} as gc
        -- Focus wins where a Miami student has both at the same school.
        left join
            focus_conformed as fc
            on gc.students_student_number = fc.student_number
            and gc.schoolid = fc.schoolid
            and gc._dbt_source_project = fc._dbt_source_project
        where fc.student_number is null
    ),

    unioned as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            studentid,
            schoolid,
            student_number,
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
            class_rank,
            calculated_academic_year,
        from powerschool_conformed

        union all

        select
            _dbt_source_relation,
            _dbt_source_project,
            studentid,
            schoolid,
            student_number,
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
            class_rank,
            calculated_academic_year,
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
