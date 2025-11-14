with
    student_week as (
        select
            co.*,

            cw.week_start_monday,
            cw.week_end_sunday,
            cw.quarter,
            cw.semester,
            cw.school_week_start_date,
            cw.school_week_end_date,
            cw.week_number_academic_year,
            cw.week_number_quarter,
            cw.is_current_week_mon_sun,
            cw.date_count,

            if(
                cw.week_start_monday between co.entrydate and co.exitdate, true, false
            ) as is_enrolled_week,

            if(
                cw.week_end_sunday between co.entrydate and co.exitdate, true, false
            ) as is_enrolled_week_end,
        from {{ ref("int_extracts__student_enrollments") }} as co
        inner join
            {{ ref("int_powerschool__calendar_week") }} as cw
            on co.academic_year = cw.academic_year
            and co.schoolid = cw.schoolid
    )

    {{
        dbt_utils.deduplicate(
            relation="student_week",
            partition_by="_dbt_source_relation, student_number, week_start_monday",
            order_by="is_enrolled_week desc",
        )
    }}
