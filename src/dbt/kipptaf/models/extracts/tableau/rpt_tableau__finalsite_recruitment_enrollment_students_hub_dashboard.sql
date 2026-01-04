with
    temp_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_finalsite__status_report"),
                partition_by="surrogate_key",
                order_by="status_start_date",
            )
        }}
    ),

    enrollment_history_calc as (
        select
            academic_year,
            student_number,
            student_first_name,
            student_last_name,

            sum(
                if(date_diff(exitdate, entrydate, day) >= 7, 1, 0)
            ) as enroll_type_check,

        from {{ ref("int_extracts__student_enrollments") }}
        where grade_level != 99
        group by academic_year, student_number, student_first_name, student_last_name
    ),

    enrollment_type_calc as (
        select
            * except (enroll_type_check),

            concat(student_first_name, student_last_name) as name_join,

            case
                when
                    coalesce(
                        lag(enroll_type_check) over (
                            partition by student_number order by academic_year
                        ),
                        0
                    )
                    = 0
                then 'New'
                when
                    coalesce(
                        lag(enroll_type_check) over (
                            partition by student_number order by academic_year
                        ),
                        0
                    )
                    = 1
                    and academic_year - coalesce(
                        lag(academic_year) over (
                            partition by student_number order by academic_year
                        ),
                        0
                    )
                    > 1
                then 'New'
                else 'Returner'
            end as enrollment_type,

        from enrollment_history_calc
    ),

    mod_enrollment_type as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            d.*,

            j1.student_number as ps_student_number,

            coalesce(
                if(
                    d.powerschool_student_number is not null,
                    j1.enrollment_type,
                    j2.enrollment_type
                ),
                'New'
            ) as enrollment_type,

        from temp_deduplicate as d
        left join
            enrollment_type_calc as j1
            on d.powerschool_student_number = j1.student_number
            -- remove -1 once the upstream table updates
            and d.academic_year - 1 = j1.academic_year
            and d.powerschool_student_number is not null
        left join
            enrollment_type_calc as j2
            on d.name_join = j2.name_join
            -- remove -1 once the upstream table updates
            and d.academic_year - 1 = j1.academic_year
            and d.powerschool_student_number is null
    )

select
    m.*,

    x.overall_status,
    x.funnel_status,
    x.status_category,
    x.detailed_status_ranking,
    x.powerschool_enroll_status,
    x.valid_detailed_status,
    x.offered,
    x.conversion,
    x.offered_ops,
    x.conversion_ops,

    current_date('{{ var("local_timezone") }}') as today_date,

    count(*) over (partition by m.academic_year, m.finalsite_student_id) as rn,

    case
        when count(*) over (partition by m.academic_year, m.finalsite_student_id) = 1
        then
            coalesce(
                lag(m.status_start_date) over (
                    partition by m.academic_year, m.finalsite_student_id
                    order by x.detailed_status_ranking
                ),
                current_date('{{ var("local_timezone") }}')
            )
        else
            coalesce(
                lead(m.status_start_date - 1) over (
                    partition by m.academic_year, m.finalsite_student_id
                    order by x.detailed_status_ranking
                ),
                current_date('{{ var("local_timezone") }}')
            )
    end as status_end_date,

    coalesce(
        lag(m.status_start_date) over (
            partition by m.academic_year, m.name_grade_level_join
            order by x.detailed_status_ranking
        ),
        current_date('{{ var("local_timezone") }}')
    ) as previous_date,

    coalesce(
        lead(m.status_start_date - 1) over (
            partition by m.academic_year, m.finalsite_student_id
            order by x.detailed_status_ranking
        ),
        current_date('{{ var("local_timezone") }}')
    ) as next_date,

from mod_enrollment_type as m
left join
    {{ ref("stg_google_sheets__finalsite_status_crosswalk") }} as x
    -- fix this later when int view is fixed
    on m.academic_year = x.enrollment_academic_year
    and m.enrollment_type = x.enrollment_type
    and m.detailed_status = x.detailed_status
