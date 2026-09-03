with
    enrolled as (
        -- grain projection, not dup-masking:
        -- academic_year/region/ps_schoolid/grade_level
        select distinct
            _dbt_source_project,
            academic_year,
            region,
            schoolid,
            schoolid as ps_schoolid,
            grade_level,

            'powerschool' as school_source,

        from {{ ref("int_powerschool__student_enrollment_union") }}
        -- 999999 is the graduated-students placeholder
        where schoolid != 999999 and grade_level is not null

        union all

        -- grain projection, not dup-masking:
        -- academic_year/region/ps_schoolid/grade_level
        select distinct
            _dbt_source_project,
            academic_year,
            region,
            schoolid,
            ps_schoolid,
            grade_level,

            'focus' as school_source,

        from {{ ref("int_focus__student_enrollment_roster") }}
        -- A fixed boundary, not the current year -- do not swap for
        -- current_academic_year. Focus reaches back to AY2018, but Miami's
        -- PowerSchool archive owns through AY2025. Null ps_schoolid drops Focus's
        -- non-instructional Applicants school and would break ps_schoolid's job as
        -- the cross-SIS join key.
        where academic_year >= 2026 and ps_schoolid is not null
    ),

    -- grain projection: the anti-join leaves at most one row per
    -- region/ps_schoolid/grade_level, and academic_year is a literal
    incoming as (
        select distinct
            sr._dbt_source_project,
            sr.region,
            sr.grade_level,
            x.location_powerschool_school_id as schoolid,
            x.location_powerschool_school_id as ps_schoolid,

            {{ var("current_academic_year") }} + 1 as academic_year,

            'finalsite' as school_source,

        from {{ ref("stg_finalsite__status_report") }} as sr
        inner join
            {{ ref("int_people__location_crosswalk") }} as x
            on sr.assigned_school = x.location_name
        left join
            enrolled as e
            on sr.region = e.region
            and sr.grade_level = e.grade_level
            and sr.active_school_year_int = e.academic_year
            and x.location_powerschool_school_id = e.ps_schoolid
        where
            sr.active_school_year_int = {{ var("current_academic_year") }} + 1
            -- ps_schoolid is the grain key and the cross-SIS join key, so an
            -- unresolved crosswalk row cannot be carried
            and x.location_powerschool_school_id is not null
            -- Finalsite is authoritative for next year, so this keeps continuing
            -- schools, not just brand-new ones. Scoped to the SAME year purely to
            -- stop a duplicate once a SIS starts carrying next year too, which
            -- happens when PowerSchool rolls over before the year begins.
            and e.ps_schoolid is null
    )

select
    _dbt_source_project,
    academic_year,
    region,
    schoolid,
    ps_schoolid,
    grade_level,
    school_source,

from enrolled

union all

select
    _dbt_source_project,
    academic_year,
    region,
    schoolid,
    ps_schoolid,
    grade_level,
    school_source,

from incoming
