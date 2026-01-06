with
    finalsite_report as (
        select
            f.*,

            x.region,
            x.powerschool_school_id,
            x.abbreviation as school_abbreviation,

            concat(f.first_name, f.last_name) as name_join,
            concat(f.first_name, f.last_name, f.grade_level) as name_grade_level_join,
        from {{ ref("stg_finalsite__status_report") }} as f
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on f.school = x.name

    ),

    enrollment_history_calc as (
        select
            student_number,
            student_first_name,
            student_last_name,
            academic_year,

            academic_year + 1 as academic_year_next,

            concat(student_first_name, student_last_name) as name_join,

            sum(
                if(date_diff(exitdate, entrydate, day) >= 7, 1, 0)
            ) as enroll_type_check,

        from {{ ref("int_extracts__student_enrollments") }}
        where grade_level != 99
        group by student_number, student_first_name, student_last_name, academic_year
    ),

    enrollment_type_calc as (
        select
            * except (enroll_type_check),

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
        select
            d.* except (enrollment_type),

            j1.student_number as ps_student_number,

            coalesce(
                if(
                    d.powerschool_student_number is not null,
                    j1.enrollment_type,
                    j2.enrollment_type
                ),
                'New'
            ) as enrollment_type,

        from finalsite_report as d
        left join
            enrollment_type_calc as j1
            on d.powerschool_student_number = j1.student_number
            and d.academic_year = j1.academic_year_next
            and d.powerschool_student_number is not null
        left join
            enrollment_type_calc as j2
            on d.name_join = j2.name_join
            and d.academic_year = j1.academic_year_next
            and d.powerschool_student_number is null
    )

select
    m.academic_year,
    m.detailed_status,
    m.enrollment_year,
    m.finalsite_student_id,
    m.first_name,
    m.grade_level,
    m.grade_level_name,
    m.last_name,
    m.powerschool_student_number,
    m.school,
    m.status,
    m.status_start_date,
    m.region,
    m.powerschool_school_id,
    m.school_abbreviation,
    m.name_join,
    m.name_grade_level_join,
    m.ps_student_number,
    m.enrollment_type,

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
    {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
    -- TODO: fix this later when int view is fixed
    on m.academic_year = x.enrollment_academic_year
    and m.enrollment_type = x.enrollment_type
    and m.detailed_status = x.detailed_status
