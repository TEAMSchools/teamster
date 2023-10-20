with
    grades_union as (
        select
            sg.studentid,
            sg.schoolid,
            sg.course_number,
            sg.academic_year,
            if(sg.excludefromgpa = 0, sg.potentialcrhrs, null) as potentialcrhrs,
            if(sg.excludefromgraduation = 0, sg.earnedcrhrs, null) as earnedcrhrs,
            if(sg.excludefromgpa = 0, sg.gpa_points, null) as gpa_points,
            if(
                sg.excludefromgpa = 0, sg.potentialcrhrs, null
            ) as potentialcrhrs_projected,
            if(
                sg.excludefromgraduation = 0, sg.earnedcrhrs, null
            ) as earnedcrhrs_projected,
            if(sg.excludefromgpa = 0, sg.gpa_points, null) as gpa_points_projected,
            if(
                sg.excludefromgpa = 0, sg.potentialcrhrs, null
            ) as potentialcrhrs_projected_s1,
            if(
                sg.excludefromgraduation = 0, sg.earnedcrhrs, null
            ) as earnedcrhrs_projected_s1,
            if(sg.excludefromgpa = 0, sg.gpa_points, null) as gpa_points_projected_s1,
            if(
                sg.excludefromgpa = 0, sg.gpa_points, null
            ) as gpa_points_projected_s1_unweighted,
            if(
                sg.excludefromgpa = 0
                and sg.credit_type in ('MATH', 'SCI', 'ENG', 'SOC'),
                sg.potentialcrhrs,
                null
            ) as potentialcrhrs_core,
            if(
                sg.excludefromgpa = 0
                and sg.credit_type in ('MATH', 'SCI', 'ENG', 'SOC'),
                sg.gpa_points,
                null
            ) as gpa_points_core,

            if(sg.excludefromgpa = 0, su.grade_points, null) as unweighted_grade_points,
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        left join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as su
            on sg.percent between su.min_cutoffpercentage and su.max_cutoffpercentage
            and sg.gradescale_name_unweighted = su.gradescale_name
        where sg.storecode = 'Y1'

        union all

        select
            fg.studentid,

            co.schoolid,

            fg.course_number,

            {{ var("current_academic_year") }} as academic_year,
            null as potentialcrhrs,
            null as earnedcrhrs,
            null as gpa_points,

            if(
                fg.y1_letter_grade is null, null, fg.potential_credit_hours
            ) as potentialcrhrs_projected,
            if(
                fg.y1_letter_grade not like 'F%', fg.potential_credit_hours, 0.0
            ) as earnedcrhrs_projected,
            fg.y1_grade_points as gpa_points_projected,

            null as potentialcrhrs_projected_s1,
            null as earnedcrhrs_projected_s1,
            null as gpa_points_projected_s1,
            null as gpa_points_projected_s1_unweighted,
            null as potentialcrhrs_core,
            null as gpa_points_core,
            null as unweighted_grade_points,
        from {{ ref("base_powerschool__final_grades") }} as fg
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on fg.studentid = co.studentid
            and fg.yearid = co.yearid
            and co.rn_year = 1
        left join
            {{ ref("stg_powerschool__storedgrades") }} as sg
            on fg.studentid = sg.studentid
            and fg.course_number = sg.course_number
            and sg.academic_year = {{ var("current_academic_year") }}
            and sg.storecode = 'Y1'
        where
            fg.exclude_from_gpa = 0
            /* ensures already stored grades are excluded */
            and sg.studentid is null
            and current_date('{{ var("local_timezone") }}')
            between fg.termbin_start_date and fg.termbin_end_date

        union all

        /* semester 1 == y1 as of q2 */
        select
            fg.studentid,

            co.schoolid,

            fg.course_number,

            co.academic_year,

            null as potentialcrhrs,
            null as earnedcrhrs,
            null as gpa_points,
            null as potentialcrhrs_projected,
            null as earnedcrhrs_projected,
            null as gpa_points_projected,

            fg.potential_credit_hours as potentialcrhrs_projected_s1,
            if(
                fg.y1_letter_grade not like 'F%', fg.potential_credit_hours, 0
            ) as earnedcrhrs_projected_s1,
            fg.y1_grade_points as gpa_points_projected_s1,
            fg.y1_grade_points_unweighted as gpa_points_projected_s1_unweighted,

            null as potentialcrhrs_core,
            null as gpa_points_core,
            null as unweighted_grade_points,
        from {{ ref("base_powerschool__final_grades") }} as fg
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on fg.studentid = co.studentid
            and fg.yearid = co.yearid
            and co.rn_year = 1
        left join
            {{ ref("stg_powerschool__storedgrades") }} as sg
            on fg.studentid = sg.studentid
            and fg.course_number = sg.course_number
            and sg.academic_year = {{ var("current_academic_year") }}
            and sg.storecode = 'Y1'
        where
            fg.yearid = ({{ var("current_academic_year") }} - 1990)
            and fg.storecode = 'Q2'
            and fg.exclude_from_gpa = 0
            /* include only unstored current-year grades */
            and sg.studentid is null
    ),

    with_weighted_points as (
        select
            studentid,
            academic_year,
            schoolid,
            potentialcrhrs,
            earnedcrhrs,
            potentialcrhrs_projected,
            potentialcrhrs_projected_s1,
            potentialcrhrs_core,
            earnedcrhrs_projected,
            earnedcrhrs_projected_s1,
            (potentialcrhrs * gpa_points) as weighted_points,
            (potentialcrhrs * unweighted_grade_points) as unweighted_points,
            (potentialcrhrs_core * gpa_points_core) as weighted_points_core,
            (
                potentialcrhrs_projected * gpa_points_projected
            ) as weighted_points_projected,
            (
                potentialcrhrs_projected_s1 * gpa_points_projected_s1
            ) as weighted_points_projected_s1,
            (
                potentialcrhrs_projected_s1 * gpa_points_projected_s1_unweighted
            ) as weighted_points_projected_s1_unweighted,
        from grades_union
    ),

    points_rollup as (
        select
            studentid,
            schoolid,
            sum(weighted_points) as weighted_points,
            sum(weighted_points_core) as weighted_points_core,
            sum(weighted_points_projected) as weighted_points_projected,
            sum(weighted_points_projected_s1) as weighted_points_projected_s1,
            sum(
                weighted_points_projected_s1_unweighted
            ) as weighted_points_projected_s1_unweighted,
            sum(unweighted_points) as unweighted_points,
            sum(earnedcrhrs) as earned_credits_cum,
            sum(earnedcrhrs_projected) as earned_credits_cum_projected,
            sum(earnedcrhrs_projected_s1) as earned_credits_cum_projected_s1,
            sum(potentialcrhrs) as potentialcrhrs,
            sum(potentialcrhrs_core) as potentialcrhrs_core,
            sum(potentialcrhrs_projected) as potentialcrhrs_projected,
            sum(potentialcrhrs_projected_s1) as potentialcrhrs_projected_s1,
            sum(
                if(
                    academic_year < {{ var("current_academic_year") }},
                    earnedcrhrs,
                    potentialcrhrs
                )
            ) as potential_credits_cum,
        from with_weighted_points
        group by studentid, schoolid
    )

select
    studentid,
    schoolid,
    earned_credits_cum,
    potential_credits_cum,
    earned_credits_cum_projected,
    earned_credits_cum_projected_s1,
    round(safe_divide(weighted_points, potentialcrhrs), 2) as cumulative_y1_gpa,
    round(
        safe_divide(unweighted_points, potentialcrhrs), 2
    ) as cumulative_y1_gpa_unweighted,
    round(
        safe_divide(weighted_points_projected, potentialcrhrs_projected), 2
    ) as cumulative_y1_gpa_projected,
    round(
        safe_divide(weighted_points_projected_s1, potentialcrhrs_projected_s1), 2
    ) as cumulative_y1_gpa_projected_s1,
    round(
        safe_divide(
            weighted_points_projected_s1_unweighted, potentialcrhrs_projected_s1
        ),
        2
    ) as cumulative_y1_gpa_projected_s1_unweighted,
    round(
        safe_divide(weighted_points_core, potentialcrhrs_core), 2
    ) as core_cumulative_y1_gpa,
from points_rollup
