with
    source as (
        select *
        from {{ ref("rpt_tableau__fresh_dashboard_progress_to_goals") }}
    )

select
    academic_year,
    org,
    region,
    schoolid,
    school,
    school_level,

    case school_level
        when 'ES' then 1
        when 'MS' then 2
        when 'HS' then 3
    end as school_level_sort,

    -- school-level enrollment counts (grade_level = -1)
    sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Student'
                and grade_level = -1
                then student_count
        end
    ) as all_student_enrollment_s,

    sum(
        case
            when
                enrollment_type = 'New'
                and row_type = 'Student'
                and grade_level = -1
                then student_count
        end
    ) as new_student_enrollment_s,

    sum(
        case
            when
                enrollment_type = 'Returning'
                and row_type = 'Student'
                and grade_level = -1
                then student_count
        end
    ) as re_enroll_enrollment_s,

    -- school+grade enrollment counts (grade_level != -1)
    sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Student'
                and grade_level != -1
                then student_count
        end
    ) as all_student_enrollment_sg,

    sum(
        case
            when
                enrollment_type = 'New'
                and row_type = 'Student'
                and grade_level != -1
                then student_count
        end
    ) as new_student_enrollment_sg,

    sum(
        case
            when
                enrollment_type = 'Returning'
                and row_type = 'Student'
                and grade_level != -1
                then student_count
        end
    ) as re_enroll_enrollment_sg,

    -- target fields (school rollup, grade_level = -1)
    sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Goal'
                and grade_level = -1
                then seat_target
        end
    ) as seat_target_s,

    sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Goal'
                and grade_level = -1
                then fdos_target
        end
    ) as fdos_target_s,

    sum(
        case
            when
                enrollment_type = 'New'
                and row_type = 'Goal'
                and grade_level = -1
                then new_student_target
        end
    ) as new_student_target_s,

    sum(
        case
            when
                enrollment_type = 'Returning'
                and row_type = 'Goal'
                and grade_level = -1
                then re_enroll_projection
        end
    ) as re_enroll_projection_s,

    -- distance to target (count), school rollup
    sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Student'
                and grade_level = -1
                then student_count
        end
    )
    - sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Goal'
                and grade_level = -1
                then seat_target
        end
    ) as seat_target_distance_s,

    sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Student'
                and grade_level = -1
                then student_count
        end
    )
    - sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Goal'
                and grade_level = -1
                then fdos_target
        end
    ) as fdos_target_distance_s,

    sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Student'
                and grade_level = -1
                then student_count
        end
    ) - sum(budget_target) as budget_target_distance_s,

    sum(
        case
            when
                enrollment_type = 'New'
                and row_type = 'Student'
                and grade_level = -1
                then student_count
        end
    )
    - sum(
        case
            when
                enrollment_type = 'New'
                and row_type = 'Goal'
                and grade_level = -1
                then new_student_target
        end
    ) as new_student_target_distance_s,

    sum(
        case
            when
                enrollment_type = 'Returning'
                and row_type = 'Student'
                and grade_level = -1
                then student_count
        end
    )
    - sum(
        case
            when
                enrollment_type = 'Returning'
                and row_type = 'Goal'
                and grade_level = -1
                then re_enroll_projection
        end
    ) as re_enroll_target_distance_s,

    -- distance to target (count), school+grade
    sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Student'
                and grade_level != -1
                then student_count
        end
    ) - sum(seat_target) as seat_target_distance_sg,

    sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Student'
                and grade_level != -1
                then student_count
        end
    ) - sum(fdos_target) as fdos_target_distance_sg,

    sum(
        case
            when
                enrollment_type = 'All'
                and row_type = 'Student'
                and grade_level != -1
                then student_count
        end
    ) - sum(budget_target) as budget_target_distance_sg,

    sum(
        case
            when
                enrollment_type = 'New'
                and row_type = 'Student'
                and grade_level != -1
                then student_count
        end
    ) - sum(new_student_target) as new_student_target_distance_sg,

    sum(
        case
            when
                enrollment_type = 'Returning'
                and row_type = 'Student'
                and grade_level != -1
                then student_count
        end
    ) - sum(re_enroll_projection) as re_enroll_target_distance_sg,

    -- percent distance to target (school rollup)
    safe_divide(
        sum(
            case
                when
                    enrollment_type = 'All'
                    and row_type = 'Student'
                    and grade_level = -1
                    then student_count
            end
        )
        - sum(
            case
                when
                    enrollment_type = 'All'
                    and row_type = 'Goal'
                    and grade_level = -1
                    then seat_target
            end
        ),
        sum(
            case
                when
                    enrollment_type = 'All'
                    and row_type = 'Goal'
                    and grade_level = -1
                    then seat_target
            end
        )
    ) as seat_target_distance_pct,

    safe_divide(
        sum(
            case
                when
                    enrollment_type = 'All'
                    and row_type = 'Student'
                    and grade_level = -1
                    then student_count
            end
        )
        - sum(
            case
                when
                    enrollment_type = 'All'
                    and row_type = 'Goal'
                    and grade_level = -1
                    then fdos_target
            end
        ),
        sum(
            case
                when
                    enrollment_type = 'All'
                    and row_type = 'Goal'
                    and grade_level = -1
                    then fdos_target
            end
        )
    ) as fdos_target_distance_pct,

    safe_divide(
        sum(
            case
                when
                    enrollment_type = 'All'
                    and row_type = 'Student'
                    and grade_level = -1
                    then student_count
            end
        ) - sum(budget_target),
        sum(budget_target)
    ) as budget_target_distance_pct,

    safe_divide(
        sum(
            case
                when
                    enrollment_type = 'New'
                    and row_type = 'Student'
                    and grade_level = -1
                    then student_count
            end
        )
        - sum(
            case
                when
                    enrollment_type = 'New'
                    and row_type = 'Goal'
                    and grade_level = -1
                    then new_student_target
            end
        ),
        sum(
            case
                when
                    enrollment_type = 'New'
                    and row_type = 'Goal'
                    and grade_level = -1
                    then new_student_target
            end
        )
    ) as new_student_target_distance_pct,

    safe_divide(
        sum(
            case
                when
                    enrollment_type = 'Returning'
                    and row_type = 'Student'
                    and grade_level = -1
                    then student_count
            end
        )
        - sum(
            case
                when
                    enrollment_type = 'Returning'
                    and row_type = 'Goal'
                    and grade_level = -1
                    then re_enroll_projection
            end
        ),
        sum(
            case
                when
                    enrollment_type = 'Returning'
                    and row_type = 'Goal'
                    and grade_level = -1
                    then re_enroll_projection
            end
        )
    ) as re_enroll_target_distance_pct,

from source
group by
    academic_year,
    org,
    region,
    schoolid,
    school,
    school_level,
