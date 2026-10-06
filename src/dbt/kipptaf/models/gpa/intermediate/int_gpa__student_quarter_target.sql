with
    unweighted_scale as (
        select letter_grade, grade_points, min_cutoffpercentage,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        /* every scale in use shares these cutoffs; 2019 Unweighted is the
           reference, and the 83 floor is the B cutoff */
        where
            gradescale_name = 'KIPP NJ 2019 (5-12) Unweighted'
            and min_cutoffpercentage >= 83
    ),

    schedule as (
        select
            studentid,
            _dbt_source_project,

            sum(potential_credit_hours) as gpa_credits,
            sum(
                potential_credit_hours * case
                    courses_gradescaleid when 991 then 1.0 when 1075 then 0.5 else 0.0
                end
            ) as bump_points,
        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and exclude_from_gpa = 0
            and not is_dropped_section
            and potential_credit_hours > 0
        group by studentid, _dbt_source_project
    ),

    students as (
        select
            co.studentid,
            co.schoolid,
            co.student_number,
            co._dbt_source_project,

            gc.is_cumulative_3_0_attainable,
            gc.cumulative_y1_gpa_projected_unweighted,

            round(gc.gpa_needed_for_cumulative_3_0, 4) as gpa_needed_unweighted,
            safe_divide(s.bump_points, s.gpa_credits) as schedule_bump,
        from {{ ref("int_extracts__student_enrollments") }} as co
        inner join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on co.studentid = gc.studentid
            and co.schoolid = gc.schoolid
            and co._dbt_source_project = gc._dbt_source_project
        left join
            schedule as s
            on co.studentid = s.studentid
            and co._dbt_source_project = s._dbt_source_project
        where
            co.academic_year = {{ var("current_academic_year") }}
            and co.rn_year = 1
            and co.school_level = 'HS'
    ),

    targets as (
        select
            st.studentid,
            st.schoolid,
            st._dbt_source_project,

            min(us.min_cutoffpercentage) as target_cutoff_percent,
        from students as st
        inner join unweighted_scale as us on st.gpa_needed_unweighted <= us.grade_points
        group by st.studentid, st.schoolid, st._dbt_source_project
    ),

    with_target as (
        select
            st.studentid,
            st.schoolid,
            st.student_number,
            st._dbt_source_project,
            st.gpa_needed_unweighted,
            st.is_cumulative_3_0_attainable,
            st.cumulative_y1_gpa_projected_unweighted,

            t.target_cutoff_percent,

            us.letter_grade as target_letter_grade,
            us.grade_points as target_grade_points,

            coalesce(st.schedule_bump, 0.0) as schedule_bump,
        from students as st
        left join
            targets as t
            on st.studentid = t.studentid
            and st.schoolid = t.schoolid
            and st._dbt_source_project = t._dbt_source_project
        left join
            unweighted_scale as us on t.target_cutoff_percent = us.min_cutoffpercentage
    )

select
    studentid,
    schoolid,
    student_number,
    _dbt_source_project,
    gpa_needed_unweighted,
    target_cutoff_percent,
    target_letter_grade,
    target_grade_points,
    is_cumulative_3_0_attainable,
    cumulative_y1_gpa_projected_unweighted,

    round(schedule_bump, 4) as schedule_bump,
    round(gpa_needed_unweighted + schedule_bump, 2) as gpa_needed_weighted,

    case
        when gpa_needed_unweighted is null or is_cumulative_3_0_attainable is null
        then 'unknown'
        when not is_cumulative_3_0_attainable or target_cutoff_percent is null
        then 'goal_not_attainable'
        when cumulative_y1_gpa_projected_unweighted >= 3.0
        then 'on_pace'
        else 'not_on_pace'
    end as pace_status,
from with_target
