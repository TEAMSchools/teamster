with
    school_levels as (
        -- grain projection, not dup-masking:
        -- _dbt_source_project/academic_year/ps_schoolid/school_level_alt.
        -- Sumner intentionally yields two rows; see the properties yml.
        select distinct
            _dbt_source_project, academic_year, ps_schoolid, school_level_alt,

        from {{ ref("int_students__school_directory") }}
        where academic_year = {{ var("current_academic_year") }}
    ),

    week_school_levels as (
        select
            cw._dbt_source_project,
            cw.academic_year,
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
            and cw._dbt_source_project != 'kippmiami'
    )

select
    academic_year,
    region,
    school_level,
    `quarter`,
    week_number_quarter,
    week_start_monday,

    max(school_week_end_date) as week_end_friday,

from week_school_levels
where school_level != 'ES'
group by
    academic_year,
    region,
    school_level,
    `quarter`,
    week_number_quarter,
    week_start_monday
