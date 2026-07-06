with
    stored_grades as (
        select
            sg.studentid,
            sg.schoolid,
            sg.academic_year,

            if(sg.excludefromgpa = 0, sg.potentialcrhrs, null) as potentialcrhrs,
            if(sg.excludefromgraduation = 0, sg.earnedcrhrs, null) as earnedcrhrs,
            if(sg.excludefromgpa = 0, sg.gpa_points, null) as gpa_points,
            if(sg.excludefromgpa = 0, su.grade_points, null) as unweighted_grade_points,
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        left join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as su
            on sg.percent between su.min_cutoffpercentage and su.max_cutoffpercentage
            and sg.gradescale_name_unweighted = su.gradescale_name
        where
            sg.storecode = 'Y1'
            and sg.academic_year < {{ var("current_academic_year") }}
    ),

    year_rollup as (
        select
            studentid,
            schoolid,
            academic_year,

            sum(potentialcrhrs * gpa_points) as weighted_points,
            sum(potentialcrhrs * unweighted_grade_points) as unweighted_points,
            sum(potentialcrhrs) as potential_gpa_credits,
            sum(earnedcrhrs) as earned_credits,
        from stored_grades
        group by studentid, schoolid, academic_year
    ),

    running_totals as (
        select
            studentid,
            schoolid,
            academic_year,

            sum(weighted_points) over (
                partition by studentid, schoolid order by academic_year
            ) as weighted_points_cum,
            sum(unweighted_points) over (
                partition by studentid, schoolid order by academic_year
            ) as unweighted_points_cum,
            sum(potential_gpa_credits) over (
                partition by studentid, schoolid order by academic_year
            ) as potential_gpa_credits_cum,
            sum(earned_credits) over (
                partition by studentid, schoolid order by academic_year
            ) as earned_credits_cum,
        from year_rollup
    ),

    completed_years as (
        select
            rt.studentid,
            rt.schoolid,
            rt.academic_year,
            rt.earned_credits_cum,
            rt.potential_gpa_credits_cum,

            enr.grade_level,

            false as is_projected,

            round(
                safe_divide(rt.weighted_points_cum, rt.potential_gpa_credits_cum), 2
            ) as cumulative_y1_gpa,
            round(
                safe_divide(rt.unweighted_points_cum, rt.potential_gpa_credits_cum), 2
            ) as cumulative_y1_gpa_unweighted,
        from running_totals as rt
        left join
            {{ ref("base_powerschool__student_enrollments") }} as enr
            on rt.studentid = enr.studentid
            and rt.academic_year = enr.academic_year
            and enr.rn_year = 1
    ),

    projected_current_year as (
        select
            gc.studentid,
            gc.schoolid,
            gc.earned_credits_cum_projected as earned_credits_cum,
            gc.potential_gpa_credits_cum_projected as potential_gpa_credits_cum,
            gc.cumulative_y1_gpa_projected as cumulative_y1_gpa,

            enr.grade_level,

            {{ var("current_academic_year") }} as academic_year,
            true as is_projected,

            gc.cumulative_y1_gpa_projected_unweighted as cumulative_y1_gpa_unweighted,
        from {{ ref("int_powerschool__gpa_cumulative") }} as gc
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as enr
            on gc.studentid = enr.studentid
            and gc.schoolid = enr.schoolid
            and enr.academic_year = {{ var("current_academic_year") }}
            and enr.rn_year = 1
    )

select
    studentid,
    schoolid,
    academic_year,
    grade_level,
    earned_credits_cum,
    potential_gpa_credits_cum,
    cumulative_y1_gpa,
    cumulative_y1_gpa_unweighted,
    is_projected,
from completed_years

union all

select
    studentid,
    schoolid,
    academic_year,
    grade_level,
    earned_credits_cum,
    potential_gpa_credits_cum,
    cumulative_y1_gpa,
    cumulative_y1_gpa_unweighted,
    is_projected,
from projected_current_year
