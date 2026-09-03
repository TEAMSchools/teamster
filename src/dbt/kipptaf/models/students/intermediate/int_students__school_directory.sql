with
    directory as (
        -- grain projection, not dup-masking:
        -- academic_year/region/ps_schoolid/grade_level
        select distinct
            _dbt_source_project,
            academic_year,
            region,
            schoolid as ps_schoolid,
            grade_level,

            'sis' as school_source,

        from {{ ref("int_students__student_enrollment_union") }}
        -- 999999 is the graduated-students placeholder
        where schoolid != 999999 and grade_level is not null

        union all

        -- grain projection, not dup-masking:
        -- academic_year/region/ps_schoolid/grade_level
        select distinct
            sr._dbt_source_project,
            sr.active_school_year_int as academic_year,
            sr.region,
            x.location_powerschool_school_id as ps_schoolid,
            sr.grade_level,

            'finalsite' as school_source,

        from {{ ref("stg_finalsite__status_report") }} as sr
        -- location_name is the crosswalk's unique key; the school id fans out
        inner join
            {{ ref("int_people__location_crosswalk") }} as x
            on sr.assigned_school = x.location_name
        where
            sr.active_school_year_int = {{ var("current_academic_year") }} + 1
            -- a file's grade is correct only for its own cycle year
            and cast(left(sr._dagster_partition_key, 4) as int)
            = sr.active_school_year_int
            and x.location_powerschool_school_id is not null
            and x.location_powerschool_school_id != 0
            and not x.location_is_pathways
            and sr.grade_level is not null
    ),

    school_attributes as (
        select
            powerschool_school_id as ps_schoolid,
            location_name as school_name,
            abbreviation as school_short_name,
            grade_band as school_level,
            focus_school_id,

        from {{ ref("stg_google_sheets__people__locations") }}
        where
            powerschool_school_id is not null
            and abbreviation is not null
            and powerschool_school_id != 0
            and not is_pathways
    )

select
    d._dbt_source_project,
    d.academic_year,
    d.region,
    d.ps_schoolid,
    d.grade_level,
    d.school_source,

    s.school_name,
    s.school_short_name,
    s.school_level,
    s.focus_school_id,

    -- TODO: figure out a better way to track these
    case
        when
            d.academic_year >= 2025
            and s.school_short_name = 'Sumner'
            and d.grade_level >= 5
        then 'MS'
        else s.school_level
    end as school_level_alt,

from directory as d
left join school_attributes as s on d.ps_schoolid = s.ps_schoolid
