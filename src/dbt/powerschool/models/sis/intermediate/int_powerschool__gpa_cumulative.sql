with
    gradescale_max as (
        select gradescaleid, max(grade_points) as max_grade_points,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        group by gradescaleid
    ),

    /* every GPA course on this year's schedule, keyed on the rn_year = 1
       school, with the most unweighted points it can still earn. final_grades
       is one row per course and termbin, so the group by picks one row per
       course; its Y1 is a running value, so the last term's is the final one */
    current_year_courses as (
        select
            fg.studentid,
            fg.course_number,

            co.schoolid,

            max(fg.potential_credit_hours) as potential_credit_hours,

            /* ended with no Y1 reads null, not the scale max: unknown */
            if(
                max(fg.termbin_end_date) < current_date('{{ var("local_timezone") }}'),
                max_by(fg.y1_grade_points_unweighted, fg.termbin_end_date),
                max(gsm_u.max_grade_points)
            ) as max_grade_points_unweighted,
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
        left join
            gradescale_max as gsm_u
            on fg.courses_gradescaleid_unweighted = gsm_u.gradescaleid
        where
            fg.yearid = {{ var("current_academic_year") - 1990 }}
            and fg.exclude_from_gpa = 0
            and fg.potential_credit_hours > 0
            /* a course already stored this year is counted from storedgrades */
            and sg.studentid is null
        group by fg.studentid, fg.course_number, co.schoolid

        union all

        /* a course stored this year is locked at its stored unweighted points */
        select
            sg.studentid,
            sg.course_number,

            co.schoolid,

            sg.potentialcrhrs as potential_credit_hours,

            su.grade_points as max_grade_points_unweighted,
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on sg.studentid = co.studentid
            and co.academic_year = {{ var("current_academic_year") }}
            and co.rn_year = 1
        left join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as su
            on sg.percent between su.min_cutoffpercentage and su.max_cutoffpercentage
            and sg.gradescale_name_unweighted = su.gradescale_name
        where
            sg.storecode = 'Y1'
            and sg.academic_year = {{ var("current_academic_year") }}
            and sg.excludefromgpa = 0
    ),

    current_year_max as (
        select
            studentid,
            schoolid,

            sum(potential_credit_hours) as potentialcrhrs_current,
            sum(
                potential_credit_hours * max_grade_points_unweighted
            ) as unweighted_points_projected_max_current,
            countif(
                potential_credit_hours > 0 and max_grade_points_unweighted is null
            ) as n_current_max_unknown,
        from current_year_courses
        group by studentid, schoolid
    ),

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
            if(
                sg.excludefromgpa = 0, su.grade_points, null
            ) as unweighted_grade_points_projected,
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

            fg.y1_grade_points_unweighted as unweighted_grade_points_projected,
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
            null as unweighted_grade_points_projected,
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
            fg.yearid = {{ var("current_academic_year") - 1990 }}
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
            (
                potentialcrhrs_projected * unweighted_grade_points_projected
            ) as weighted_points_projected_unweighted,
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
            sum(
                weighted_points_projected_unweighted
            ) as weighted_points_projected_unweighted,
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
            sum(
                if(
                    academic_year < {{ var("current_academic_year") }},
                    unweighted_points,
                    null
                )
            ) as unweighted_points_prior,
            sum(
                if(
                    academic_year < {{ var("current_academic_year") }},
                    potentialcrhrs,
                    null
                )
            ) as potentialcrhrs_prior,
        from with_weighted_points
        group by studentid, schoolid
    ),

    needed_gpa as (
        select
            pr.*,

            cm.potentialcrhrs_current,

            safe_divide(
                (
                    3.0
                    * (coalesce(pr.potentialcrhrs_prior, 0) + cm.potentialcrhrs_current)
                )
                - coalesce(pr.unweighted_points_prior, 0),
                cm.potentialcrhrs_current
            ) as gpa_needed_raw,

            /* a course whose max is unknown makes the student's max unknowable;
               null it (flag reads unknown) rather than understate it by keeping
               the course's credits in the denominator only */
            if(
                cm.n_current_max_unknown = 0,
                safe_divide(
                    cm.unweighted_points_projected_max_current,
                    cm.potentialcrhrs_current
                ),
                null
            ) as gpa_max_current_raw,
        from points_rollup as pr
        left join
            current_year_max as cm
            on pr.studentid = cm.studentid
            and pr.schoolid = cm.schoolid
    )

select
    ng.studentid,
    ng.schoolid,
    ng.earned_credits_cum,
    ng.potential_credits_cum,
    ng.earned_credits_cum_projected,
    ng.earned_credits_cum_projected_s1,
    ng.potentialcrhrs_projected as potential_gpa_credits_cum_projected,
    ng.potentialcrhrs_current as potential_gpa_credits_current_year,

    s.dcid as students_dcid,
    s.student_number as students_student_number,

    sch.name as school_name,
    sch.abbreviation as school_abbreviation,
    sch.school_level,

    round(safe_divide(ng.weighted_points, ng.potentialcrhrs), 2) as cumulative_y1_gpa,
    round(
        safe_divide(ng.unweighted_points, ng.potentialcrhrs), 2
    ) as cumulative_y1_gpa_unweighted,
    round(
        safe_divide(ng.weighted_points_projected, ng.potentialcrhrs_projected), 2
    ) as cumulative_y1_gpa_projected,
    round(
        safe_divide(ng.weighted_points_projected_s1, ng.potentialcrhrs_projected_s1), 2
    ) as cumulative_y1_gpa_projected_s1,
    round(
        safe_divide(
            ng.weighted_points_projected_s1_unweighted, ng.potentialcrhrs_projected_s1
        ),
        2
    ) as cumulative_y1_gpa_projected_s1_unweighted,
    round(
        safe_divide(
            ng.weighted_points_projected_unweighted, ng.potentialcrhrs_projected
        ),
        2
    ) as cumulative_y1_gpa_projected_unweighted,
    round(
        safe_divide(ng.weighted_points_core, ng.potentialcrhrs_core), 2
    ) as core_cumulative_y1_gpa,

    round(ng.gpa_needed_raw, 2) as gpa_needed_for_cumulative_3_0,

    round(ng.gpa_needed_raw, 2)
    <= round(ng.gpa_max_current_raw, 2) as is_cumulative_3_0_attainable,
from needed_gpa as ng
left join {{ ref("stg_powerschool__students") }} as s on ng.studentid = s.id
left join
    {{ ref("stg_powerschool__schools") }} as sch on ng.schoolid = sch.school_number
