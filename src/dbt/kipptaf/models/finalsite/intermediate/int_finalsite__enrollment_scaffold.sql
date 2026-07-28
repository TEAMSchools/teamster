with
    powerschool_region as (
        select
            sps.school_number,
            sps.abbreviation,
            sps._dbt_source_project,
            {{ extract_region("sps") }} as region,

        from {{ ref("stg_powerschool__schools") }} as sps
        where sps.state_excludefromreporting = 0
    ),

    -- Miami's SIS moved to Focus (#4441); stg_powerschool__schools' Miami
    -- rows are a frozen pre-migration snapshot, not a live source of truth.
    -- Deliberate, temporary carve-out -- confirmed with the team to keep
    -- Miami 100% sheet-sourced regardless of scaffold source until Focus is
    -- ready as a scaffold source. Remove this filter (and update the
    -- sheet-side builder's Miami note below) once that happens.
    powerschool_schools as (
        select school_number, abbreviation, _dbt_source_project, region,
        from powerschool_region
        where region != 'Miami'
    ),

    -- Grade membership comes from actual current enrollment, not
    -- stg_powerschool__schools.low_grade/high_grade -- that field encodes a
    -- school's eventual, fully-built-out grade span, not what it currently
    -- serves (verified: growing schools like Hatch/Rise/Purpose carry a
    -- low_grade years below any student they've ever enrolled). enroll_status
    -- = 0 is "Currently Enrolled" -- this table has no academic_year column,
    -- so status (not a date range) is what scopes it to now. Also filters
    -- out negative grade_level: PowerSchool uses negative values for its own
    -- pre-registration / pre-K domain, and since this pipeline's convention
    -- is grade_level = -1 means PK, an unfiltered PowerSchool negative row
    -- would masquerade as a legitimate PK enrollment instead of being
    -- excluded as pre-registration noise.
    -- Known caveat: a school's very first student in a newly-opening grade
    -- may not be entered in PowerSchool yet even though Finalsite is already
    -- recruiting for that grade -- this scaffold won't carry that grade
    -- until PowerSchool has at least one enrolled student in it.
    -- Carries _dbt_source_project so grade_membership's join can't collide
    -- across districts on a repeated numeric schoolid -- each PowerSchool
    -- instance assigns schoolid independently, so an excluded/out-of-scope
    -- school in one district can share a schoolid with a reporting school in
    -- another.
    current_grade_levels as (
        select distinct schoolid, grade_level, _dbt_source_project,
        from {{ ref("stg_powerschool__students") }}
        where enroll_status = 0 and grade_level >= 0
    ),

    grade_membership as (
        select ps.school_number, ps.abbreviation, ps.region, cgl.grade_level,

        from powerschool_schools as ps
        inner join
            current_grade_levels as cgl
            on ps.school_number = cgl.schoolid
            and ps._dbt_source_project = cgl._dbt_source_project
    ),

    powerschool_scaffold as (
        select
            gm.school_number as schoolid,
            gm.abbreviation as school,
            gm.region,
            gm.grade_level,

            {{ var("finalsite_recruitment_year") }} as academic_year,

            'KTAF' as org,
            'powerschool' as scaffold_source,

            case
                when gm.grade_level >= 9
                then 'HS'
                when gm.grade_level >= 5
                then 'MS'
                else 'ES'
            end as school_level,

        from grade_membership as gm
    ),

    -- Scoped to the current cycle so a stale row from a prior year (a
    -- closed school, a dropped grade) doesn't look identical to "PS
    -- doesn't have this yet" and get silently resurrected forever. Miami
    -- must carry its FULL spine here (every school, every grade), not just
    -- -9 rows and net-new entries, since the PowerSchool builder excludes
    -- it entirely above.
    gsheet_scaffold as (
        select
            s.schoolid,
            s.school,
            s.region,
            s.grade_level,
            s.academic_year,
            s.org,
            s.school_level,

            'gsheet' as scaffold_source,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
        where s.academic_year = {{ var("finalsite_recruitment_year") }}
    )

select
    schoolid,
    school,
    region,
    grade_level,
    academic_year,
    org,
    scaffold_source,
    school_level,
from powerschool_scaffold

union all

select
    g.schoolid,
    g.school,
    g.region,
    g.grade_level,
    g.academic_year,
    g.org,
    g.scaffold_source,
    g.school_level,
from gsheet_scaffold as g
left join
    powerschool_scaffold as p
    on g.region = p.region
    and g.schoolid = p.schoolid
    and g.grade_level = p.grade_level
where p.schoolid is null
