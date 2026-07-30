with
    latest_graded_year as (
        /* the most recent year with posted Y1 grades. Cumulative earned credits
           cannot serve as this signal — they include prior years, so a
           not-yet-started year's upperclassmen already carry credits. */
        select max(yearid) + 1990 as latest_graded_academic_year,
        from {{ ref("int_powerschool__gpa_term") }}
        where gpa_y1 is not null
    )

select
    gcy._dbt_source_relation,
    gcy._dbt_source_project,
    gcy.studentid,
    gcy.academic_year,
    gcy.schoolid,
    gcy.grade_level,
    gcy.is_projected,
    gcy.earned_credits_cum,
    gcy.potential_gpa_credits_cum,
    gcy.cumulative_y1_gpa,
    gcy.cumulative_y1_gpa_unweighted,

    e.student_number,
    e.student_name,
    e.academic_year_display,
    e.region,
    e.school_level_alt as school_level,
    e.school,
    e.enroll_status,
    e.cohort,
    e.graduation_year,
    e.gender,
    e.ethnicity,
    e.advisory,
    e.year_in_school,
    e.year_in_network,
    e.rn_undergrad,
    e.is_self_contained as is_pathways,
    e.is_retained_year,
    e.is_retained_ever,
    e.student_slideback,
    e.lunch_status,
    e.lep_status,
    e.gifted_and_talented,
    e.iep_status,
    e.is_504,
    e.salesforce_id,
    e.ktc_cohort,
    e.is_counseling_services,
    e.is_student_athlete,
    e.ada,
    e.ada_above_or_at_80,
    e.hos,
    e.school_leader,
    e.school_leader_tableau_username,

    gcc.cumulative_y1_gpa_unweighted as cumulative_y1_gpa_unweighted_as_of_today,
    gcc.gpa_needed_for_cumulative_3_0,
    gcc.is_cumulative_3_0_attainable,
    gcc.potential_gpa_credits_current_year,

    gcy.academic_year = lgy.latest_graded_academic_year as is_latest_graded_year,

    gcy.cumulative_y1_gpa_unweighted >= 2.75
    and gcy.cumulative_y1_gpa_unweighted < 3.00 as is_on_cusp_3_0,

    case
        when gcy.cumulative_y1_gpa_unweighted >= 3.50
        then '3.5+'
        when gcy.cumulative_y1_gpa_unweighted >= 3.00
        then '3.0-3.49'
        when gcy.cumulative_y1_gpa_unweighted >= 2.50
        then '2.5-2.99'
        when gcy.cumulative_y1_gpa_unweighted >= 2.00
        then '2.0-2.49'
        when gcy.cumulative_y1_gpa_unweighted < 2.00
        then 'below 2.0'
    end as gpa_band_label,

    case
        when gcc.cumulative_y1_gpa_unweighted >= 3.50
        then '3.5+'
        when gcc.cumulative_y1_gpa_unweighted >= 3.00
        then '3.0-3.49'
        when gcc.cumulative_y1_gpa_unweighted >= 2.50
        then '2.5-2.99'
        when gcc.cumulative_y1_gpa_unweighted >= 2.00
        then '2.0-2.49'
        when gcc.cumulative_y1_gpa_unweighted < 2.00
        then 'below 2.0'
    end as gpa_band_as_of_today_label,

from {{ ref("int_powerschool__gpa_cumulative_year") }} as gcy
/* the inner join on the year's rn_year = 1 enrollment (including schoolid)
   dedupes the union model's student x school x year grain to one row per
   student-year, keyed to the primary enrollment school */
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on gcy.studentid = e.studentid
    and gcy.academic_year = e.academic_year
    and gcy.schoolid = e.schoolid
    and gcy._dbt_source_project = e._dbt_source_project
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gcc
    on gcy.studentid = gcc.studentid
    and gcy.schoolid = gcc.schoolid
    and gcy._dbt_source_project = gcc._dbt_source_project
    /* int_powerschool__gpa_cumulative is current-state, with no academic year.
       Gating on is_projected attaches it to the current-year row only; without
       the gate today's values get stamped onto every prior year. */
    and gcy.is_projected
cross join latest_graded_year as lgy
where
    e.rn_year = 1
    and not e.is_out_of_district
    /* status guard drops pre-registered (-1, which can pass
       is_enrolled_recent) and invalid (1) rows */
    and e.enroll_status in (0, 2, 3)
    and e.is_enrolled_recent
    /* Miami hard-excluded: region unsupported in the rebuilt dashboard
       (#4340) */
    -- TODO(#4340): add Paterson once PS gradebook data is populated
    and e.region in ('Newark', 'Camden')
