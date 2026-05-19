with
    historical as (
        select
            sg.studentid,
            sg.schoolid,

            sum(if(sg.excludefromgpa = 0, sg.potentialcrhrs, null)) as potentialcrhrs_hist,
            sum(
                if(sg.excludefromgpa = 0, sg.potentialcrhrs * su.grade_points, null)
            ) as unweighted_points_hist,
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        left join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as su
            on sg.percent between su.min_cutoffpercentage and su.max_cutoffpercentage
            and sg.gradescale_name_unweighted = su.gradescale_name
        where sg.storecode = 'Y1'
        group by sg.studentid, sg.schoolid
    ),

    enrolled as (
        select
            fg.studentid,
            fg.schoolid,

            sum(
                if(
                    fg.exclude_from_gpa = 0 and fg.y1_letter_grade is not null,
                    fg.potential_credit_hours,
                    null
                )
            ) as enrolled_potentialcrhrs,
        from {{ ref("base_powerschool__final_grades") }} as fg
        left join
            {{ ref("stg_powerschool__storedgrades") }} as sg
            on fg.studentid = sg.studentid
            and fg.course_number = sg.course_number
            and sg.academic_year = {{ var("current_academic_year") }}
            and sg.storecode = 'Y1'
        where
            fg.exclude_from_gpa = 0
            and sg.studentid is null
            and current_date('{{ var("local_timezone") }}')
            between fg.termbin_start_date and fg.termbin_end_date
        group by fg.studentid, fg.schoolid
    )

/*
    cumulative_y1_gpa_projected_unweighted (from int_powerschool__gpa_cumulative):
        = (unweighted_points_hist + enrolled_crhrs × current_y1_uw_gpa)
          / (potentialcrhrs_hist + enrolled_crhrs)

    solving for current_y1_uw_gpa given a target T:
        needed_y1_uw_gpa = (T × (potentialcrhrs_hist + enrolled_crhrs) - unweighted_points_hist)
                           / enrolled_crhrs

    the result is the unweighted Y1 GPA a student must earn across all currently
    enrolled courses this year for their projected cumulative to equal T.
*/
select
    e.studentid,
    e.schoolid,
    e.enrolled_potentialcrhrs,

    round(
        safe_divide(
            2.5 * (coalesce(h.potentialcrhrs_hist, 0) + e.enrolled_potentialcrhrs)
            - coalesce(h.unweighted_points_hist, 0),
            e.enrolled_potentialcrhrs
        ),
        2
    ) as needed_gpa_unweighted_for_2_5,
    round(
        safe_divide(
            3.0 * (coalesce(h.potentialcrhrs_hist, 0) + e.enrolled_potentialcrhrs)
            - coalesce(h.unweighted_points_hist, 0),
            e.enrolled_potentialcrhrs
        ),
        2
    ) as needed_gpa_unweighted_for_3_0,
    round(
        safe_divide(
            3.5 * (coalesce(h.potentialcrhrs_hist, 0) + e.enrolled_potentialcrhrs)
            - coalesce(h.unweighted_points_hist, 0),
            e.enrolled_potentialcrhrs
        ),
        2
    ) as needed_gpa_unweighted_for_3_5,
from enrolled as e
left join historical as h on e.studentid = h.studentid and e.schoolid = h.schoolid
