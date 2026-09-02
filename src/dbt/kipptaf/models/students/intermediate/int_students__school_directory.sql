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
            u.region,
            u.grade_level,
            u.schoolid,
            u.schoolid as ps_schoolid,

            {{ var("current_academic_year") }} + 1 as academic_year,

            'finalsite' as school_source,

            'kipp' || lower(u.region) as _dbt_source_project,

        from {{ ref("int_finalsite__status_report_unpivot") }} as u
        left join
            enrolled as e
            on u.region = e.region
            and u.schoolid = e.ps_schoolid
            and u.grade_level = e.grade_level
        where
            u.enrollment_academic_year = {{ var("current_academic_year") }} + 1
            -- schoolid 0 is Finalsite's "No School Assigned"
            and u.schoolid != 0
            -- anti-join: only school/grade pairs no SIS has ever carried
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
