with
    school_levels as (
        -- grain projection, not dup-masking:
        -- _dbt_source_project/academic_year/ps_schoolid/school_level_alt.
        -- Sumner intentionally yields two rows; see the properties yml.
        select distinct
            _dbt_source_project, academic_year, ps_schoolid, school_level_alt,

        from {{ ref("int_students__school_directory") }}
        where
            -- summer toggle: see skill
            academic_year = {{ var("current_academic_year") }}
    ),

    week_school_levels as (
        select
            cw._dbt_source_project,
            cw.region,
            cw.`quarter`,
            cw.week_number_quarter,
            cw.week_start_monday,
            cw.school_week_end_date,

            coalesce(sl.school_level_alt, cw.school_level) as school_level,

        from {{ ref("int_students__calendar_week") }} as cw
        left join
            school_levels as sl
            on cw.academic_year = sl.academic_year
            and cw.schoolid = sl.ps_schoolid
            and cw._dbt_source_project = sl._dbt_source_project
        where
            -- summer toggle: see skill
            cw.academic_year = {{ var("current_academic_year") }}
            and cw.week_start_monday
            < date_trunc(current_date('{{ var("local_timezone") }}'), isoweek)
    ),

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

        from week_school_levels
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
    -- trunk-ignore(sqlfluff/RF06): keeps the uppercase header T&L uploads
    cnt_w as `W`,
    -- trunk-ignore(sqlfluff/RF06): keeps the uppercase header T&L uploads
    cnt_h as `H`,
    -- trunk-ignore(sqlfluff/RF06): keeps the uppercase header T&L uploads
    cnt_f as `F`,
    -- trunk-ignore(sqlfluff/RF06): keeps the uppercase header T&L uploads
    cnt_s as `S`,

    {{ var("current_academic_year") }} as academic_year,  /* summer toggle: see skill */

from week_expectations
