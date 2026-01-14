with
    distinct_rows as (
        select distinct
            * except (enrollment_type, `status`),

            initcap(replace(`status`, '_', ' ')) as detailed_status,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

            cast(academic_year as string)
            || '-'
            || right(cast(academic_year + 1 as string), 2) as academic_year_display,

        from {{ source("google_sheets", "src_google_sheets__finalsite__sample_data") }}
    ),

    end_date_calc as (
        select
            *,

            lead(status_start_date - 1, 1, current_date('America/New_York')) over (
                partition by finalsite_student_id, enrollment_year
                order by status_start_date asc
            ) as status_end_date,

        from distinct_rows
    )

select
    *,

    if(
        status_end_date = status_start_date,
        1,
        date_diff(status_end_date, status_start_date, day)
    ) as days_in_status,

from end_date_calc
