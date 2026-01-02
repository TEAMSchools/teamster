with
    temp_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_finalsite__status_report"),
                partition_by="surrogate_key",
                order_by="effective_date",
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

            concat(student_first_name, student_last_name, grade_level) as name_join,

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
    )

select
    d.* except (enrollment_type),

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
    and d.powerschool_student_number is not null
left join
    enrollment_type_calc as j2
    on d.name_join = j2.name_join
    and d.powerschool_student_number is null
