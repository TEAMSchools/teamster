with
    term_weeks as (
        /*
        calendar_week is per-schoolid; school_week_end_date varies across the
        schools in a region when only some of them lose a day to a holiday or
        PD, so take the region's latest in-session day rather than distinct
        (which would fan the join out to one row per end date)
        */
        select
            _dbt_source_project,
            region,
            school_level,
            `quarter`,
            week_number_quarter,
            week_start_monday,

            max(school_week_end_date) as school_week_end_date,

        from {{ ref("int_students__calendar_week") }}
        where
            -- summer toggle: see skill
            academic_year = {{ var("current_academic_year") - 1 }}
            and week_start_monday
            < date_trunc(current_date('{{ var("local_timezone") }}'), isoweek)
        group by
            _dbt_source_project,
            region,
            school_level,
            `quarter`,
            week_number_quarter,
            week_start_monday
    ),

    week_expectations as (
        select
            u.school_level,
            u.`quarter`,
            u.cnt_w,
            u.cnt_h,
            u.cnt_f,
            u.cnt_s,
            u.notes,

            tw.region,
            tw.week_number_quarter,
            tw.week_start_monday,
            tw.school_week_end_date,

        from {{ ref("stg_powerschool__u_expectations") }} as u
        inner join
            term_weeks as tw
            on u.school_level = tw.school_level
            and u.`quarter` = tw.`quarter`
            and u.week_number = tw.week_number_quarter
            and u._dbt_source_project = tw._dbt_source_project
    )

select
    region,
    school_level,
    `quarter`,
    week_number_quarter,
    week_start_monday,
    school_week_end_date as week_end_friday,
    notes,
    cnt_w as `W`,
    cnt_h as `H`,
    cnt_f as `F`,
    cnt_s as `S`,

    {{ var("current_academic_year") - 1 }} as academic_year,  /* summer toggle: see skill */

from week_expectations
