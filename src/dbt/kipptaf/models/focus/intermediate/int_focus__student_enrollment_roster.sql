with
    -- Reads the roster, not int_focus__student_enrollment. The reshape in #5009
    -- left the latter a thin staging-plus-pivot-labels view and moved the wide
    -- spine here, so the five columns excluded below only exist on the roster.
    -- union_relations resolves its column list at compile time from the
    -- relation's INFORMATION_SCHEMA, so the stale prod view kept enumerating
    -- columns the upstream had already dropped and stopped parsing entirely.
    -- The district roster trims each stint to the day before the student's
    -- next stint starts, so exitdate here is the inclusive last day and stints
    -- never overlap.
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__student_enrollment_roster"),
                ]
            )
        }}
    ),

    with_source_project as (
        select
            *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
        from union_relations
    ),

    enrollments as (
        select *, {{ extract_region("with_source_project") }} as region,
        from with_source_project
    )

select
    e.* except (
        school_number,
        school_title,
        school_state_school_id,
        grade_level_short_name,
        school_level
    ),

    loc.powerschool_school_id as ps_schoolid,
    loc.location_name as school,
    loc.abbreviation as school_abbreviation,
    loc.reporting_school_id as reporting_schoolid,
    loc.location_region as region_official_name,
    loc.deanslist_school_id,

    'KTAF' as district,

    -- Two closed schools (Focus ids 71 and 72, KIPP Miami Sunrise Academy and
    -- KIPP Miami-Liberty City) carry no Focus school-level label, so
    -- e.school_level is null for their ~3,056 historical rows. The
    -- crosswalk's grade_band covers both from the same PowerSchool-era
    -- archive (Sunrise ES, Liberty MS), so it's the fallback.
    coalesce(e.school_level, loc.grade_band) as school_level,

    concat(e.region, coalesce(e.school_level, loc.grade_band)) as region_school_level,

from enrollments as e
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on e.school_number = loc.focus_school_id
